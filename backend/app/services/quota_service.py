"""Persistent period budgets. Unknown dispatched usage keeps its reservation.

Reservations use a conservative input estimate and bounded output, not a provider
billing guarantee: reported usage may reconcile above the reservation/limit.
Crash-orphaned reservations deliberately remain charged (fail closed).
"""
import asyncio
import hashlib
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.core.errors import RouterException, ErrorCategory
from app.models.entities import (RouterApiKey, ProviderCredential, PeriodQuotaCounter, PeriodQuotaReservation,
    CredentialPeriodQuotaCounter, CredentialPeriodQuotaReservation)
from app.services.log_service import LogService, request_telemetry


def denied(message, credential_id=None):
    metadata = {"local_admission": True}
    if credential_id is not None:
        metadata.update(quota_owner="credential", credential_id=credential_id)
    return RouterException(message, ErrorCategory.RATE_LIMIT, status_code=429, raw_error=metadata)


def normalize_profile(name):
    return "judge/" + name[6:] if name and name.startswith("smart/") else name


def window(rule, now):
    period = rule["period"]
    if period == "interval":
        start, end = (datetime.fromisoformat(rule[k]) for k in ("start", "end"))
        if not start <= now < end:
            raise denied("Quota date interval is not active")
    elif period == "custom":
        anchor = datetime.fromisoformat(rule["anchor"])
        seconds = rule["duration_seconds"]
        start = anchor + timedelta(seconds=((now - anchor).total_seconds() // seconds) * seconds)
        end = start + timedelta(seconds=seconds)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + (start.month == 12), month=start.month % 12 + 1)
    else:
        seconds = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800}[period]
        anchor = datetime(1970, 1, 5 if period == "week" else 1, tzinfo=timezone.utc)
        start = anchor + timedelta(seconds=((now - anchor).total_seconds() // seconds) * seconds)
        end = start + timedelta(seconds=seconds)
    identity = {k: rule.get(k) for k in ("scope", "model", "period", "duration_seconds", "anchor", "start", "end")}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return digest, start.isoformat(), end.isoformat()


async def lock_key(db, key_id, owner=RouterApiKey):
    # SQLite's writer lock is acquired BEFORE reading counters, across processes.
    result = await db.execute(update(owner).where(owner.id == key_id).values(
        id=owner.id, updated_at=owner.updated_at).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise denied("API key no longer exists")
    return await db.scalar(select(owner).where(owner.id == key_id).execution_options(populate_existing=True))


async def counter(db, key_id, rule, now, table=PeriodQuotaCounter):
    try:
        identity, start, end = window(rule, now)
    except RouterException as exc:
        if table is CredentialPeriodQuotaCounter:
            raise denied(exc.message, key_id) from exc
        raise
    row = await db.get(table, (key_id, identity, start))
    if row is None:
        row = table(key_id=key_id, rule_identity=identity, window_start=start, requests=0, tokens=0, usd=0)
        db.add(row)
        await db.flush()
    return row, end


def check(rule, row, requests=0, tokens=0, usd=0, credential_id=None):
    for field, amount in (("requests", requests), ("tokens", tokens), ("usd", usd)):
        if rule.get(field) is not None and getattr(row, field) + amount > rule[field]:
            raise denied(f"Period {field} quota reached ({rule['scope']}: {rule.get('model') or 'key'})", credential_id)


class QuotaTicket:
    def __init__(self, reservation_id, direct_credits=None):
        self.id = reservation_id
        self.direct_credits = direct_credits or []

    async def finish(self, usage_dict=None, success=False, dispatched=True):
        # Shield and await cleanup so cancellation cannot strand a known refund.
        async def settle():
            claimed = await QuotaService.settle(self.id, usage_dict, dispatched)
            details = request_telemetry.get()
            if claimed and not dispatched and details is not None:
                pending = details.setdefault('quota_direct_pending', [])
                pending.extend(credit for credit in self.direct_credits if credit not in pending)
        task = asyncio.create_task(settle())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise


class QuotaService:
    @staticmethod
    async def admit(db, key, requested_model=None):
        requested_model = normalize_profile(requested_model)
        now = datetime.now(timezone.utc)
        direct_rules = []
        for rule in key.quota_rules or []:
            if not rule['enabled'] or rule['scope'] != 'key' and rule['model'] != requested_model:
                continue
            row, _ = await counter(db, key.id, rule, now)
            check(rule, row, requests=1)
            row.requests += 1
            if rule['scope'] == 'model':
                direct_rules.append((row.rule_identity, row.window_start))
        return direct_rules

    @staticmethod
    async def reserve_dispatch(provider, model_obj, request, *, credential=None):
        details = request_telemetry.get()
        details = details if details is not None else {}
        owners = []
        # Fixed owner order for reservation, editing and settlement: router, credential.
        if details.get('router_key_id'):
            owners.append((RouterApiKey, PeriodQuotaCounter, PeriodQuotaReservation, details['router_key_id']))
        if credential is not None:
            owners.append((ProviderCredential, CredentialPeriodQuotaCounter, CredentialPeriodQuotaReservation, credential.id))
        if not owners:
            return None, request
        async with AsyncSessionLocal() as db:
            active = []
            for owner, counters, reservations, key_id in owners:
                configured = await db.scalar(select(owner.quota_rules).where(owner.id == key_id))
                if configured and any(r['enabled'] for r in configured):
                    active.append((owner, counters, reservations, key_id))
            if not active:
                return None, request
            await db.rollback()
            direct_credits = []
            try:
                requested = normalize_profile(details.get('requested_model'))
                now = datetime.now(timezone.utc)
                rows = []
                for owner, counters, reservations, key_id in active:
                    key = await lock_key(db, key_id, owner)
                    for r in key.quota_rules or []:
                        if r['enabled'] and (r['scope'] == 'key' or
                            r['scope'] == 'model' and r['model'] == model_obj.canonical_slug or
                            owner is RouterApiKey and r['scope'] == 'profile' and r['model'] == requested):
                            row, end = await counter(db, key.id, r, now, counters)
                            rows.append((r, row, end, owner, reservations, key.id))
                if not rows:
                    await db.rollback()
                    return None, request
                rules = [r for r, *_ in rows]
                finite = any(r.get('tokens') is not None or r.get('usd') is not None for r in rules)
                prices = LogService.price_snapshot(model_obj)
                if any(r.get('usd') is not None for r in rules) and any(v is None for v in prices.values()):
                    raise denied('USD quota requires known input and output model prices (explicit zero is allowed)',
                        next((key_id for r, _, _, owner, _, key_id in rows if owner is ProviderCredential and r.get('usd') is not None), None))
                # UTF-8 bytes conservatively bound text tokens, including tools/history.
                native = not hasattr(request, 'get_effective_max_tokens')
                payload = request.model_dump() if native else request.model_dump(include={'messages', 'tools'})
                prompt = len(json.dumps(payload, ensure_ascii=False).encode()) if finite else 0
                if finite and any(isinstance(m.content, list) and any(p.get('type') not in ('text', 'input_text') for p in m.content) for m in getattr(request, 'messages', [])):
                    if not model_obj.context_length:
                        raise denied('Multimodal quota reservation requires a known context length')
                    prompt = max(prompt, model_obj.context_length)
                outputs = model_obj.max_output_tokens if native else request.get_effective_max_tokens()
                choices = getattr(request, 'n', None)
                choices = 1 if choices is None else choices
                if outputs is not None and (not isinstance(outputs, int) or isinstance(outputs, bool) or outputs < 1):
                    raise denied('Quota reservation requires a positive output budget')
                if not isinstance(choices, int) or isinstance(choices, bool) or choices < 1:
                    raise denied('Quota reservation requires a positive number of choices')
                if finite:
                    bounds = [v for v in (outputs, model_obj.max_output_tokens) if isinstance(v, int) and not isinstance(v, bool) and v > 0]
                    limiting_credential = None
                    for rule, row, _, owner, _, key_id in rows:
                        if rule.get('tokens') is not None:
                            affordable = (rule['tokens'] - row.tokens - prompt) // choices
                            bounds.append(affordable)
                            if owner is ProviderCredential and (affordable < 1 or native and outputs is not None and affordable < outputs):
                                limiting_credential = key_id
                        if rule.get('usd') is not None:
                            remaining = rule['usd'] - row.usd - prompt * (prices['input_per_1m'] / 1e6)
                            if not math.isfinite(remaining) or remaining < 0:
                                raise denied('USD quota cannot cover the input reservation', key_id if owner is ProviderCredential else None)
                            if prices['output_per_1m']:
                                affordable = remaining / prices['output_per_1m'] * 1e6 / choices
                                bounds.append(math.floor(affordable) if math.isfinite(affordable) else 2147483647)
                                if owner is ProviderCredential and (affordable < 1 or native and outputs is not None and affordable < outputs):
                                    limiting_credential = key_id
                    if not bounds or min(bounds) < 1:
                        raise denied('Finite quota requires a bounded positive output budget', limiting_credential)
                    if native and (not isinstance(outputs, int) or outputs < 1 or outputs > min(bounds)):
                        raise denied('Native decision quota requires its full known model output ceiling; this endpoint cannot clamp output', limiting_credential)
                    outputs = min(bounds)
                    if not native:
                        request = request.model_copy(update={'max_tokens': outputs, 'max_completion_tokens': outputs})
                tokens = prompt + (outputs or 0) * choices if finite else 0
                estimated_cost = LogService.cost_for_usage(prices, {'prompt_tokens': prompt, 'completion_tokens': (outputs or 0) * choices}) if finite else 0
                if estimated_cost is None and any(r.get('usd') is not None for r in rules):
                    raise denied('USD quota cannot reserve an unknown or nonfinite cost')
                usd = estimated_cost or 0
                allocations = {}
                direct_credits = []
                for rule, row, _, owner, reservations, key_id in rows:
                    credit = (row.rule_identity, row.window_start)
                    admitted_direct = owner is RouterApiKey and rule['scope'] == 'model' and credit in details.get('quota_direct_pending', [])
                    count = int(owner is ProviderCredential or rule['scope'] == 'model' and not admitted_direct)
                    if admitted_direct:
                        direct_credits.append(credit)
                    check(rule, row, count, tokens, usd, key_id if owner is ProviderCredential else None)
                    row.requests += count
                    row.tokens += tokens
                    row.usd += usd
                    allocations.setdefault((reservations, key_id), []).append({'identity': row.rule_identity, 'start': row.window_start, 'requests': count, 'tokens': tokens, 'usd': usd})
                reservation_id = uuid.uuid4().hex
                for (reservations, key_id), values in allocations.items():
                    db.add(reservations(id=reservation_id, key_id=key_id, allocations=values, prices=prices, settled=False))
                pending = details.get('quota_direct_pending', [])
                # Claim request-local first-dispatch credit before releasing SQLite's writer lock.
                for credit in direct_credits:
                    pending.remove(credit)
                await db.commit()
                return QuotaTicket(reservation_id, direct_credits), request
            except BaseException:
                await db.rollback()
                pending = details.setdefault('quota_direct_pending', [])
                pending.extend(credit for credit in direct_credits if credit not in pending)
                raise

    @staticmethod
    async def settle(reservation_id, usage, dispatched):
        async with AsyncSessionLocal() as db:
            claimed = False
            # Same table order as reserve; both claims and reconciliations commit together.
            for reservations, counters in ((PeriodQuotaReservation, PeriodQuotaCounter),
                                            (CredentialPeriodQuotaReservation, CredentialPeriodQuotaCounter)):
                result = await db.execute(update(reservations).where(reservations.id == reservation_id,
                    reservations.settled == False).values(settled=True))
                if result.rowcount != 1:
                    continue
                claimed = True
                reservation = await db.get(reservations, reservation_id)
                usage = usage if isinstance(usage, dict) else {}
                def count(*names):
                    value = next((usage[n] for n in names if n in usage), None)
                    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
                incoming, outgoing = count('prompt_tokens', 'input_tokens'), count('completion_tokens', 'output_tokens')
                total = count('total_tokens')
                known = (incoming or 0) + (outgoing or 0)
                if incoming is not None and outgoing is not None:
                    total = max(total or 0, known)
                elif total is not None and total < known:
                    # A default/inconsistent total cannot refund an unknown component.
                    total = None
                cost = LogService.cost_for_usage(reservation.prices, usage)
                for allocation in reservation.allocations:
                    row = await db.get(counters, (reservation.key_id, allocation['identity'], allocation['start']))
                    row.requests -= allocation['requests'] if not dispatched else 0
                    row.tokens += (total if total is not None else max(allocation['tokens'], known)) - allocation['tokens'] if dispatched else -allocation['tokens']
                    row.usd += (cost if cost is not None else allocation['usd']) - allocation['usd'] if dispatched else -allocation['usd']
            await db.commit()
            return claimed

    @staticmethod
    async def usage(db, key):
        result = []
        counters = CredentialPeriodQuotaCounter if isinstance(key, ProviderCredential) else PeriodQuotaCounter
        now = datetime.now(timezone.utc)
        for rule in key.quota_rules or []:
            try:
                identity, start, end = window(rule, now)
                active = rule['enabled']
            except RouterException:
                identity, start, end = window(rule, datetime.fromisoformat(rule['start']))
                active = False
            row = await db.get(counters, (key.id, identity, start))
            used = {f: getattr(row, f) if row else 0 for f in ('requests', 'tokens', 'usd')}
            result.append({'rule_id': rule['id'], 'scope': rule['scope'], 'model': rule.get('model'), 'active': active,
                           'start': start, 'end': end, 'used': used,
                           'remaining': {f: max(0, rule[f] - used[f]) if rule.get(f) is not None else None for f in used}})
        return result
