import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

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

class ProviderRead(ProviderBase):
    id: int
    credentials_count: int = 0
    models_count: int = 0
    healthy_credentials_count: int = 0
    created_at: datetime
    updated_at: datetime

# Credential
class CredentialCreate(BaseModel):
    provider_id: int
    name: str
    api_key: str
    group_name: Optional[str] = None
    proxy_id: Optional[int] = None
    priority: int = 1
    weight: int = 1
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    max_concurrency: Optional[int] = None

class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    group_name: Optional[str] = None
    proxy_id: Optional[int] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    weight: Optional[int] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    max_concurrency: Optional[int] = None

class CredentialBulkAssignProxy(BaseModel):
    credential_ids: List[int]
    proxy_id: Optional[int] = None

class CredentialBulkAssignGroup(BaseModel):
    credential_ids: List[int]
    group_name: Optional[str] = None

class CredentialRead(BaseModel):
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
    priority: int
    weight: int
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    max_concurrency: Optional[int] = None
    discovered_models_count: int = 0
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
    discovered_at: datetime
    created_at: Optional[datetime] = None
    rating: Optional[ModelRatingInfo] = None
    limits: Optional[ModelLimitsRead] = None


class DiscoveredModelUpdate(BaseModel):
    enabled: Optional[bool] = None
    is_visible: Optional[bool] = None
    display_name: Optional[str] = None
    input_price_per_1m: Optional[float] = None
    output_price_per_1m: Optional[float] = None
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
    temperature: Optional[float] = None
    priority_order: int = 0
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
    temperature: Optional[float] = None
    priority_order: int
    is_active: bool

class RoutingProfileCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    strategy: Literal["priority", "round_robin", "least_latency"] = "priority"
    retry_count: int = 3
    timeout_seconds: float = 60.0
    fallback_conditions: List[str] = Field(default_factory=lambda: ["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"])
    thinking_effort: Optional[str] = None
    context_length: Optional[int] = None
    temperature: Optional[float] = None
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
    strategy: Optional[Literal["priority", "round_robin", "least_latency"]] = None
    retry_count: Optional[int] = None
    timeout_seconds: Optional[float] = None
    fallback_conditions: Optional[List[str]] = None
    thinking_effort: Optional[str] = None
    context_length: Optional[int] = None
    temperature: Optional[float] = None
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
    context_length: Optional[int] = None
    temperature: Optional[float] = None
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
    temperature: Optional[float] = None
    priority_order: int = 0
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
    temperature: Optional[float] = None
    priority_order: int = 0
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
    judge_temperature: Optional[float] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None
    min_successful_candidates: int = 2
    max_parallelism: int = 5
    timeout_seconds: float = 120.0
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
    judge_temperature: Optional[float] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None
    min_successful_candidates: Optional[int] = None
    max_parallelism: Optional[int] = None
    timeout_seconds: Optional[float] = None
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
    judge_temperature: Optional[float] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None
    min_successful_candidates: int
    max_parallelism: int
    timeout_seconds: float
    enabled: bool
    participants: List[FusionParticipantRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

# Router API Key
class RouterApiKeyCreate(BaseModel):
    name: str
    permissions: List[str] = Field(default_factory=lambda: ["direct", "routes", "fusion"])
    allowed_models: List[str] = Field(default_factory=lambda: ["*"])
    allowed_routes: List[str] = Field(default_factory=lambda: ["*"])
    allowed_fusions: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    request_limit: Optional[int] = None
    expiration_date: Optional[datetime] = None
    ip_restrictions: List[str] = Field(default_factory=list)

class RouterApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    permissions: Optional[List[str]] = None
    allowed_models: Optional[List[str]] = None
    allowed_routes: Optional[List[str]] = None
    allowed_fusions: Optional[List[str]] = None
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    request_limit: Optional[int] = None
    expiration_date: Optional[datetime] = None
    ip_restrictions: Optional[List[str]] = None

class RouterApiKeyRead(BaseModel):
    id: int
    name: str
    key_prefix: str
    masked_key: str
    enabled: bool
    permissions: List[str]
    allowed_models: List[str]
    allowed_routes: List[str]
    allowed_fusions: List[str]
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    request_limit: Optional[int] = None
    total_requests: int
    expiration_date: Optional[datetime] = None
    ip_restrictions: List[str]
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
    cached_tokens_cost_saved_usd: float = 0.0
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
