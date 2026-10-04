from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from sqlalchemy import (
    String, Integer, Boolean, Float, DateTime, Text, ForeignKey, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, TimestampMixin

class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class Proxy(Base, TimestampMixin):
    __tablename__ = "proxies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scheme: Mapped[str] = mapped_column(String(20), default="http", nullable=False)  # http, https, socks5, socks5h
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    encrypted_username: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="UNTESTED", nullable=False)  # HEALTHY, ERROR, UNTESTED
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    last_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    credentials: Mapped[List["ProviderCredential"]] = relationship("ProviderCredential", back_populates="proxy")

class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)  # google, openai, anthropic, openrouter, generic_openai, groq, etc.
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    models_endpoint: Mapped[str] = mapped_column(String(255), default="/models", nullable=False)
    chat_endpoint: Mapped[str] = mapped_column(String(255), default="/chat/completions", nullable=False)
    responses_endpoint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), default="bearer", nullable=False)  # bearer, x-api-key, custom_header, query_param, none
    auth_header: Mapped[str] = mapped_column(String(100), default="Authorization", nullable=False)
    extra_headers: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    credentials: Mapped[List["ProviderCredential"]] = relationship("ProviderCredential", back_populates="provider", cascade="all, delete-orphan")
    models: Mapped[List["DiscoveredModel"]] = relationship("DiscoveredModel", back_populates="provider", cascade="all, delete-orphan")

    @property
    def adapter_configuration(self) -> Dict[str, Any]:
        return {
            **self.configuration,
            "models_endpoint": self.models_endpoint,
            "chat_endpoint": self.chat_endpoint,
            "responses_endpoint": self.responses_endpoint,
            "auth_type": self.auth_type,
            "auth_header": self.auth_header,
        }

class ProviderCredential(Base, TimestampMixin):
    __tablename__ = "provider_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    masked_key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    group_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proxy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("proxies.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)  # HEALTHY, DEGRADED, RATE_LIMITED, COOLDOWN, INVALID, DISABLED, UNKNOWN
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rpm_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tpm_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_concurrency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    provider: Mapped["Provider"] = relationship("Provider", back_populates="credentials")
    proxy: Mapped[Optional["Proxy"]] = relationship("Proxy", back_populates="credentials")
    discovered_models: Mapped[List["DiscoveredModel"]] = relationship("DiscoveredModel", back_populates="credential", cascade="all, delete-orphan")
    model_preferences: Mapped[List["CredentialModelPreference"]] = relationship("CredentialModelPreference", back_populates="credential", cascade="all, delete-orphan", order_by="CredentialModelPreference.priority_order")

class DiscoveredModel(Base, TimestampMixin):
    __tablename__ = "discovered_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="CASCADE"), nullable=True)
    provider_model_id: Mapped[str] = mapped_column(String(150), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    canonical_slug: Mapped[str] = mapped_column(String(200), index=True, nullable=False)  # e.g. google/gemini-3.8-flash
    capabilities: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    supported_endpoints: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    context_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_price_per_1m: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    output_price_per_1m: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reasoning_effort: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_type: Mapped[str] = mapped_column(String(50), default="openai", nullable=False)  # "openai" or "jev"
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    provider: Mapped["Provider"] = relationship("Provider", back_populates="models")
    credential: Mapped[Optional["ProviderCredential"]] = relationship("ProviderCredential", back_populates="discovered_models")

class CredentialModelPreference(Base, TimestampMixin):
    __tablename__ = "credential_model_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential_id: Mapped[int] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("discovered_models.id", ondelete="CASCADE"), nullable=False)
    priority_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    credential: Mapped["ProviderCredential"] = relationship("ProviderCredential", back_populates="model_preferences")
    model: Mapped["DiscoveredModel"] = relationship("DiscoveredModel")

class RoutingProfile(Base, TimestampMixin):
    __tablename__ = "routing_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)  # e.g. "coding", accessed as "route/coding"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strategy: Mapped[str] = mapped_column(String(50), default="priority", nullable=False)  # priority, round_robin, least_latency
    retry_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=60.0, nullable=False)
    fallback_conditions: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"], nullable=False)
    thinking_effort: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    context_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    randomize_candidates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    randomize_keys: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    candidates: Mapped[List["RoutingCandidate"]] = relationship("RoutingCandidate", back_populates="profile", cascade="all, delete-orphan", order_by="RoutingCandidate.priority_order", foreign_keys="RoutingCandidate.profile_id")

class RoutingCandidate(Base, TimestampMixin):
    __tablename__ = "routing_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("routing_profiles.id", ondelete="CASCADE"), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(30), default="model", nullable=False)  # "model" or "profile"
    target_profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routing_profiles.id", ondelete="CASCADE"), nullable=True)
    provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True)
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="CASCADE"), nullable=True)
    model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("discovered_models.id", ondelete="CASCADE"), nullable=True)
    thinking_effort: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    credential_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["RoutingProfile"] = relationship("RoutingProfile", back_populates="candidates", foreign_keys=[profile_id])
    target_profile: Mapped[Optional["RoutingProfile"]] = relationship("RoutingProfile", foreign_keys=[target_profile_id])
    provider: Mapped[Optional["Provider"]] = relationship("Provider")
    credential: Mapped[Optional["ProviderCredential"]] = relationship("ProviderCredential")
    model: Mapped[Optional["DiscoveredModel"]] = relationship("DiscoveredModel")

class FusionProfile(Base, TimestampMixin):
    __tablename__ = "fusion_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)  # accessed as "fusion/slug"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strategy: Mapped[str] = mapped_column(String(50), default="synthesize", nullable=False)  # synthesize, best_of_n, consensus, critique_and_rewrite
    judge_type: Mapped[str] = mapped_column(String(30), default="model", nullable=False)  # "model" or "profile"
    judge_routing_profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routing_profiles.id", ondelete="SET NULL"), nullable=True)
    judge_provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True)
    judge_credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True)
    judge_credential_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    judge_model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("discovered_models.id", ondelete="CASCADE"), nullable=True)
    judge_thinking_effort: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    judge_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    min_successful_candidates: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_parallelism: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=120.0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    judge_routing_profile: Mapped[Optional["RoutingProfile"]] = relationship("RoutingProfile", foreign_keys=[judge_routing_profile_id])
    judge_provider: Mapped[Optional["Provider"]] = relationship("Provider", foreign_keys=[judge_provider_id])
    judge_credential: Mapped[Optional["ProviderCredential"]] = relationship("ProviderCredential", foreign_keys=[judge_credential_id])
    judge_model: Mapped[Optional["DiscoveredModel"]] = relationship("DiscoveredModel", foreign_keys=[judge_model_id])
    participants: Mapped[List["FusionParticipant"]] = relationship("FusionParticipant", back_populates="profile", cascade="all, delete-orphan", order_by="FusionParticipant.priority_order")

class FusionParticipant(Base, TimestampMixin):
    __tablename__ = "fusion_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("fusion_profiles.id", ondelete="CASCADE"), nullable=False)
    participant_type: Mapped[str] = mapped_column(String(30), default="model", nullable=False)  # "model" or "profile"
    target_profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routing_profiles.id", ondelete="CASCADE"), nullable=True)
    provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True)
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True)
    credential_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("discovered_models.id", ondelete="CASCADE"), nullable=True)
    thinking_effort: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    priority_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    label: Mapped[str] = mapped_column(String(50), default="Participant", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["FusionProfile"] = relationship("FusionProfile", back_populates="participants")
    target_profile: Mapped[Optional["RoutingProfile"]] = relationship("RoutingProfile", foreign_keys=[target_profile_id])
    provider: Mapped[Optional["Provider"]] = relationship("Provider", foreign_keys=[provider_id])
    credential: Mapped[Optional["ProviderCredential"]] = relationship("ProviderCredential", foreign_keys=[credential_id])
    model: Mapped[Optional["DiscoveredModel"]] = relationship("DiscoveredModel", foreign_keys=[model_id])

class JudgeProfile(Base, TimestampMixin):
    __tablename__ = "judge_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)  # accessed as "judge/<slug>" or "smart/<slug>"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strategy: Mapped[str] = mapped_column(String(50), default="auto", nullable=False)  # auto, complexity, task_type
    judge_type: Mapped[str] = mapped_column(String(30), default="model", nullable=False)  # "model" or "profile"
    judge_routing_profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routing_profiles.id", ondelete="SET NULL"), nullable=True)
    judge_provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True)
    judge_credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True)
    judge_credential_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    judge_model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("discovered_models.id", ondelete="CASCADE"), nullable=True)
    judge_thinking_effort: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    judge_temperature: Mapped[Optional[float]] = mapped_column(Float, default=0.1, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fallback_candidate_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fallback_strongest_on_overflow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    context_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=60.0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    judge_routing_profile: Mapped[Optional["RoutingProfile"]] = relationship("RoutingProfile", foreign_keys=[judge_routing_profile_id])
    judge_provider: Mapped[Optional["Provider"]] = relationship("Provider", foreign_keys=[judge_provider_id])
    judge_credential: Mapped[Optional["ProviderCredential"]] = relationship("ProviderCredential", foreign_keys=[judge_credential_id])
    judge_model: Mapped[Optional["DiscoveredModel"]] = relationship("DiscoveredModel", foreign_keys=[judge_model_id])
    candidates: Mapped[List["JudgeCandidate"]] = relationship("JudgeCandidate", back_populates="profile", cascade="all, delete-orphan", order_by="JudgeCandidate.priority_order")

class JudgeCandidate(Base, TimestampMixin):
    __tablename__ = "judge_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("judge_profiles.id", ondelete="CASCADE"), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(30), default="model", nullable=False)  # "model" or "profile"
    target_profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routing_profiles.id", ondelete="CASCADE"), nullable=True)
    provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True)
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True)
    credential_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("discovered_models.id", ondelete="CASCADE"), nullable=True)
    thinking_effort: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    priority_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    label: Mapped[str] = mapped_column(String(100), default="Candidate", nullable=False)
    task_types: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    complexity_level: Mapped[str] = mapped_column(String(50), default="all", nullable=False)  # "low", "medium", "high", "all"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["JudgeProfile"] = relationship("JudgeProfile", back_populates="candidates")
    target_profile: Mapped[Optional["RoutingProfile"]] = relationship("RoutingProfile", foreign_keys=[target_profile_id])
    provider: Mapped[Optional["Provider"]] = relationship("Provider", foreign_keys=[provider_id])
    credential: Mapped[Optional["ProviderCredential"]] = relationship("ProviderCredential", foreign_keys=[credential_id])
    model: Mapped[Optional["DiscoveredModel"]] = relationship("DiscoveredModel", foreign_keys=[model_id])

class RouterApiKey(Base, TimestampMixin):
    __tablename__ = "router_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # e.g. sk-router-abcd
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    masked_key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    permissions: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["direct", "routes", "fusion", "judge"], nullable=False)
    allowed_models: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["*"], nullable=False)
    allowed_routes: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["*"], nullable=False)
    allowed_fusions: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["*"], nullable=False)
    allowed_judges: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["*"], nullable=False)
    rate_limit_rpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rate_limit_tpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    request_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_restrictions: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class RequestLog(Base, TimestampMixin):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    router_key_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("router_api_keys.id", ondelete="SET NULL"), nullable=True)
    requested_model: Mapped[str] = mapped_column(String(150), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)  # DIRECT, PRIORITY, FUSION
    resolved_provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)
    resolved_credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True)
    upstream_model: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", nullable=False)  # SUCCESS, FAILED, FALLBACK_SUCCESS, FUSION_SUCCESS
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Only if LOG_REQUEST_CONTENT enabled
    response_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Only if LOG_REQUEST_CONTENT enabled
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    attempts: Mapped[List["RequestAttempt"]] = relationship("RequestAttempt", back_populates="request_log", cascade="all, delete-orphan")
    router_key: Mapped[Optional["RouterApiKey"]] = relationship("RouterApiKey", foreign_keys=[router_key_id], lazy="select")
    resolved_provider: Mapped[Optional["Provider"]] = relationship("Provider", foreign_keys=[resolved_provider_id], lazy="select")
    resolved_credential: Mapped[Optional["ProviderCredential"]] = relationship("ProviderCredential", foreign_keys=[resolved_credential_id], lazy="select")

class RequestAttempt(Base, TimestampMixin):
    __tablename__ = "request_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_log_id: Mapped[int] = mapped_column(Integer, ForeignKey("request_logs.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    credential_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # SUCCESS, FAILED
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    request_log: Mapped["RequestLog"] = relationship("RequestLog", back_populates="attempts")

class UsageRecord(Base, TimestampMixin):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    router_key_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("router_api_keys.id", ondelete="SET NULL"), nullable=True)
    provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True)
    model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("discovered_models.id", ondelete="SET NULL"), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)

class CompressionGlobalSetting(Base, TimestampMixin):
    __tablename__ = "compression_global_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trigger_token_threshold: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    min_savings_bailout_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    preserve_recent_turns: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    preserve_system_prompt_mode: Mapped[str] = mapped_column(String(50), default="when_caching", nullable=False)  # when_caching, always, never
    enable_telemetry: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fail_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class CompressionStage(Base, TimestampMixin):
    __tablename__ = "compression_stages"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # slug
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="Zap", nullable=False)
    stage_type: Mapped[str] = mapped_column(String(50), default="builtin", nullable=False)  # builtin, custom_regex, custom_script
    priority_order: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    custom_rules: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

class ResponseCacheEntry(Base, TimestampMixin):
    __tablename__ = "response_cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signature: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    response_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_hit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class CacheMetric(Base):
    __tablename__ = "cache_metrics"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class SecurityConfig(Base, TimestampMixin):
    __tablename__ = "security_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Prompt injection guardrail
    injection_guard_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    injection_mode: Mapped[str] = mapped_column(String(20), default="warn", nullable=False)  # "block", "warn", "log"
    injection_threshold: Mapped[str] = mapped_column(String(20), default="high", nullable=False)  # "high", "medium", "low"
    max_injection_scan_bytes: Mapped[int] = mapped_column(Integer, default=16384, nullable=False)  # 16 KB bounded scan
    custom_injection_patterns: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list, nullable=True)

    # Credential masker guardrail (bidirectional)
    credential_masking_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # opt-in
    mask_inbound: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mask_outbound: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_credential_patterns: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list, nullable=True)

    # DuckDuckGo fallback web search
    duckduckgo_fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # OIDC login gate
    oidc_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    oidc_disable_password_login: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    oidc_issuer: Mapped[Optional[str]] = mapped_column(String(500), default="", nullable=True)
    oidc_client_id: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    oidc_client_secret: Mapped[Optional[str]] = mapped_column(String(500), default="", nullable=True)
    oidc_scopes: Mapped[Optional[List[str]]] = mapped_column(JSON, default=lambda: ["openid", "profile", "email"], nullable=True)
    oidc_allowed_emails: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list, nullable=True)


