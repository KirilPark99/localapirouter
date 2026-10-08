import re
from datetime import datetime, timezone
from ipaddress import ip_network
from typing import Any, Dict, List, Literal, Optional, Annotated
from pydantic import BaseModel, Field, field_validator, AfterValidator

def _validate_log_date(value: str) -> str:
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value

LogDateFilter = Annotated[str, AfterValidator(_validate_log_date)]
IPAddressRange = Annotated[str, AfterValidator(lambda value: str(ip_network(value, strict=False)))]

# Auth
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AdminUserRead(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: datetime

# Proxy
class ProxyBase(BaseModel):
    name: str
    scheme: Literal["http", "https", "socks5", "socks5h"] = "http"
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: bool = True
    country: Optional[str] = None
    country_code: Optional[str] = None

class ProxyCreate(ProxyBase):
    pass

class ProxyUpdate(BaseModel):
    name: Optional[str] = None
    scheme: Optional[Literal["http", "https", "socks5", "socks5h"]] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: Optional[bool] = None
    country: Optional[str] = None
    country_code: Optional[str] = None

class ProxyRead(BaseModel):
    id: int
    name: str
    scheme: str
    host: str
    port: int
    has_auth: bool
    enabled: bool
    status: str
    country: Optional[str] = None
    country_code: Optional[str] = None
    assigned_providers: List[str] = []
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime

class ProxyTestResult(BaseModel):
    success: bool
    latency_ms: float
    message: str
    ip: Optional[str] = None
    server_ip: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    details: Optional[str] = None

class ProxyParseRequest(BaseModel):
    raw: str

class ProxyParseResult(BaseModel):
    scheme: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    suggested_name: Optional[str] = None

# Provider
class ProviderBase(BaseModel):
    name: str
    slug: str
    adapter_type: str
    base_url: str
    models_endpoint: str = "/models"
    chat_endpoint: str = "/chat/completions"
    responses_endpoint: Optional[str] = None
    enabled: bool = True
    auth_type: Literal["bearer", "x-api-key", "custom_header", "query_param", "none"] = "bearer"
    auth_header: str = "Authorization"
    extra_headers: Dict[str, Any] = Field(default_factory=dict)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

class ProviderCreate(ProviderBase):
    pass

class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    adapter_type: Optional[str] = None
    base_url: Optional[str] = None
    models_endpoint: Optional[str] = None
    chat_endpoint: Optional[str] = None
    responses_endpoint: Optional[str] = None
    enabled: Optional[bool] = None
    auth_type: Optional[Literal["bearer", "x-api-key", "custom_header", "query_param", "none"]] = None
    auth_header: Optional[str] = None
    extra_headers: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class NotesUpdate(BaseModel):
    notes: Optional[str] = None

class ProviderRead(ProviderBase):
    id: int
    credentials_count: int = 0
    models_count: int = 0
    healthy_credentials_count: int = 0
    created_at: datetime
    updated_at: datetime

# Router API Key
from pydantic import model_validator

class PeriodQuotaRule(BaseModel):
    model_config = {"extra": "forbid"}
    id: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    enabled: bool = Field(default=True, strict=True)
    scope: Literal["key", "model", "profile"] = "key"
    model: Optional[str] = Field(default=None, min_length=3, max_length=200, pattern=r"^[^\s*/]+/[^\s*]+$")
    period: Literal["minute", "hour", "day", "week", "month", "custom", "interval"] = "day"
    duration_seconds: Optional[int] = Field(default=None, strict=True, ge=1, le=315360000)
    anchor: Optional[datetime] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    requests: Optional[int] = Field(default=None, strict=True, gt=0, le=2147483647)
    tokens: Optional[int] = Field(default=None, strict=True, gt=0, le=9007199254740991)
    usd: Optional[float] = Field(default=None, strict=True, gt=0, le=1e12, allow_inf_nan=False)

    @field_validator("anchor", "start", "end", mode="before")
    @classmethod
    def aware_date(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Quota dates must be ISO timestamps with a timezone")
        try:
            return value.astimezone(timezone.utc)
        except OverflowError as exc:
            raise ValueError("Quota date is outside the supported UTC range") from exc

    @model_validator(mode="after")
    def valid_rule(self):
        if not any(v is not None for v in (self.requests, self.tokens, self.usd)):
            raise ValueError("Provide at least one quota limit")
        if self.scope == "key" and self.model is not None or self.scope != "key" and self.model is None:
            raise ValueError("Model/profile scope requires an exact name; key scope has no model")
        virtual = self.model and self.model.startswith(("route/", "fusion/", "judge/", "smart/"))
        if self.scope == "profile" and not virtual or self.scope == "model" and virtual:
            raise ValueError("Use profile scope for requested virtual profiles, model scope for canonical upstream models")
        if self.model and self.model.startswith("smart/"):
            self.model = "judge/" + self.model[6:]
        if self.period == "custom":
            if self.duration_seconds is None or self.anchor is None:
                raise ValueError("Custom period requires duration_seconds and a stable UTC anchor")
        elif self.duration_seconds is not None or self.anchor is not None:
            raise ValueError("Duration and anchor are only valid for custom periods")
        if self.period == "interval":
            if self.start is None or self.end is None or self.start >= self.end:
                raise ValueError("Interval requires aware start < end")
        elif self.start is not None or self.end is not None:
            raise ValueError("Start/end are only valid for intervals")
        return self


def _quota_rules_unique(rules):
    if rules is None:
        return rules
    ids = [r.id for r in rules if r.id]
    identities = [(r.scope, r.model, r.period, r.duration_seconds, r.anchor, r.start, r.end) for r in rules]
    if len(ids) != len(set(ids)) or len(identities) != len(set(identities)):
        raise ValueError("Duplicate quota rule IDs or scope/window")
    return rules

QuotaRules = Annotated[List[PeriodQuotaRule], Field(max_length=64), AfterValidator(_quota_rules_unique)]

def _credential_quota_rules(rules):
    if rules and any(r.scope == "profile" for r in rules):
        raise ValueError("Provider credential quotas support key and canonical model scopes only")
    return rules

CredentialQuotaRules = Annotated[QuotaRules, AfterValidator(_credential_quota_rules)]

# Credential
class CredentialCreate(BaseModel):
    quota_rules: CredentialQuotaRules = Field(default_factory=list)
    provider_id: int
    name: str
    api_key: str
    group_name: Optional[str] = None
    proxy_id: Optional[int] = None
    priority: int = 1
    weight: int = 1
    rpm_limit: Optional[int] = Field(default=None, ge=1)
    tpm_limit: Optional[int] = Field(default=None, ge=1)
    max_concurrency: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = None

class CredentialUpdate(BaseModel):
    quota_rules: Optional[CredentialQuotaRules] = None
    name: Optional[str] = None
    api_key: Optional[str] = None
    group_name: Optional[str] = None
    proxy_id: Optional[int] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    weight: Optional[int] = None
    rpm_limit: Optional[int] = Field(default=None, ge=1)
    tpm_limit: Optional[int] = Field(default=None, ge=1)
    max_concurrency: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = None

class CredentialBulkAssignProxy(BaseModel):
    credential_ids: List[int]
    proxy_id: Optional[int] = None

class CredentialBulkAssignGroup(BaseModel):
    credential_ids: List[int]
    group_name: Optional[str] = None

class CredentialRead(BaseModel):
    quota_rules: List[PeriodQuotaRule] = Field(default_factory=list)
    id: int
    provider_id: int
    provider_name: str
    name: str
    group_name: Optional[str] = None
    masked_key: str
    key_fingerprint: str
    enabled: bool
    proxy_id: Optional[int] = None
    proxy_name: Optional[str] = None
    status: str
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int
    cooldown_until: Optional[datetime] = None
    model_cooldowns: Optional[Dict[str, int]] = None
    priority: int
    weight: int
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    max_concurrency: Optional[int] = None
    discovered_models_count: int = 0
    notes: Optional[str] = None
    created_at: datetime

class CredentialTestResult(BaseModel):
    success: bool
    latency_ms: float
    message: str
    models_found: int = 0
    error_category: Optional[str] = None

# Models
class ModelRatingInfo(BaseModel):
    intelligence_index: Optional[float] = None
    coding_index: Optional[float] = None
    agentic_index: Optional[float] = None
    speed_tokens_per_sec: Optional[float] = None
    is_reasoning: Optional[bool] = False
    eval_provider: str = "Artificial Analysis"
    source_url: Optional[str] = None
    model_creator: Optional[str] = None
    aa_name: Optional[str] = None
    aa_slug: Optional[str] = None

class ModelLimitsRead(BaseModel):
    model_id: int
    provider_model_id: str
    canonical_slug: str
    provider_slug: str
    context_length: Optional[int] = None
    max_output_tokens: Optional[int] = None
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    rate_limit_rpd: Optional[int] = None
    remaining_requests: Optional[int] = None
    remaining_tokens: Optional[int] = None
    reset_requests: Optional[str] = None
    reset_tokens: Optional[str] = None
    account_usage: Optional[float] = None
    account_limit: Optional[float] = None
    is_free_tier: Optional[bool] = None
    source: str = "direct_api"
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_details: Optional[Dict[str, Any]] = None


class DiscoveredModelRead(BaseModel):
    id: int
    provider_id: int
    provider_name: str
    credential_id: Optional[int] = None
    credential_name: Optional[str] = None
    provider_model_id: str
    display_name: str
    canonical_slug: str
    capabilities: Dict[str, Any]
    supported_endpoints: List[str]
    context_length: Optional[int] = None
    max_output_tokens: Optional[int] = None
    input_price_per_1m: Optional[float] = 0.0
    output_price_per_1m: Optional[float] = 0.0
    enabled: bool
    available: bool
    is_visible: bool = True
    reasoning_effort: Optional[str] = None
    temperature: Optional[float] = None
    model_type: str = "openai"
    discovered_at: datetime
    created_at: Optional[datetime] = None
    rating: Optional[ModelRatingInfo] = None
    limits: Optional[ModelLimitsRead] = None


class DiscoveredModelUpdate(BaseModel):
    enabled: Optional[bool] = None
    is_visible: Optional[bool] = None
    display_name: Optional[str] = None
    model_type: Optional[str] = None
    input_price_per_1m: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    output_price_per_1m: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    context_length: Optional[int] = None
    reasoning_effort: Optional[str] = None
    temperature: Optional[float] = None

    @field_validator("temperature")
    @classmethod
    def validate_temperature_range(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

    @field_validator("reasoning_effort")
    @classmethod
    def validate_reasoning_effort_no_digits(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        if not v or v.lower() in ("default", "reset", "clear", "none_default"):
            return None
        return v.lower()

class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "myairouter"
    permission: List[Any] = Field(default_factory=list)
    root: Optional[str] = None
    parent: Optional[str] = None
    context_length: Optional[int] = None
    max_tokens: Optional[int] = None
    reasoning_effort: Optional[str] = None
    temperature: Optional[float] = None
    model_type: Optional[str] = "openai"

class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelCard]

# Routing
class RoutingCandidateInput(BaseModel):
    candidate_type: Literal["model", "profile"] = "model"
    target_profile_id: Optional[int] = None
    provider_id: Optional[int] = None
    credential_id: Optional[int] = None
    credential_group: Optional[str] = None
    model_id: Optional[int] = None
    thinking_effort: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    priority_order: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class RoutingCandidateRead(BaseModel):
    id: int
    candidate_type: Literal["model", "profile"] = "model"
    target_profile_id: Optional[int] = None
    target_profile_name: Optional[str] = None
    target_profile_slug: Optional[str] = None
    provider_id: Optional[int] = None
    provider_name: Optional[str] = None
    credential_id: Optional[int] = None
    credential_name: Optional[str] = None
    credential_group: Optional[str] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    canonical_slug: Optional[str] = None
    thinking_effort: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    priority_order: int
    is_active: bool

class RoutingProfileCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    strategy: Literal["priority", "cache-optimized", "round_robin", "least_latency"] = "priority"
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    fallback_conditions: List[str] = Field(default_factory=lambda: ["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"])
    thinking_effort: Optional[str] = None
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    randomize_candidates: bool = False
    randomize_keys: bool = True
    enabled: bool = True
    candidates: List[RoutingCandidateInput] = Field(default_factory=list)

    @field_validator("temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class RoutingProfileUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    strategy: Optional[Literal["priority", "cache-optimized", "round_robin", "least_latency"]] = None
    retry_count: Optional[int] = Field(default=None, ge=0, le=10)
    timeout_seconds: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    fallback_conditions: Optional[List[str]] = None
    thinking_effort: Optional[str] = None
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    randomize_candidates: Optional[bool] = None
    randomize_keys: Optional[bool] = None
    enabled: Optional[bool] = None
    candidates: Optional[List[RoutingCandidateInput]] = None

    @field_validator("temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class RoutingProfileRead(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    strategy: str
    retry_count: int
    timeout_seconds: float
    fallback_conditions: List[str]
    thinking_effort: Optional[str] = None
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    randomize_candidates: bool = False
    randomize_keys: bool = True
    enabled: bool
    candidates: List[RoutingCandidateRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

# Fusion
class FusionParticipantInput(BaseModel):
    participant_type: Literal["model", "profile"] = "model"
    target_profile_id: Optional[int] = None
    provider_id: Optional[int] = None
    credential_id: Optional[int] = None
    credential_group: Optional[str] = None
    model_id: Optional[int] = None
    thinking_effort: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    priority_order: int = Field(default=0, ge=0)
    label: str = "Candidate"
    is_active: bool = True

    @field_validator("temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class FusionParticipantRead(BaseModel):
    id: int
    participant_type: str = "model"
    target_profile_id: Optional[int] = None
    target_profile_name: Optional[str] = None
    target_profile_slug: Optional[str] = None
    provider_id: Optional[int] = None
    provider_name: Optional[str] = None
    credential_id: Optional[int] = None
    credential_name: Optional[str] = None
    credential_group: Optional[str] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    canonical_slug: Optional[str] = None
    thinking_effort: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    priority_order: int = Field(default=0, ge=0)
    label: str
    is_active: bool

class FusionProfileCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    strategy: Literal["synthesize", "best_of_n", "consensus", "critique_and_rewrite"] = "synthesize"
    judge_type: Literal["model", "profile"] = "model"
    judge_routing_profile_id: Optional[int] = None
    judge_provider_id: Optional[int] = None
    judge_credential_id: Optional[int] = None
    judge_credential_group: Optional[str] = None
    judge_model_id: Optional[int] = None
    judge_thinking_effort: Optional[str] = None
    judge_temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    system_prompt: Optional[str] = None
    min_successful_candidates: int = Field(default=2, gt=0, allow_inf_nan=False)
    max_parallelism: int = Field(default=5, gt=0, allow_inf_nan=False)
    timeout_seconds: float = Field(default=120.0, gt=0, allow_inf_nan=False)
    enabled: bool = True
    participants: List[FusionParticipantInput] = Field(default_factory=list)

    @field_validator("judge_temperature", "temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class FusionProfileUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    strategy: Optional[Literal["synthesize", "best_of_n", "consensus", "critique_and_rewrite"]] = None
    judge_type: Optional[Literal["model", "profile"]] = None
    judge_routing_profile_id: Optional[int] = None
    judge_provider_id: Optional[int] = None
    judge_credential_id: Optional[int] = None
    judge_credential_group: Optional[str] = None
    judge_model_id: Optional[int] = None
    judge_thinking_effort: Optional[str] = None
    judge_temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    system_prompt: Optional[str] = None
    min_successful_candidates: Optional[int] = Field(default=None, gt=0, allow_inf_nan=False)
    max_parallelism: Optional[int] = Field(default=None, gt=0, allow_inf_nan=False)
    timeout_seconds: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    enabled: Optional[bool] = None
    participants: Optional[List[FusionParticipantInput]] = None

    @field_validator("judge_temperature", "temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class FusionProfileRead(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    strategy: str
    judge_type: str = "model"
    judge_routing_profile_id: Optional[int] = None
    judge_routing_profile_name: Optional[str] = None
    judge_routing_profile_slug: Optional[str] = None
    judge_provider_id: Optional[int] = None
    judge_provider_name: Optional[str] = None
    judge_credential_id: Optional[int] = None
    judge_credential_name: Optional[str] = None
    judge_credential_group: Optional[str] = None
    judge_model_id: Optional[int] = None
    judge_model_name: Optional[str] = None
    judge_thinking_effort: Optional[str] = None
    judge_temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    system_prompt: Optional[str] = None
    min_successful_candidates: int
    max_parallelism: int
    timeout_seconds: float
    enabled: bool
    participants: List[FusionParticipantRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

# Judge Routing
class JudgeCandidateInput(BaseModel):
    candidate_type: Literal["model", "profile"] = "model"
    target_profile_id: Optional[int] = None
    provider_id: Optional[int] = None
    credential_id: Optional[int] = None
    credential_group: Optional[str] = None
    model_id: Optional[int] = None
    thinking_effort: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    priority_order: int = Field(default=0, ge=0)
    label: str = "Candidate"
    task_types: List[str] = Field(default_factory=list)
    complexity_level: str = "all"
    description: Optional[str] = None
    is_active: bool = True

    @field_validator("temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class JudgeCandidateRead(BaseModel):
    id: int
    candidate_type: str = "model"
    target_profile_id: Optional[int] = None
    target_profile_name: Optional[str] = None
    target_profile_slug: Optional[str] = None
    provider_id: Optional[int] = None
    provider_name: Optional[str] = None
    credential_id: Optional[int] = None
    credential_name: Optional[str] = None
    credential_group: Optional[str] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    canonical_slug: Optional[str] = None
    thinking_effort: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    priority_order: int = Field(default=0, ge=0)
    label: str
    task_types: List[str] = Field(default_factory=list)
    complexity_level: str = "all"
    description: Optional[str] = None
    is_active: bool

class JudgeProfileCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    strategy: Literal["auto", "complexity", "task_type"] = "auto"
    judge_type: Literal["model", "profile"] = "model"
    judge_routing_profile_id: Optional[int] = None
    judge_provider_id: Optional[int] = None
    judge_credential_id: Optional[int] = None
    judge_credential_group: Optional[str] = None
    judge_model_id: Optional[int] = None
    judge_thinking_effort: Optional[str] = None
    judge_temperature: Optional[float] = Field(default=0.1, ge=0, le=2, allow_inf_nan=False)
    system_prompt: Optional[str] = None
    fallback_candidate_id: Optional[int] = None
    fallback_strongest_on_overflow: bool = False
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    timeout_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    enabled: bool = True
    candidates: List[JudgeCandidateInput] = Field(default_factory=list)

    @field_validator("judge_temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class JudgeProfileUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    strategy: Optional[Literal["auto", "complexity", "task_type"]] = None
    judge_type: Optional[Literal["model", "profile"]] = None
    judge_routing_profile_id: Optional[int] = None
    judge_provider_id: Optional[int] = None
    judge_credential_id: Optional[int] = None
    judge_credential_group: Optional[str] = None
    judge_model_id: Optional[int] = None
    judge_thinking_effort: Optional[str] = None
    judge_temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    system_prompt: Optional[str] = None
    fallback_candidate_id: Optional[int] = None
    fallback_strongest_on_overflow: Optional[bool] = None
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    timeout_seconds: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    enabled: Optional[bool] = None
    candidates: Optional[List[JudgeCandidateInput]] = None

    @field_validator("judge_temperature")
    @classmethod
    def validate_temp(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return round(float(v), 3)

class JudgeProfileRead(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    strategy: str
    judge_type: str
    judge_routing_profile_id: Optional[int] = None
    judge_routing_profile_name: Optional[str] = None
    judge_routing_profile_slug: Optional[str] = None
    judge_provider_id: Optional[int] = None
    judge_provider_name: Optional[str] = None
    judge_credential_id: Optional[int] = None
    judge_credential_name: Optional[str] = None
    judge_credential_group: Optional[str] = None
    judge_model_id: Optional[int] = None
    judge_model_name: Optional[str] = None
    judge_canonical_slug: Optional[str] = None
    judge_model_type: Optional[str] = None
    judge_thinking_effort: Optional[str] = None
    judge_temperature: Optional[float] = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    system_prompt: Optional[str] = None
    fallback_candidate_id: Optional[int] = None
    fallback_strongest_on_overflow: bool = False
    context_length: Optional[int] = Field(default=None, ge=0, allow_inf_nan=False)
    timeout_seconds: float
    enabled: bool
    candidates: List[JudgeCandidateRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

class JudgeTestRequest(BaseModel):
    prompt: str = Field(..., description="Prompt or query to be evaluated by the judge")

class JudgeTestResponse(BaseModel):
    selected_candidate_id: Optional[int] = None
    selected_candidate_label: str
    selected_target: str
    strategy: str
    estimated_complexity: str
    detected_task_type: Optional[str] = None
    judge_reasoning: str
    judge_model_name: str
    latency_ms: float
    status: str
    error: Optional[str] = None

# Router API Key
class RouterApiKeyCreate(BaseModel):
    name: str
    quota_rules: QuotaRules = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=lambda: ["direct", "routes", "fusion", "judge"])
    allowed_models: List[str] = Field(default_factory=lambda: ["*"])
    allowed_routes: List[str] = Field(default_factory=lambda: ["*"])
    allowed_fusions: List[str] = Field(default_factory=lambda: ["*"])
    allowed_judges: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_rpm: Optional[int] = Field(default=None, ge=0)
    rate_limit_tpm: Optional[int] = Field(default=None, ge=0)
    request_limit: Optional[int] = Field(default=None, ge=0)
    expiration_date: Optional[datetime] = None
    ip_restrictions: List[IPAddressRange] = Field(default_factory=list)
    notes: Optional[str] = None

class RouterApiKeyUpdate(BaseModel):
    quota_rules: Optional[QuotaRules] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None
    permissions: Optional[List[str]] = None
    allowed_models: Optional[List[str]] = None
    allowed_routes: Optional[List[str]] = None
    allowed_fusions: Optional[List[str]] = None
    allowed_judges: Optional[List[str]] = None
    rate_limit_rpm: Optional[int] = Field(default=None, ge=0)
    rate_limit_tpm: Optional[int] = Field(default=None, ge=0)
    request_limit: Optional[int] = Field(default=None, ge=0)
    expiration_date: Optional[datetime] = None
    ip_restrictions: Optional[List[IPAddressRange]] = None
    notes: Optional[str] = None

class RouterApiKeyRead(BaseModel):
    quota_rules: List[PeriodQuotaRule] = Field(default_factory=list)
    id: int
    name: str
    key_prefix: str
    masked_key: str
    enabled: bool
    permissions: List[str]
    allowed_models: List[str]
    allowed_routes: List[str]
    allowed_fusions: List[str]
    allowed_judges: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    request_limit: Optional[int] = None
    total_requests: int
    expiration_date: Optional[datetime] = None
    ip_restrictions: List[str]
    notes: Optional[str] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime

class RouterApiKeyCreated(RouterApiKeyRead):
    raw_api_key: str  # Shown ONLY once on creation!

# Logs
class RequestAttemptRead(BaseModel):
    id: int
    attempt_number: int
    provider_name: str
    credential_name: str
    model_name: str
    status: str
    http_status: Optional[int] = None
    error_category: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: float

class RequestLogRead(BaseModel):
    id: int
    request_id: str
    router_key_id: Optional[int] = None
    router_key_name: Optional[str] = None
    requested_model: str
    mode: str
    resolved_provider_name: Optional[str] = None
    resolved_credential_name: Optional[str] = None
    upstream_model: Optional[str] = None
    latency_ms: float
    status_code: int
    status: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    estimated_cost_usd: float
    error_category: Optional[str] = None
    error_message: Optional[str] = None
    prompt_content: Optional[str] = None
    response_content: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    attempts: List[RequestAttemptRead] = Field(default_factory=list)

class LogsSummaryResponse(BaseModel):
    total_requests: int
    total_errors: int
    error_rate: float
    avg_latency_ms: float
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cached_tokens: int
    total_reasoning_tokens: int
    total_cost_usd: float
    total_fallback_rescued: int

# Dashboard Stats
class DashboardStats(BaseModel):
    total_providers: int
    total_credentials: int
    healthy_credentials: int
    total_models: int
    total_routes: int
    total_fusions: int
    total_judges: int = 0
    requests_24h: int
    fallbacks_24h: int = 0
    success_rate_24h: float
    avg_latency_24h: float
    total_tokens_24h: int
    estimated_cost_24h: float

# Detailed Analytics Schemas
class StatusCodeItem(BaseModel):
    code: int
    count: int
    percentage: float

class TopErrorItem(BaseModel):
    error_message: str
    error_category: str
    count: int
    last_seen: Optional[str] = None

class FallbackFunnelStats(BaseModel):
    total_profile_requests: int = 0
    primary_direct_success: int = 0
    primary_key_failover_success: int = 0
    fallback_model_success: int = 0
    chain_failures: int = 0
    baseline_success_rate: float = 0.0
    final_success_rate: float = 0.0
    reliability_gain_pct: float = 0.0

class SummaryComparison(BaseModel):
    requests_change_pct: Optional[float] = None
    success_rate_change_pct: Optional[float] = None
    tokens_change_pct: Optional[float] = None
    cost_change_pct: Optional[float] = None
    latency_change_pct: Optional[float] = None

class KeyStatsItem(BaseModel):
    id: Optional[int] = None
    name: str
    prefix: str
    requests_count: int
    success_count: int
    failure_count: int
    success_rate: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: float
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    tokens_per_sec: float = 0.0

class CredentialStatsItem(BaseModel):
    id: Optional[int] = None
    name: str
    provider_name: str
    status: str
    requests_count: int
    success_count: int
    failure_count: int
    fallback_success_count: int
    success_rate: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int
    avg_latency_ms: float
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    tokens_per_sec: float = 0.0

class ProviderStatsItem(BaseModel):
    id: Optional[int] = None
    name: str
    slug: str
    requests_count: int
    success_count: int
    failure_count: int
    success_rate: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: float
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    tokens_per_sec: float = 0.0

class ModelStatsItem(BaseModel):
    model_name: str
    provider_name: str
    requests_count: int
    success_count: int
    failure_count: int
    success_rate: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: float
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    tokens_per_sec: float = 0.0

class ProfileCandidateStat(BaseModel):
    priority_order: int
    name: str
    model_id: Optional[str] = None
    candidate_type: str = "model"
    requests_count: int = 0
    success_count: int = 0

class ProfileStatsItem(BaseModel):
    slug: str
    name: str
    mode: str
    is_active: bool = True
    candidates_count: int = 0
    requests_count: int
    success_count: int
    first_candidate_success_count: int = 0
    fallback_success_count: int = 0
    key_failover_count: int = 0
    failure_count: int
    fallback_rate: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: float
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    tokens_per_sec: float = 0.0
    candidates: List[ProfileCandidateStat] = Field(default_factory=list)

class SummaryStats(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    fallback_requests: int
    success_rate: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cached_tokens: int
    total_reasoning_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: float
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    tokens_per_sec: float = 0.0
    cached_tokens_cost_saved_usd: Optional[float] = None
    projected_daily_cost_usd: float = 0.0
    projected_monthly_cost_usd: float = 0.0

class TimeBucketStatsItem(BaseModel):
    time_label: str
    timestamp: str
    requests: int
    errors: int
    fallbacks: int
    tokens: int
    cost: float = 0.0
    avg_latency_ms: float = 0.0

class DetailedAnalyticsResponse(BaseModel):
    period: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    granularity: str = "hour"
    filter_type: Optional[str] = None
    filter_value: Optional[str] = None
    summary: SummaryStats
    comparison: Optional[SummaryComparison] = None
    fallback_funnel: Optional[FallbackFunnelStats] = None
    status_codes: List[StatusCodeItem] = Field(default_factory=list)
    top_errors: List[TopErrorItem] = Field(default_factory=list)
    timeline: List[TimeBucketStatsItem]
    by_router_keys: List[KeyStatsItem]
    by_credentials: List[CredentialStatsItem]
    by_providers: List[ProviderStatsItem]
    by_models: List[ModelStatsItem]
    by_profiles: List[ProfileStatsItem]
