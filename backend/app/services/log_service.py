from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, desc, or_, asc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import (
    RequestLog,
    RequestAttempt,
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
    FusionProfile,
    FusionParticipant,
    JudgeProfile,
    RouterApiKey,
)
from app.schemas.entities import (
    RequestLogRead,
    RequestAttemptRead,
    LogsSummaryResponse,
    DashboardStats,
    DetailedAnalyticsResponse,
    SummaryStats,
    SummaryComparison,
    StatusCodeItem,
    TopErrorItem,
    FallbackFunnelStats,
    KeyStatsItem,
    CredentialStatsItem,
    ProviderStatsItem,
    ModelStatsItem,
    ProfileCandidateStat,
    ProfileStatsItem,
    TimeBucketStatsItem,
)
from app.core.config import settings

class LogService:
    @classmethod
    async def record_request_log(
        cls,
        db: AsyncSession,
        request_id: str,
        requested_model: str,
        mode: str,
        status: str,
        status_code: int,
        latency_ms: float,
        router_key_id: Optional[int] = None,
        resolved_provider_id: Optional[int] = None,
        resolved_credential_id: Optional[int] = None,
        upstream_model: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        error_category: Optional[str] = None,
        error_message: Optional[str] = None,
        prompt_content: Optional[str] = None,
        response_content: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        attempts: Optional[List[Dict[str, Any]]] = None,
        input_price_per_1m: float = 0.0,
        output_price_per_1m: float = 0.0,
    ) -> RequestLog:
        # Calculate cost estimate
        est_cost = ((input_tokens / 1_000_000.0) * input_price_per_1m) + ((output_tokens / 1_000_000.0) * output_price_per_1m)

        # Privacy check: never store prompt/response unless LOG_REQUEST_CONTENT enabled
        stored_prompt = prompt_content if settings.LOG_REQUEST_CONTENT else None
        stored_response = response_content if settings.LOG_REQUEST_CONTENT else None

        log_obj = RequestLog(
            request_id=request_id,
            router_key_id=router_key_id,
            requested_model=requested_model,
            mode=mode,
            resolved_provider_id=resolved_provider_id,
            resolved_credential_id=resolved_credential_id,
            upstream_model=upstream_model,
            latency_ms=latency_ms,
            status_code=status_code,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            estimated_cost_usd=round(est_cost, 6),
            error_category=error_category,
            error_message=error_message,
            prompt_content=stored_prompt,
            response_content=stored_response,
            metadata_json=metadata_json or {},
        )
        db.add(log_obj)
        await db.flush()

        if attempts:
            for a in attempts:
                att = RequestAttempt(
                    request_log_id=log_obj.id,
                    attempt_number=a.get("attempt_number", 1),
                    provider_name=a.get("provider_name", "Unknown"),
                    credential_name=a.get("credential_name", "Unknown"),
                    model_name=a.get("model_name", "Unknown"),
                    status=a.get("status", "FAILED"),
                    http_status=a.get("http_status"),
                    error_category=a.get("error_category"),
                    error_message=a.get("error_message"),
                    latency_ms=a.get("latency_ms", 0.0),
                )
                db.add(att)

        await db.commit()
        return log_obj

    @classmethod
    def _apply_log_filters(
        cls,
        query,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mode: Optional[str] = None,
        status: Optional[str] = None,
        status_code: Optional[int] = None,
        provider_id: Optional[int] = None,
        model: Optional[str] = None,
        router_key_id: Optional[int] = None,
        has_error: Optional[bool] = None,
        has_fallback: Optional[bool] = None,
        min_latency: Optional[float] = None,
        is_stream: Optional[bool] = None,
        search: Optional[str] = None,
    ):
        if start_date:
            try:
                s_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.where(RequestLog.created_at >= s_dt)
            except Exception:
                pass
        if end_date:
            try:
                e_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if len(end_date) == 10:
                    e_dt = e_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                query = query.where(RequestLog.created_at <= e_dt)
            except Exception:
                pass
        if mode:
            query = query.where(RequestLog.mode == mode)
        if status:
            query = query.where(RequestLog.status == status)
        if status_code is not None:
            query = query.where(RequestLog.status_code == status_code)
        if provider_id is not None:
            query = query.where(RequestLog.resolved_provider_id == provider_id)
        if model and model.strip():
            m_term = f"%{model.strip()}%"
            query = query.where(
                or_(
                    RequestLog.requested_model.ilike(m_term),
                    RequestLog.upstream_model.ilike(m_term),
                )
            )
        if router_key_id is not None:
            query = query.where(RequestLog.router_key_id == router_key_id)
        if has_error is True:
            query = query.where(or_(RequestLog.status == "FAILED", RequestLog.status_code >= 400))
        elif has_error is False:
            query = query.where(RequestLog.status != "FAILED", RequestLog.status_code < 400)
        if has_fallback is True:
            query = query.where(RequestLog.status == "FALLBACK_SUCCESS")
        if min_latency is not None and min_latency > 0:
            query = query.where(RequestLog.latency_ms >= min_latency)
        if is_stream is True:
            query = query.where(
                or_(
                    func.json_extract(RequestLog.metadata_json, "$.stream") == 1,
                    func.json_extract(RequestLog.metadata_json, "$.stream") == True,
                    func.json_extract(RequestLog.metadata_json, "$.stream") == "true",
                )
            )
        elif is_stream is False:
            query = query.where(
                or_(
                    func.json_extract(RequestLog.metadata_json, "$.stream") == None,
                    func.json_extract(RequestLog.metadata_json, "$.stream") == 0,
                    func.json_extract(RequestLog.metadata_json, "$.stream") == False,
                    func.json_extract(RequestLog.metadata_json, "$.stream") == "false",
                )
            )
        if search and search.strip():
            s_term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    RequestLog.requested_model.ilike(s_term),
                    RequestLog.upstream_model.ilike(s_term),
                    RequestLog.request_id.ilike(s_term),
                    RequestLog.error_message.ilike(s_term),
                )
            )
        return query

    @classmethod
    async def list_logs(
        cls,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mode: Optional[str] = None,
        status: Optional[str] = None,
        status_code: Optional[int] = None,
        provider_id: Optional[int] = None,
        model: Optional[str] = None,
        router_key_id: Optional[int] = None,
        has_error: Optional[bool] = None,
        has_fallback: Optional[bool] = None,
        min_latency: Optional[float] = None,
        is_stream: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = "created_at",
        sort_order: Optional[str] = "desc",
    ) -> List[RequestLogRead]:
        query = select(RequestLog).options(
            selectinload(RequestLog.attempts),
            selectinload(RequestLog.router_key),
            selectinload(RequestLog.resolved_provider),
            selectinload(RequestLog.resolved_credential),
        )
        query = cls._apply_log_filters(
            query,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            status=status,
            status_code=status_code,
            provider_id=provider_id,
            model=model,
            router_key_id=router_key_id,
            has_error=has_error,
            has_fallback=has_fallback,
            min_latency=min_latency,
            is_stream=is_stream,
            search=search,
        )

        sort_col = RequestLog.id
        if sort_by == "created_at":
            sort_col = RequestLog.created_at
        elif sort_by == "latency_ms":
            sort_col = RequestLog.latency_ms
        elif sort_by in ("tokens", "total_tokens"):
            sort_col = RequestLog.input_tokens + RequestLog.output_tokens
        elif sort_by in ("cost", "estimated_cost_usd"):
            sort_col = RequestLog.estimated_cost_usd

        if sort_order == "asc":
            query = query.order_by(asc(sort_col), asc(RequestLog.id))
        else:
            query = query.order_by(desc(sort_col), desc(RequestLog.id))

        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        logs = result.scalars().all()

        output = []
        for l in logs:
            key_name = l.router_key.name if l.router_key else ("Admin Session" if not l.router_key_id else f"Key #{l.router_key_id}")
            prov_name = l.resolved_provider.name if l.resolved_provider else None
            cred_name = l.resolved_credential.name if l.resolved_credential else None
            output.append(
                RequestLogRead(
                    id=l.id,
                    request_id=l.request_id,
                    router_key_id=l.router_key_id,
                    router_key_name=key_name,
                    requested_model=l.requested_model,
                    mode=l.mode,
                    resolved_provider_name=prov_name,
                    resolved_credential_name=cred_name,
                    upstream_model=l.upstream_model,
                    latency_ms=l.latency_ms,
                    status_code=l.status_code,
                    status=l.status,
                    input_tokens=l.input_tokens,
                    output_tokens=l.output_tokens,
                    cached_tokens=l.cached_tokens,
                    reasoning_tokens=l.reasoning_tokens,
                    estimated_cost_usd=l.estimated_cost_usd,
                    error_category=l.error_category,
                    error_message=l.error_message,
                    prompt_content=l.prompt_content,
                    response_content=l.response_content,
                    metadata_json=l.metadata_json,
                    created_at=l.created_at,
                    attempts=[
                        RequestAttemptRead(
                            id=att.id,
                            attempt_number=att.attempt_number,
                            provider_name=att.provider_name,
                            credential_name=att.credential_name,
                            model_name=att.model_name,
                            status=att.status,
                            http_status=att.http_status,
                            error_category=att.error_category,
                            error_message=att.error_message,
                            latency_ms=att.latency_ms,
                        )
                        for att in l.attempts
                    ],
                )
            )
        return output

    @classmethod
    async def count_logs(
        cls,
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mode: Optional[str] = None,
        status: Optional[str] = None,
        status_code: Optional[int] = None,
        provider_id: Optional[int] = None,
        model: Optional[str] = None,
        router_key_id: Optional[int] = None,
        has_error: Optional[bool] = None,
        has_fallback: Optional[bool] = None,
        min_latency: Optional[float] = None,
        is_stream: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> int:
        query = select(func.count(RequestLog.id))
        query = cls._apply_log_filters(
            query,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            status=status,
            status_code=status_code,
            provider_id=provider_id,
            model=model,
            router_key_id=router_key_id,
            has_error=has_error,
            has_fallback=has_fallback,
            min_latency=min_latency,
            is_stream=is_stream,
            search=search,
        )
        return (await db.execute(query)).scalar_one() or 0

    @classmethod
    async def get_logs_summary(
        cls,
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mode: Optional[str] = None,
        status: Optional[str] = None,
        status_code: Optional[int] = None,
        provider_id: Optional[int] = None,
        model: Optional[str] = None,
        router_key_id: Optional[int] = None,
        has_error: Optional[bool] = None,
        has_fallback: Optional[bool] = None,
        min_latency: Optional[float] = None,
        is_stream: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> LogsSummaryResponse:
        query = select(
            func.count(RequestLog.id),
            func.sum(case((or_(RequestLog.status == "FAILED", RequestLog.status_code >= 400), 1), else_=0)),
            func.avg(RequestLog.latency_ms),
            func.sum(RequestLog.input_tokens),
            func.sum(RequestLog.output_tokens),
            func.sum(RequestLog.cached_tokens),
            func.sum(RequestLog.reasoning_tokens),
            func.sum(RequestLog.estimated_cost_usd),
            func.sum(case((RequestLog.status == "FALLBACK_SUCCESS", 1), else_=0)),
        )
        query = cls._apply_log_filters(
            query,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            status=status,
            status_code=status_code,
            provider_id=provider_id,
            model=model,
            router_key_id=router_key_id,
            has_error=has_error,
            has_fallback=has_fallback,
            min_latency=min_latency,
            is_stream=is_stream,
            search=search,
        )
        row = (await db.execute(query)).one()
        total_reqs = row[0] or 0
        total_errs = int(row[1] or 0)
        avg_lat = round(float(row[2] or 0.0), 1)
        in_toks = int(row[3] or 0)
        out_toks = int(row[4] or 0)
        cached_toks = int(row[5] or 0)
        reasoning_toks = int(row[6] or 0)
        cost = round(float(row[7] or 0.0), 4)
        fallback_rescued = int(row[8] or 0)
        err_rate = round((total_errs / total_reqs * 100), 1) if total_reqs > 0 else 0.0

        return LogsSummaryResponse(
            total_requests=total_reqs,
            total_errors=total_errs,
            error_rate=err_rate,
            avg_latency_ms=avg_lat,
            total_tokens=in_toks + out_toks,
            total_prompt_tokens=in_toks,
            total_completion_tokens=out_toks,
            total_cached_tokens=cached_toks,
            total_reasoning_tokens=reasoning_toks,
            total_cost_usd=cost,
            total_fallback_rescued=fallback_rescued,
        )

    @classmethod
    async def get_dashboard_stats(cls, db: AsyncSession) -> DashboardStats:
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        p_count = (await db.execute(select(func.count(Provider.id)))).scalar_one()
        c_count = (await db.execute(select(func.count(ProviderCredential.id)))).scalar_one()
        healthy_c_count = (await db.execute(
            select(func.count(ProviderCredential.id)).where(
                ProviderCredential.status == "HEALTHY",
                ProviderCredential.enabled == True,
            )
        )).scalar_one()
        m_count = (await db.execute(select(func.count(DiscoveredModel.id)))).scalar_one()
        r_count = (await db.execute(select(func.count(RoutingProfile.id)))).scalar_one()
        f_count = (await db.execute(select(func.count(FusionProfile.id)))).scalar_one()
        j_count = (await db.execute(select(func.count(JudgeProfile.id)))).scalar_one()

        # 24h stats
        reqs_24h = (await db.execute(
            select(func.count(RequestLog.id)).where(RequestLog.created_at >= day_ago)
        )).scalar_one()

        success_24h = (await db.execute(
            select(func.count(RequestLog.id)).where(
                RequestLog.created_at >= day_ago,
                RequestLog.status.in_(["SUCCESS", "FALLBACK_SUCCESS", "FUSION_SUCCESS", "JUDGE_FALLBACK_SUCCESS"]),
            )
        )).scalar_one()

        fallbacks_24h = (await db.execute(
            select(func.count(RequestLog.id)).where(
                RequestLog.created_at >= day_ago,
                RequestLog.status.in_(["FALLBACK_SUCCESS", "JUDGE_FALLBACK_SUCCESS"]),
            )
        )).scalar_one()

        avg_lat = (await db.execute(
            select(func.avg(RequestLog.latency_ms)).where(RequestLog.created_at >= day_ago)
        )).scalar_one() or 0.0

        total_tokens = (await db.execute(
            select(func.sum(RequestLog.input_tokens + RequestLog.output_tokens)).where(RequestLog.created_at >= day_ago)
        )).scalar_one() or 0

        total_cost = (await db.execute(
            select(func.sum(RequestLog.estimated_cost_usd)).where(RequestLog.created_at >= day_ago)
        )).scalar_one() or 0.0

        success_rate = (success_24h / reqs_24h * 100.0) if reqs_24h > 0 else 100.0

        return DashboardStats(
            total_providers=p_count,
            total_credentials=c_count,
            healthy_credentials=healthy_c_count,
            total_models=m_count,
            total_routes=r_count,
            total_fusions=f_count,
            total_judges=j_count,
            requests_24h=reqs_24h,
            fallbacks_24h=fallbacks_24h,
            success_rate_24h=round(success_rate, 1),
            avg_latency_24h=round(float(avg_lat), 1),
            total_tokens_24h=int(total_tokens),
            estimated_cost_24h=round(float(total_cost), 4),
        )

    @classmethod
    async def get_detailed_analytics(
        cls,
        db: AsyncSession,
        period: str = "all",
        granularity: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> DetailedAnalyticsResponse:
        now = datetime.now(timezone.utc)
        now_naive = now.replace(tzinfo=None)

        def parse_dt(val: Optional[str], is_end: bool = False) -> Optional[datetime]:
            if not val:
                return None
            val = val.strip()
            try:
                if len(val) == 10 and "-" in val:
                    dt = datetime.strptime(val, "%Y-%m-%d")
                    if is_end:
                        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                    return dt
                clean_val = val.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_val)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                return None

        # Preload metadata mappings
        providers = {p.id: p for p in (await db.execute(select(Provider))).scalars().all()}
        prov_slug_map = {p.slug: p.id for p in providers.values()}
        for p in providers.values():
            prov_slug_map[p.name.lower()] = p.id
        creds = {c.id: c for c in (await db.execute(select(ProviderCredential).options(selectinload(ProviderCredential.provider)))).scalars().all()}
        rkeys = {k.id: k for k in (await db.execute(select(RouterApiKey))).scalars().all()}
        
        routes_query = select(RoutingProfile).options(
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.model),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.target_profile).selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.model),
        )
        routes = {r.slug: r for r in (await db.execute(routes_query)).scalars().all()}

        fusions_query = select(FusionProfile).options(
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.model),
        )
        fusions = {f.slug: f for f in (await db.execute(fusions_query)).scalars().all()}

        disc_models = (await db.execute(select(DiscoveredModel))).scalars().all()
        model_prices = {}
        for dm in disc_models:
            if dm.input_price_per_1m:
                model_prices[dm.provider_model_id] = dm.input_price_per_1m
                model_prices[dm.canonical_slug] = dm.input_price_per_1m

        # Helper to apply date and drilldown filters
        def apply_query_filters(q, s_dt, e_dt, f_type, f_val):
            if s_dt:
                q = q.where(RequestLog.created_at >= s_dt)
            if e_dt:
                q = q.where(RequestLog.created_at <= e_dt)
            if f_type and f_val:
                clean_f = str(f_val).strip()
                if f_type == "model":
                    clean_m = clean_f.removeprefix("route/").removeprefix("fusion/")
                    q = q.where(
                        or_(
                            RequestLog.requested_model == clean_f,
                            RequestLog.upstream_model == clean_f,
                            RequestLog.requested_model == clean_m,
                            RequestLog.upstream_model == clean_m,
                            RequestLog.requested_model == f"route/{clean_m}",
                            RequestLog.requested_model == f"fusion/{clean_m}",
                        )
                    )
                elif f_type == "provider":
                    pid = None
                    if clean_f.isdigit():
                        pid = int(clean_f)
                    elif clean_f.lower() in prov_slug_map:
                        pid = prov_slug_map[clean_f.lower()]
                    if pid is not None:
                        q = q.where(RequestLog.resolved_provider_id == pid)
                elif f_type == "credential":
                    if clean_f.isdigit():
                        q = q.where(RequestLog.resolved_credential_id == int(clean_f))
                elif f_type == "key":
                    if clean_f in ("0", "direct", "null", "admin"):
                        q = q.where(RequestLog.router_key_id.is_(None))
                    elif clean_f.isdigit():
                        q = q.where(RequestLog.router_key_id == int(clean_f))
                elif f_type == "profile":
                    clean_p = clean_f.removeprefix("route/").removeprefix("fusion/")
                    q = q.where(
                        or_(
                            RequestLog.requested_model == clean_f,
                            RequestLog.requested_model == clean_p,
                            RequestLog.requested_model == f"route/{clean_p}",
                            RequestLog.requested_model == f"fusion/{clean_p}",
                        )
                    )
            return q

        # Determine start/end bounds and comparison bounds
        eff_period = period
        parsed_start = parse_dt(start_date)
        parsed_end = parse_dt(end_date, is_end=True)
        
        start_dt = None
        end_dt = None
        prev_start_dt = None
        prev_end_dt = None

        if parsed_start and parsed_end:
            eff_period = "custom"
            start_dt = parsed_start
            end_dt = parsed_end
            span = end_dt - start_dt
            prev_end_dt = start_dt
            prev_start_dt = start_dt - span
            span_h = span.total_seconds() / 3600.0
            eff_granularity = granularity or ("hour" if span_h <= 48.0 else "day")
            t_start = start_dt
            t_end = end_dt
        elif period == "today":
            start_dt = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now_naive
            prev_start_dt = start_dt - timedelta(days=1)
            prev_end_dt = end_dt - timedelta(days=1)
            eff_granularity = granularity or "hour"
            t_start = start_dt
            t_end = end_dt.replace(minute=0, second=0, microsecond=0)
        elif period == "yesterday":
            yesterday = now_naive - timedelta(days=1)
            start_dt = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            prev_start_dt = start_dt - timedelta(days=1)
            prev_end_dt = start_dt - timedelta(microseconds=1)
            eff_granularity = granularity or "hour"
            t_start = start_dt
            t_end = yesterday.replace(hour=23, minute=0, second=0, microsecond=0)
        elif period == "24h":
            eff_granularity = granularity or "hour"
            start_dt = (now_naive - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
            end_dt = now_naive.replace(minute=0, second=0, microsecond=0)
            prev_start_dt = start_dt - timedelta(hours=24)
            prev_end_dt = start_dt
            t_start = start_dt
            t_end = end_dt
        elif period == "7d":
            eff_granularity = granularity or "day"
            if eff_granularity == "hour":
                start_dt = (now_naive - timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
                end_dt = now_naive.replace(minute=0, second=0, microsecond=0)
            else:
                start_dt = (now_naive - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start_dt = start_dt - (end_dt - start_dt)
            prev_end_dt = start_dt
            t_start = start_dt
            t_end = end_dt
        elif period == "30d":
            eff_granularity = granularity or "day"
            if eff_granularity == "hour":
                start_dt = (now_naive - timedelta(days=30)).replace(minute=0, second=0, microsecond=0)
                end_dt = now_naive.replace(minute=0, second=0, microsecond=0)
            else:
                start_dt = (now_naive - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start_dt = start_dt - (end_dt - start_dt)
            prev_end_dt = start_dt
            t_start = start_dt
            t_end = end_dt
        elif period == "this_month":
            eff_granularity = granularity or "day"
            start_dt = now_naive.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = now_naive
            span = end_dt - start_dt
            prev_end_dt = start_dt
            prev_start_dt = start_dt - span
            t_start = start_dt
            t_end = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
        else: # "all"
            eff_period = "all"
            start_dt = None
            end_dt = now_naive
            eff_granularity = granularity or "hour"
            t_start = None
            t_end = None

        # Fetch main logs
        main_query = apply_query_filters(
            select(RequestLog).order_by(RequestLog.id.asc()),
            start_dt,
            end_dt,
            filter_type,
            filter_value,
        )
        logs_res = await db.execute(main_query)
        logs = logs_res.scalars().all()

        # Detect bounds from logs if start_dt is not set (e.g. for "all")
        min_dt = None
        for l in logs:
            if l.created_at:
                dt = l.created_at
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                if min_dt is None or dt < min_dt:
                    min_dt = dt

        if eff_period == "all":
            if min_dt is None:
                t_start = (now_naive - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
                t_end = now_naive.replace(minute=0, second=0, microsecond=0)
                eff_granularity = granularity or "hour"
            else:
                span_hours = (now_naive - min_dt).total_seconds() / 3600.0
                eff_granularity = granularity or ("hour" if span_hours <= 48.0 else "day")
                if eff_granularity == "hour":
                    t_start = min_dt.replace(minute=0, second=0, microsecond=0)
                    t_end = now_naive.replace(minute=0, second=0, microsecond=0)
                else:
                    t_start = min_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    t_end = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)

        # Pre-populate continuous time buckets
        time_agg = {}
        curr = t_start.replace(minute=0, second=0, microsecond=0) if eff_granularity == "hour" else t_start.replace(hour=0, minute=0, second=0, microsecond=0)
        span_total_hours = (t_end - t_start).total_seconds() / 3600.0
        while curr <= t_end:
            if eff_granularity == "hour":
                b_key = curr.strftime("%Y-%m-%d %H:00")
                b_label = curr.strftime("%d %b %H:00") if span_total_hours > 24 else curr.strftime("%H:00")
                next_step = timedelta(hours=1)
            else:
                b_key = curr.strftime("%Y-%m-%d")
                b_label = curr.strftime("%d %b")
                next_step = timedelta(days=1)

            time_agg[b_key] = {
                "label": b_label,
                "ts": b_key,
                "requests": 0,
                "errors": 0,
                "fallbacks": 0,
                "tokens": 0,
                "cost": 0.0,
                "latencies": [],
            }
            curr += next_step

        # Pre-seed profile_agg
        profile_agg = {}
        cand_models_map = {}
        for r_slug, r_obj in routes.items():
            cands_info = []
            cand_models_list = []
            for c in sorted(r_obj.candidates, key=lambda x: x.priority_order):
                models_set = set()
                c_name = ""
                c_model_id = None
                if c.candidate_type == "profile" and c.target_profile:
                    c_name = f"Profile: {c.target_profile.name}"
                    c_model_id = f"route/{c.target_profile.slug}"
                    for sub_c in c.target_profile.candidates:
                        if sub_c.model:
                            models_set.add(sub_c.model.provider_model_id)
                            models_set.add(sub_c.model.canonical_slug)
                            if sub_c.model.display_name:
                                models_set.add(sub_c.model.display_name)
                elif c.model:
                    c_name = c.model.display_name or c.model.provider_model_id
                    c_model_id = c.model.provider_model_id
                    models_set.add(c.model.provider_model_id)
                    models_set.add(c.model.canonical_slug)
                    if c.model.display_name:
                        models_set.add(c.model.display_name)
                else:
                    c_name = f"Candidate #{c.priority_order + 1}"

                cand_models_list.append((c, models_set))
                cands_info.append(
                    ProfileCandidateStat(
                        priority_order=c.priority_order,
                        name=c_name,
                        model_id=c_model_id,
                        candidate_type=c.candidate_type,
                        requests_count=0,
                        success_count=0,
                    )
                )

            cand_models_map[r_slug] = cand_models_list
            profile_agg[r_slug] = {
                "slug": r_slug,
                "name": r_obj.name,
                "mode": "PRIORITY",
                "is_active": r_obj.enabled,
                "candidates_count": len(r_obj.candidates),
                "requests": 0,
                "success": 0,
                "first_candidate_success": 0,
                "fallback_success": 0,
                "key_failovers": 0,
                "failure": 0,
                "prompt_tok": 0,
                "compl_tok": 0,
                "cached_tok": 0,
                "reasoning_tok": 0,
                "cost": 0.0,
                "latencies": [],
                "candidates": cands_info,
            }

        for f_slug, f_obj in fusions.items():
            f_cands = [
                ProfileCandidateStat(
                    priority_order=idx,
                    name=p.label or (p.model.display_name if p.model else f"Participant #{idx+1}"),
                    model_id=p.model.provider_model_id if p.model else None,
                    candidate_type="fusion_participant",
                    requests_count=0,
                    success_count=0,
                )
                for idx, p in enumerate(f_obj.participants)
            ]
            profile_agg[f_slug] = {
                "slug": f_slug,
                "name": f_obj.name,
                "mode": "FUSION",
                "is_active": f_obj.enabled,
                "candidates_count": len(f_obj.participants),
                "requests": 0,
                "success": 0,
                "first_candidate_success": 0,
                "fallback_success": 0,
                "key_failovers": 0,
                "failure": 0,
                "prompt_tok": 0,
                "compl_tok": 0,
                "cached_tok": 0,
                "reasoning_tok": 0,
                "cost": 0.0,
                "latencies": [],
                "candidates": f_cands,
            }

        tot_req = len(logs)
        succ_req = 0
        fail_req = 0
        fallback_req = 0
        tot_prompt = 0
        tot_compl = 0
        tot_cached = 0
        tot_reasoning = 0
        tot_cost = 0.0
        latencies = []
        cached_saved_usd = 0.0

        key_agg = {}
        cred_agg = {}
        prov_agg = {}
        model_agg = {}
        status_code_counts: Dict[int, int] = {}
        error_counts: Dict[tuple, Dict[str, Any]] = {}

        total_profile_requests = 0

        for l in logs:
            is_success = l.status in ("SUCCESS", "FALLBACK_SUCCESS", "FUSION_SUCCESS")
            is_fallback = l.status == "FALLBACK_SUCCESS"
            if is_success:
                succ_req += 1
            else:
                fail_req += 1
            if is_fallback:
                fallback_req += 1

            in_t = l.input_tokens or 0
            out_t = l.output_tokens or 0
            c_t = l.cached_tokens or 0
            r_t = l.reasoning_tokens or 0

            tot_prompt += in_t
            tot_compl += out_t
            tot_cached += c_t
            tot_reasoning += r_t
            tot_cost += (l.estimated_cost_usd or 0.0)
            if l.latency_ms:
                latencies.append(l.latency_ms)

            # Caching savings
            if c_t > 0:
                m_ref = l.upstream_model or l.requested_model
                p_price = model_prices.get(m_ref, 1.20)
                cached_saved_usd += (c_t / 1_000_000.0) * (p_price * 0.75)

            # Status codes
            sc = l.status_code or (200 if is_success else 500)
            status_code_counts[sc] = status_code_counts.get(sc, 0) + 1

            # Top errors
            if not is_success or l.error_message:
                if l.error_message:
                    clean_msg = l.error_message.strip()
                    short_msg = clean_msg[:250] + "..." if len(clean_msg) > 250 else clean_msg
                    cat = l.error_category or "UnknownError"
                    err_key = (cat, short_msg)
                    if err_key not in error_counts:
                        error_counts[err_key] = {
                            "count": 0,
                            "last_seen": l.created_at.isoformat() if l.created_at else None,
                        }
                    error_counts[err_key]["count"] += 1
                    if l.created_at:
                        error_counts[err_key]["last_seen"] = l.created_at.isoformat()

            # Timeline bucket
            if l.created_at:
                dt = l.created_at
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                if eff_granularity == "hour":
                    bucket_key = dt.strftime("%Y-%m-%d %H:00")
                    label = dt.strftime("%d %b %H:00") if span_total_hours > 24 else dt.strftime("%H:00")
                else:
                    bucket_key = dt.strftime("%Y-%m-%d")
                    label = dt.strftime("%d %b")

                if bucket_key not in time_agg:
                    time_agg[bucket_key] = {
                        "label": label,
                        "ts": bucket_key,
                        "requests": 0,
                        "errors": 0,
                        "fallbacks": 0,
                        "tokens": 0,
                        "cost": 0.0,
                        "latencies": [],
                    }
                time_agg[bucket_key]["requests"] += 1
                if not is_success:
                    time_agg[bucket_key]["errors"] += 1
                if is_fallback:
                    time_agg[bucket_key]["fallbacks"] += 1
                time_agg[bucket_key]["tokens"] += (in_t + out_t)
                time_agg[bucket_key]["cost"] += (l.estimated_cost_usd or 0.0)
                if l.latency_ms:
                    time_agg[bucket_key]["latencies"].append(l.latency_ms)

            # By Router API Key
            kid = l.router_key_id or 0
            if kid not in key_agg:
                k_obj = rkeys.get(kid)
                key_agg[kid] = {
                    "id": kid if kid else None,
                    "name": k_obj.name if k_obj else ("Direct/Admin" if kid == 0 else f"Key #{kid}"),
                    "prefix": k_obj.key_prefix if k_obj else ("admin" if kid == 0 else "-"),
                    "requests": 0, "success": 0, "failure": 0,
                    "prompt_tok": 0, "compl_tok": 0, "cached_tok": 0, "reasoning_tok": 0,
                    "cost": 0.0, "latencies": [],
                }
            kstat = key_agg[kid]
            kstat["requests"] += 1
            if is_success: kstat["success"] += 1
            else: kstat["failure"] += 1
            kstat["prompt_tok"] += in_t
            kstat["compl_tok"] += out_t
            kstat["cached_tok"] += c_t
            kstat["reasoning_tok"] += r_t
            kstat["cost"] += (l.estimated_cost_usd or 0.0)
            if l.latency_ms: kstat["latencies"].append(l.latency_ms)

            # By Credential
            cid = l.resolved_credential_id or 0
            if cid:
                if cid not in cred_agg:
                    c_obj = creds.get(cid)
                    cred_agg[cid] = {
                        "id": cid,
                        "name": c_obj.name if c_obj else f"Key #{cid}",
                        "provider_name": c_obj.provider.name if c_obj and c_obj.provider else (providers.get(l.resolved_provider_id).name if l.resolved_provider_id in providers else "Unknown"),
                        "status": c_obj.status.value if c_obj and hasattr(c_obj.status, "value") else str(getattr(c_obj, "status", "UNKNOWN")),
                        "requests": 0, "success": 0, "failure": 0, "fallback_success": 0,
                        "prompt_tok": 0, "compl_tok": 0, "cached_tok": 0, "reasoning_tok": 0,
                        "latencies": [],
                    }
                cstat = cred_agg[cid]
                cstat["requests"] += 1
                if is_success: cstat["success"] += 1
                else: cstat["failure"] += 1
                if is_fallback: cstat["fallback_success"] += 1
                cstat["prompt_tok"] += in_t
                cstat["compl_tok"] += out_t
                cstat["cached_tok"] += c_t
                cstat["reasoning_tok"] += r_t
                if l.latency_ms: cstat["latencies"].append(l.latency_ms)

            # By Provider
            pid = l.resolved_provider_id or 0
            if pid:
                if pid not in prov_agg:
                    p_obj = providers.get(pid)
                    prov_agg[pid] = {
                        "id": pid,
                        "name": p_obj.name if p_obj else f"Provider #{pid}",
                        "slug": p_obj.slug if p_obj else f"prov-{pid}",
                        "requests": 0, "success": 0, "failure": 0,
                        "prompt_tok": 0, "compl_tok": 0, "cached_tok": 0, "reasoning_tok": 0,
                        "cost": 0.0, "latencies": [],
                    }
                pstat = prov_agg[pid]
                pstat["requests"] += 1
                if is_success: pstat["success"] += 1
                else: pstat["failure"] += 1
                pstat["prompt_tok"] += in_t
                pstat["compl_tok"] += out_t
                pstat["cached_tok"] += c_t
                pstat["reasoning_tok"] += r_t
                pstat["cost"] += (l.estimated_cost_usd or 0.0)
                if l.latency_ms: pstat["latencies"].append(l.latency_ms)

            # By Model
            mname = l.upstream_model or l.requested_model
            if mname:
                clean_m = mname.removeprefix("route/").removeprefix("fusion/")
                if clean_m not in model_agg:
                    p_name = providers[l.resolved_provider_id].name if l.resolved_provider_id in providers else "Router"
                    model_agg[clean_m] = {
                        "model_name": clean_m,
                        "provider_name": p_name,
                        "requests": 0, "success": 0, "failure": 0,
                        "prompt_tok": 0, "compl_tok": 0, "cached_tok": 0, "reasoning_tok": 0,
                        "cost": 0.0, "latencies": [],
                    }
                mstat = model_agg[clean_m]
                mstat["requests"] += 1
                if is_success: mstat["success"] += 1
                else: mstat["failure"] += 1
                mstat["prompt_tok"] += in_t
                mstat["compl_tok"] += out_t
                mstat["cached_tok"] += c_t
                mstat["reasoning_tok"] += r_t
                mstat["cost"] += (l.estimated_cost_usd or 0.0)
                if l.latency_ms: mstat["latencies"].append(l.latency_ms)

            # Fallback & Routing Funnel Tracking
            is_prof_req = l.mode in ("PRIORITY", "FUSION") or l.requested_model.startswith(("route/", "fusion/"))
            if is_prof_req:
                total_profile_requests += 1
                req_m = l.requested_model
                mode = "PRIORITY" if req_m.startswith("route/") or l.mode == "PRIORITY" else "FUSION"
                slug = req_m.removeprefix("route/").removeprefix("fusion/")
                if slug not in profile_agg:
                    profile_agg[slug] = {
                        "slug": slug,
                        "name": f"Route: {slug}" if mode == "PRIORITY" else f"Fusion: {slug}",
                        "mode": mode,
                        "is_active": False,
                        "candidates_count": 0,
                        "requests": 0,
                        "success": 0,
                        "first_candidate_success": 0,
                        "fallback_success": 0,
                        "key_failovers": 0,
                        "failure": 0,
                        "prompt_tok": 0,
                        "compl_tok": 0,
                        "cached_tok": 0,
                        "reasoning_tok": 0,
                        "cost": 0.0,
                        "latencies": [],
                        "candidates": [],
                    }
                prstat = profile_agg[slug]
                prstat["requests"] += 1
                if is_success:
                    prstat["success"] += 1
                else:
                    prstat["failure"] += 1

                if mode == "PRIORITY" and slug in cand_models_map:
                    cand_list = cand_models_map[slug]
                    up_m = l.upstream_model
                    matched_idx = None
                    if up_m:
                        for c_idx, (cand, m_set) in enumerate(cand_list):
                            if up_m in m_set or any(up_m == m or up_m.endswith(f"/{m}") for m in m_set):
                                matched_idx = c_idx
                                break

                    if matched_idx == 0:
                        if matched_idx < len(prstat["candidates"]):
                            prstat["candidates"][matched_idx].requests_count += 1
                        if is_success:
                            if matched_idx < len(prstat["candidates"]):
                                prstat["candidates"][matched_idx].success_count += 1
                            prstat["first_candidate_success"] += 1
                            if is_fallback:
                                prstat["key_failovers"] += 1
                    elif matched_idx is not None:
                        if matched_idx < len(prstat["candidates"]):
                            prstat["candidates"][matched_idx].requests_count += 1
                        if is_success:
                            if matched_idx < len(prstat["candidates"]):
                                prstat["candidates"][matched_idx].success_count += 1
                            prstat["fallback_success"] += 1
                    else:
                        if is_fallback:
                            prstat["fallback_success"] += 1
                        elif is_success:
                            prstat["first_candidate_success"] += 1
                else:
                    if is_fallback:
                        prstat["fallback_success"] += 1
                    elif is_success:
                        prstat["first_candidate_success"] += 1

                prstat["prompt_tok"] += in_t
                prstat["compl_tok"] += out_t
                prstat["cached_tok"] += c_t
                prstat["reasoning_tok"] += r_t
                prstat["cost"] += (l.estimated_cost_usd or 0.0)
                if l.latency_ms:
                    prstat["latencies"].append(l.latency_ms)

        # Helper for percentiles and TPS
        def calc_pcts(lats: List[float]):
            if not lats:
                return 0.0, 0.0, 0.0
            s = sorted(lats)
            n = len(s)
            p50 = s[int(n * 0.50)]
            p90 = s[min(int(n * 0.90), n - 1)]
            p99 = s[min(int(n * 0.99), n - 1)]
            return round(p50, 1), round(p90, 1), round(p99, 1)

        def calc_tps(tok_cnt: int, lats: List[float]):
            tot_sec = sum(lats) / 1000.0
            if tot_sec > 0 and tok_cnt > 0:
                return round(tok_cnt / tot_sec, 1)
            return 0.0

        # Build Status Codes
        status_codes_out = [
            StatusCodeItem(
                code=code,
                count=cnt,
                percentage=round(cnt / tot_req * 100.0, 1) if tot_req > 0 else 0.0,
            )
            for code, cnt in sorted(status_code_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Build Top Errors
        top_errors_out = [
            TopErrorItem(
                error_category=k[0],
                error_message=k[1],
                count=v["count"],
                last_seen=v["last_seen"],
            )
            for k, v in sorted(error_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
        ]

        # Calculate Fallback Funnel
        tot_key_failovers = sum(pr["key_failovers"] for pr in profile_agg.values())
        tot_fb_success = sum(pr["fallback_success"] for pr in profile_agg.values())
        tot_first_success = sum(pr["first_candidate_success"] for pr in profile_agg.values())
        tot_prof_fail = sum(pr["failure"] for pr in profile_agg.values())

        prim_direct = max(0, tot_first_success - tot_key_failovers)
        prim_key = tot_key_failovers
        fb_model = tot_fb_success
        chain_fail = tot_prof_fail

        baseline_succ = prim_direct + prim_key
        base_rate = round(baseline_succ / total_profile_requests * 100.0, 1) if total_profile_requests > 0 else 100.0
        final_succ = baseline_succ + fb_model
        final_rate = round(final_succ / total_profile_requests * 100.0, 1) if total_profile_requests > 0 else 100.0
        rel_gain = round(final_rate - base_rate, 1)

        funnel_stats = FallbackFunnelStats(
            total_profile_requests=total_profile_requests,
            primary_direct_success=prim_direct,
            primary_key_failover_success=prim_key,
            fallback_model_success=fb_model,
            chain_failures=chain_fail,
            baseline_success_rate=base_rate,
            final_success_rate=final_rate,
            reliability_gain_pct=rel_gain,
        )

        # Convert to response objects
        keys_out = []
        for kid, kstat in key_agg.items():
            req_cnt = kstat["requests"]
            succ_cnt = kstat["success"]
            p50, p90, _ = calc_pcts(kstat["latencies"])
            t_cnt = kstat["prompt_tok"] + kstat["compl_tok"]
            keys_out.append(
                KeyStatsItem(
                    id=kstat["id"],
                    name=kstat["name"],
                    prefix=kstat["prefix"],
                    requests_count=req_cnt,
                    success_count=succ_cnt,
                    failure_count=kstat["failure"],
                    success_rate=round(succ_cnt / req_cnt * 100.0, 1) if req_cnt > 0 else 100.0,
                    input_tokens=kstat["prompt_tok"],
                    output_tokens=kstat["compl_tok"],
                    cached_tokens=kstat["cached_tok"],
                    reasoning_tokens=kstat["reasoning_tok"],
                    total_tokens=t_cnt,
                    estimated_cost_usd=round(kstat["cost"], 5),
                    avg_latency_ms=round(sum(kstat["latencies"]) / len(kstat["latencies"]), 1) if kstat["latencies"] else 0.0,
                    p50_latency_ms=p50,
                    p90_latency_ms=p90,
                    tokens_per_sec=calc_tps(t_cnt, kstat["latencies"]),
                )
            )
        keys_out.sort(key=lambda x: x.requests_count, reverse=True)

        creds_out = []
        for cid, cstat in cred_agg.items():
            req_cnt = cstat["requests"]
            succ_cnt = cstat["success"]
            p50, p90, _ = calc_pcts(cstat["latencies"])
            t_cnt = cstat["prompt_tok"] + cstat["compl_tok"]
            creds_out.append(
                CredentialStatsItem(
                    id=cstat["id"],
                    name=cstat["name"],
                    provider_name=cstat["provider_name"],
                    status=cstat["status"],
                    requests_count=req_cnt,
                    success_count=succ_cnt,
                    failure_count=cstat["failure"],
                    fallback_success_count=cstat["fallback_success"],
                    success_rate=round(succ_cnt / req_cnt * 100.0, 1) if req_cnt > 0 else 100.0,
                    input_tokens=cstat["prompt_tok"],
                    output_tokens=cstat["compl_tok"],
                    cached_tokens=cstat["cached_tok"],
                    reasoning_tokens=cstat["reasoning_tok"],
                    total_tokens=t_cnt,
                    avg_latency_ms=round(sum(cstat["latencies"]) / len(cstat["latencies"]), 1) if cstat["latencies"] else 0.0,
                    p50_latency_ms=p50,
                    p90_latency_ms=p90,
                    tokens_per_sec=calc_tps(t_cnt, cstat["latencies"]),
                )
            )
        creds_out.sort(key=lambda x: x.requests_count, reverse=True)

        provs_out = []
        for pid, pstat in prov_agg.items():
            req_cnt = pstat["requests"]
            succ_cnt = pstat["success"]
            p50, p90, _ = calc_pcts(pstat["latencies"])
            t_cnt = pstat["prompt_tok"] + pstat["compl_tok"]
            provs_out.append(
                ProviderStatsItem(
                    id=pstat["id"],
                    name=pstat["name"],
                    slug=pstat["slug"],
                    requests_count=req_cnt,
                    success_count=succ_cnt,
                    failure_count=pstat["failure"],
                    success_rate=round(succ_cnt / req_cnt * 100.0, 1) if req_cnt > 0 else 100.0,
                    input_tokens=pstat["prompt_tok"],
                    output_tokens=pstat["compl_tok"],
                    cached_tokens=pstat["cached_tok"],
                    reasoning_tokens=pstat["reasoning_tok"],
                    total_tokens=t_cnt,
                    estimated_cost_usd=round(pstat["cost"], 5),
                    avg_latency_ms=round(sum(pstat["latencies"]) / len(pstat["latencies"]), 1) if pstat["latencies"] else 0.0,
                    p50_latency_ms=p50,
                    p90_latency_ms=p90,
                    tokens_per_sec=calc_tps(t_cnt, pstat["latencies"]),
                )
            )
        provs_out.sort(key=lambda x: x.requests_count, reverse=True)

        models_out = []
        for mname, mstat in model_agg.items():
            req_cnt = mstat["requests"]
            succ_cnt = mstat["success"]
            p50, p90, _ = calc_pcts(mstat["latencies"])
            t_cnt = mstat["prompt_tok"] + mstat["compl_tok"]
            models_out.append(
                ModelStatsItem(
                    model_name=mstat["model_name"],
                    provider_name=mstat["provider_name"],
                    requests_count=req_cnt,
                    success_count=succ_cnt,
                    failure_count=mstat["failure"],
                    success_rate=round(succ_cnt / req_cnt * 100.0, 1) if req_cnt > 0 else 100.0,
                    input_tokens=mstat["prompt_tok"],
                    output_tokens=mstat["compl_tok"],
                    cached_tokens=mstat["cached_tok"],
                    reasoning_tokens=mstat["reasoning_tok"],
                    total_tokens=t_cnt,
                    estimated_cost_usd=round(mstat["cost"], 5),
                    avg_latency_ms=round(sum(mstat["latencies"]) / len(mstat["latencies"]), 1) if mstat["latencies"] else 0.0,
                    p50_latency_ms=p50,
                    p90_latency_ms=p90,
                    tokens_per_sec=calc_tps(t_cnt, mstat["latencies"]),
                )
            )
        models_out.sort(key=lambda x: x.requests_count, reverse=True)

        profiles_out = []
        for pslug, prstat in profile_agg.items():
            req_cnt = prstat["requests"]
            succ_cnt = prstat["success"]
            fb_cnt = prstat["fallback_success"]
            first_succ = prstat["first_candidate_success"]
            key_failovers = prstat["key_failovers"]
            fail_cnt = prstat["failure"]
            fb_rate = round(fb_cnt / req_cnt * 100.0, 1) if req_cnt > 0 else 0.0
            p50, p90, _ = calc_pcts(prstat["latencies"])
            t_cnt = prstat["prompt_tok"] + prstat["compl_tok"]
            profiles_out.append(
                ProfileStatsItem(
                    slug=prstat["slug"],
                    name=prstat["name"],
                    mode=prstat["mode"],
                    is_active=prstat.get("is_active", True),
                    candidates_count=prstat.get("candidates_count", 0),
                    requests_count=req_cnt,
                    success_count=succ_cnt,
                    first_candidate_success_count=first_succ,
                    fallback_success_count=fb_cnt,
                    key_failover_count=key_failovers,
                    failure_count=fail_cnt,
                    fallback_rate=fb_rate,
                    input_tokens=prstat["prompt_tok"],
                    output_tokens=prstat["compl_tok"],
                    cached_tokens=prstat.get("cached_tok", 0),
                    reasoning_tokens=prstat.get("reasoning_tok", 0),
                    total_tokens=t_cnt,
                    estimated_cost_usd=round(prstat["cost"], 5),
                    avg_latency_ms=round(sum(prstat["latencies"]) / len(prstat["latencies"]), 1) if prstat["latencies"] else 0.0,
                    p50_latency_ms=p50,
                    p90_latency_ms=p90,
                    tokens_per_sec=calc_tps(t_cnt, prstat["latencies"]),
                    candidates=prstat.get("candidates", []),
                )
            )
        profiles_out.sort(key=lambda x: (x.is_active, x.requests_count > 0, x.requests_count), reverse=True)

        timeline_out = [
            TimeBucketStatsItem(
                time_label=tb["label"],
                timestamp=tb["ts"],
                requests=tb["requests"],
                errors=tb["errors"],
                fallbacks=tb["fallbacks"],
                tokens=tb["tokens"],
                cost=round(tb.get("cost", 0.0), 5),
                avg_latency_ms=round(sum(tb["latencies"]) / len(tb["latencies"]), 1) if tb.get("latencies") else 0.0,
            )
            for tb in sorted(time_agg.values(), key=lambda x: x["ts"])
        ]

        # Latency percentiles for summary
        p50_lat, p90_lat, p99_lat = calc_pcts(latencies)
        global_tps = calc_tps(tot_prompt + tot_compl, latencies)

        # Projections
        if start_dt and end_dt:
            dur_days = max((end_dt - start_dt).total_seconds() / 86400.0, 1.0 / 24.0)
        elif min_dt and now_naive:
            dur_days = max((now_naive - min_dt).total_seconds() / 86400.0, 1.0 / 24.0)
        else:
            dur_days = 1.0

        daily_rate = tot_cost / dur_days if dur_days > 0 else 0.0
        proj_daily = round(daily_rate, 4)
        proj_monthly = round(daily_rate * 30.0, 4)

        summary = SummaryStats(
            total_requests=tot_req,
            successful_requests=succ_req,
            failed_requests=fail_req,
            fallback_requests=fallback_req,
            success_rate=round(succ_req / tot_req * 100.0, 1) if tot_req > 0 else 100.0,
            total_prompt_tokens=tot_prompt,
            total_completion_tokens=tot_compl,
            total_tokens=tot_prompt + tot_compl,
            total_cached_tokens=tot_cached,
            total_reasoning_tokens=tot_reasoning,
            estimated_cost_usd=round(tot_cost, 5),
            avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            p50_latency_ms=p50_lat,
            p90_latency_ms=p90_lat,
            p99_latency_ms=p99_lat,
            tokens_per_sec=global_tps,
            cached_tokens_cost_saved_usd=round(cached_saved_usd, 4),
            projected_daily_cost_usd=proj_daily,
            projected_monthly_cost_usd=proj_monthly,
        )

        # Comparison with previous period
        comparison_out = None
        if prev_start_dt and prev_end_dt:
            prev_query = apply_query_filters(
                select(RequestLog).order_by(RequestLog.id.asc()),
                prev_start_dt,
                prev_end_dt,
                filter_type,
                filter_value,
            )
            prev_res = await db.execute(prev_query)
            prev_logs = prev_res.scalars().all()
            prev_tot_req = len(prev_logs)
            prev_succ_req = sum(1 for pl in prev_logs if pl.status in ("SUCCESS", "FALLBACK_SUCCESS", "FUSION_SUCCESS"))
            prev_tokens = sum((pl.input_tokens or 0) + (pl.output_tokens or 0) for pl in prev_logs)
            prev_cost = sum(pl.estimated_cost_usd or 0.0 for pl in prev_logs)
            prev_latencies = [pl.latency_ms for pl in prev_logs if pl.latency_ms]

            def calc_pct_change(curr, prev):
                if prev == 0:
                    return 100.0 if curr > 0 else 0.0
                return round(((curr - prev) / prev) * 100.0, 1)

            req_change = calc_pct_change(tot_req, prev_tot_req) if (prev_tot_req > 0 or tot_req > 0) else None
            curr_succ_rate = round(succ_req / tot_req * 100.0, 1) if tot_req > 0 else 100.0
            prev_succ_rate = round(prev_succ_req / prev_tot_req * 100.0, 1) if prev_tot_req > 0 else 100.0
            succ_change = round(curr_succ_rate - prev_succ_rate, 1) if prev_tot_req > 0 else None
            tok_change = calc_pct_change(tot_prompt + tot_compl, prev_tokens) if (prev_tokens > 0 or (tot_prompt + tot_compl) > 0) else None
            cost_change = calc_pct_change(tot_cost, prev_cost) if (prev_cost > 0 or tot_cost > 0) else None
            curr_avg_lat = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
            prev_avg_lat = round(sum(prev_latencies) / len(prev_latencies), 1) if prev_latencies else 0.0
            lat_change = calc_pct_change(curr_avg_lat, prev_avg_lat) if prev_latencies else None

            comparison_out = SummaryComparison(
                requests_change_pct=req_change,
                success_rate_change_pct=succ_change,
                tokens_change_pct=tok_change,
                cost_change_pct=cost_change,
                latency_change_pct=lat_change,
            )

        return DetailedAnalyticsResponse(
            period=eff_period,
            start_date=start_dt.isoformat() if start_dt else None,
            end_date=end_dt.isoformat() if end_dt else None,
            granularity=eff_granularity,
            filter_type=filter_type,
            filter_value=filter_value,
            summary=summary,
            comparison=comparison_out,
            fallback_funnel=funnel_stats,
            status_codes=status_codes_out,
            top_errors=top_errors_out,
            timeline=timeline_out,
            by_router_keys=keys_out,
            by_credentials=creds_out,
            by_providers=provs_out,
            by_models=models_out,
            by_profiles=profiles_out,
        )
