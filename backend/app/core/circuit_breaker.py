from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from app.core.errors import ErrorCategory
import asyncio

class CredentialStatus:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    COOLDOWN = "COOLDOWN"
    INVALID = "INVALID"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, default_cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.default_cooldown_seconds = default_cooldown_seconds
        self._consecutive_failures: Dict[int, int] = {}
        self._cooldown_until: Dict[int, datetime] = {}
        self._model_cooldown_until: Dict[Tuple[int, str], datetime] = {}
        self._model_last_errors: Dict[Tuple[int, str], str] = {}
        self._statuses: Dict[int, str] = {}
        self._last_errors: Dict[int, str] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _normalize_model_keys(model_id: str) -> List[str]:
        clean = model_id.strip().lower()
        keys = [clean]
        if "/" in clean:
            short = clean.split("/")[-1]
            if short and short not in keys:
                keys.append(short)
        return keys

    @staticmethod
    def _is_account_wide_quota_exhaustion(error_message: str) -> bool:
        if not error_message:
            return False
        lower_err = error_message.lower()
        return any(kw in lower_err for kw in (
            "insufficient_quota",
            "check your plan and billing",
            "billing details",
            "credit balance is too low",
            "organization has been disabled",
            "account deactivated",
            "account has been suspended",
            "account is suspended",
            "usage limit reached for this organization",
            "monthly organization quota",
        ))

    def is_available(self, cred_id: int, model_id: Optional[str] = None) -> Tuple[bool, str]:
        """Check if credential is available for routing requests (and optionally for a specific model)."""
        status = self._statuses.get(cred_id, CredentialStatus.HEALTHY)
        if status == CredentialStatus.DISABLED:
            return False, "Credential is disabled"
        if status == CredentialStatus.INVALID:
            return False, "Credential has authentication/authorization error"

        now = datetime.now(timezone.utc)
        cooldown = self._cooldown_until.get(cred_id)
        if cooldown and now < cooldown:
            remaining = int((cooldown - now).total_seconds())
            return False, f"Credential is in cooldown for {remaining}s ({status})"

        # Cooldown expired -> recover to healthy/degraded
        if cooldown and now >= cooldown:
            if status in (CredentialStatus.COOLDOWN, CredentialStatus.RATE_LIMITED):
                self._statuses[cred_id] = CredentialStatus.DEGRADED
                self._cooldown_until.pop(cred_id, None)

        # Check model-specific rate limit cooldown if model_id provided
        if model_id:
            for m in self._normalize_model_keys(model_id):
                m_cooldown = self._model_cooldown_until.get((cred_id, m))
                if m_cooldown and now < m_cooldown:
                    remaining = int((m_cooldown - now).total_seconds())
                    return False, f"Model '{model_id}' is in cooldown for {remaining}s (RATE_LIMITED)"
                elif m_cooldown and now >= m_cooldown:
                    self._model_cooldown_until.pop((cred_id, m), None)
                    self._model_last_errors.pop((cred_id, m), None)

        return True, "OK"

    def record_success(self, cred_id: int, model_id: Optional[str] = None):
        """Record successful request through this credential."""
        self._consecutive_failures[cred_id] = 0
        if self._statuses.get(cred_id) in (CredentialStatus.DEGRADED, CredentialStatus.RATE_LIMITED, CredentialStatus.COOLDOWN):
            self._statuses[cred_id] = CredentialStatus.HEALTHY
        self._cooldown_until.pop(cred_id, None)
        self._last_errors.pop(cred_id, None)
        if model_id:
            for m in self._normalize_model_keys(model_id):
                self._model_cooldown_until.pop((cred_id, m), None)
                self._model_last_errors.pop((cred_id, m), None)

    def record_failure(
        self,
        cred_id: int,
        category: ErrorCategory,
        retry_after: Optional[float] = None,
        error_message: str = "",
        model_id: Optional[str] = None,
    ):
        """Record failure and trip circuit breaker or cooldown if appropriate."""
        now = datetime.now(timezone.utc)
        self._last_errors[cred_id] = error_message or (category.value if hasattr(category, "value") else str(category))

        if category == ErrorCategory.AUTH_ERROR:
            self._statuses[cred_id] = CredentialStatus.INVALID
            self._consecutive_failures[cred_id] = self._consecutive_failures.get(cred_id, 0) + 1
            return

        if category == ErrorCategory.RATE_LIMIT:
            duration = retry_after if retry_after and retry_after > 0 else self.default_cooldown_seconds
            
            # If no model is specified, or error message explicitly indicates account-wide billing/organization quota exhaustion:
            if not model_id or self._is_account_wide_quota_exhaustion(error_message):
                self._statuses[cred_id] = CredentialStatus.RATE_LIMITED
                self._cooldown_until[cred_id] = now + timedelta(seconds=duration)
                self._consecutive_failures[cred_id] = self._consecutive_failures.get(cred_id, 0) + 1
                return

            # Otherwise, rate limit is isolated to the specific model:
            self._consecutive_failures[cred_id] = self._consecutive_failures.get(cred_id, 0) + 1
            for m in self._normalize_model_keys(model_id):
                self._model_cooldown_until[(cred_id, m)] = now + timedelta(seconds=duration)
                self._model_last_errors[(cred_id, m)] = error_message
            return

        if category.is_retryable:
            fails = self._consecutive_failures.get(cred_id, 0) + 1
            self._consecutive_failures[cred_id] = fails
            if fails >= self.failure_threshold:
                self._statuses[cred_id] = CredentialStatus.COOLDOWN
                self._cooldown_until[cred_id] = now + timedelta(seconds=self.default_cooldown_seconds)
            else:
                self._statuses[cred_id] = CredentialStatus.DEGRADED

    def reset(self, cred_id: int):
        """Manually clear circuit breaker and restore state."""
        self._consecutive_failures[cred_id] = 0
        self._statuses[cred_id] = CredentialStatus.HEALTHY
        self._cooldown_until.pop(cred_id, None)
        self._last_errors.pop(cred_id, None)
        keys_to_del = [k for k in self._model_cooldown_until if k[0] == cred_id]
        for k in keys_to_del:
            self._model_cooldown_until.pop(k, None)
            self._model_last_errors.pop(k, None)

    def get_status(self, cred_id: int, model_id: Optional[str] = None) -> dict:
        now = datetime.now(timezone.utc)
        cooldown = self._cooldown_until.get(cred_id)
        cooldown_remaining = max(0, int((cooldown - now).total_seconds())) if cooldown and now < cooldown else 0

        model_cooldowns = {}
        for (c_id, m_id), m_cool in list(self._model_cooldown_until.items()):
            if c_id == cred_id:
                if now < m_cool:
                    model_cooldowns[m_id] = int((m_cool - now).total_seconds())
                else:
                    self._model_cooldown_until.pop((c_id, m_id), None)
                    self._model_last_errors.pop((c_id, m_id), None)

        status = self._statuses.get(cred_id, CredentialStatus.HEALTHY)
        if model_id:
            for m in self._normalize_model_keys(model_id):
                if m in model_cooldowns:
                    cooldown_remaining = model_cooldowns[m]
                    if status == CredentialStatus.HEALTHY:
                        status = CredentialStatus.RATE_LIMITED
                    break
        elif model_cooldowns and status == CredentialStatus.HEALTHY:
            status = CredentialStatus.DEGRADED

        return {
            "status": status,
            "consecutive_failures": self._consecutive_failures.get(cred_id, 0),
            "cooldown_remaining_seconds": cooldown_remaining,
            "cooldown_until": cooldown if (cooldown and now < cooldown) else None,
            "last_error": self._last_errors.get(cred_id, None),
            "model_cooldowns": model_cooldowns,
        }

circuit_breaker = CircuitBreaker()
