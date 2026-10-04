export interface DashboardStats {
  total_providers: number;
  total_credentials: number;
  healthy_credentials: number;
  total_models: number;
  total_routes: number;
  total_fusions: number;
  total_judges?: number;
  requests_24h: number;
  fallbacks_24h: number;
  success_rate_24h: number;
  avg_latency_24h: number;
  total_tokens_24h: number;
  estimated_cost_24h: number;
}

export interface Proxy {
  id: number;
  name: string;
  scheme: "http" | "https" | "socks5" | "socks5h";
  host: string;
  port: number;
  has_auth: boolean;
  enabled: boolean;
  status: string;
  country?: string;
  country_code?: string;
  assigned_providers?: string[];
  last_check?: string;
  last_error?: string;
  created_at: string;
}

export interface ProxyCreate {
  name: string;
  scheme: "http" | "https" | "socks5" | "socks5h";
  host: string;
  port: number;
  username?: string;
  password?: string;
  enabled?: boolean;
  country?: string;
  country_code?: string;
}

export interface ProxyTestResult {
  success: boolean;
  latency_ms: number;
  message: string;
  ip?: string;
  server_ip?: string;
  country?: string;
  country_code?: string;
  details?: string;
}

export interface ProxyParseResult {
  scheme: "http" | "https" | "socks5";
  host: string;
  port: number;
  username?: string;
  password?: string;
  suggested_name?: string;
}

export interface Provider {
  id: number;
  name: string;
  slug: string;
  adapter_type: string;
  base_url: string;
  models_endpoint: string;
  chat_endpoint: string;
  responses_endpoint?: string;
  enabled: boolean;
  auth_type: "bearer" | "x-api-key" | "custom_header" | "query_param" | "none";
  auth_header: string;
  extra_headers: Record<string, any>;
  configuration: Record<string, any>;
  notes?: string | null;
  credentials_count: number;
  models_count: number;
  healthy_credentials_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProviderCreate {
  name: string;
  slug: string;
  adapter_type: string;
  base_url: string;
  models_endpoint?: string;
  chat_endpoint?: string;
  responses_endpoint?: string;
  enabled?: boolean;
  auth_type?: "bearer" | "x-api-key" | "custom_header" | "query_param" | "none";
  auth_header?: string;
  extra_headers?: Record<string, any>;
  configuration?: Record<string, any>;
  notes?: string | null;
}

export interface Credential {
  id: number;
  provider_id: number;
  provider_name: string;
  name: string;
  group_name?: string | null;
  masked_key: string;
  key_fingerprint: string;
  enabled: boolean;
  proxy_id?: number;
  proxy_name?: string;
  status: "HEALTHY" | "DEGRADED" | "RATE_LIMITED" | "COOLDOWN" | "INVALID" | "DISABLED" | "UNKNOWN";
  last_checked_at?: string;
  last_success_at?: string;
  last_error?: string;
  consecutive_failures: number;
  cooldown_until?: string;
  model_cooldowns?: Record<string, number>;
  priority: number;
  weight: number;
  rpm_limit?: number;
  tpm_limit?: number;
  max_concurrency?: number;
  discovered_models_count: number;
  created_at: string;
}

export interface CredentialCreate {
  provider_id: number;
  name: string;
  api_key: string;
  group_name?: string | null;
  proxy_id?: number;
  priority?: number;
  weight?: number;
  rpm_limit?: number;
  tpm_limit?: number;
  max_concurrency?: number;
}

export interface CredentialTestResult {
  success: boolean;
  latency_ms: number;
  message: string;
  models_found: number;
  error_category?: string;
}

export interface ModelRatingInfo {
  intelligence_index?: number;
  coding_index?: number;
  agentic_index?: number;
  speed_tokens_per_sec?: number;
  is_reasoning?: boolean;
  eval_provider: string;
  source_url?: string;
  model_creator?: string;
  aa_name?: string;
  aa_slug?: string;
}

export interface ModelLimitsInfo {
  model_id: number;
  provider_model_id: string;
  canonical_slug: string;
  provider_slug: string;
  context_length?: number;
  max_output_tokens?: number;
  rate_limit_rpm?: number;
  rate_limit_tpm?: number;
  rate_limit_rpd?: number;
  remaining_requests?: number;
  remaining_tokens?: number;
  reset_requests?: string;
  reset_tokens?: string;
  account_usage?: number;
  account_limit?: number;
  is_free_tier?: boolean;
  source: "direct_api" | "credential_config" | "database";
  fetched_at: string;
  raw_details?: Record<string, any>;
}

export interface DiscoveredModel {
  id: number;
  provider_id: number;
  provider_name: string;
  credential_id?: number;
  credential_name?: string;
  provider_model_id: string;
  display_name: string;
  canonical_slug: string;
  capabilities: Record<string, any>;
  supported_endpoints: string[];
  context_length?: number;
  max_output_tokens?: number;
  input_price_per_1m: number;
  output_price_per_1m: number;
  enabled: boolean;
  available: boolean;
  is_visible: boolean;
  model_type?: "openai" | "jev" | string;
  reasoning_effort?: string;
  temperature?: number | null;
  discovered_at: string;
  created_at?: string;
  rating?: ModelRatingInfo;
  limits?: ModelLimitsInfo;
}

export interface RoutingCandidate {
  id: number;
  candidate_type?: "model" | "profile";
  target_profile_id?: number;
  target_profile_name?: string;
  target_profile_slug?: string;
  provider_id?: number;
  provider_name?: string;
  credential_id?: number;
  credential_name?: string;
  credential_group?: string | null;
  model_id?: number;
  model_name?: string;
  canonical_slug?: string;
  thinking_effort?: string;
  temperature?: number | null;
  priority_order: number;
  is_active: boolean;
}

export interface RoutingProfile {
  id: number;
  name: string;
  slug: string;
  description?: string;
  strategy: "priority" | "round_robin" | "least_latency";
  retry_count: number;
  timeout_seconds: number;
  fallback_conditions: string[];
  thinking_effort?: string;
  temperature?: number | null;
  context_length?: number | null;
  randomize_candidates?: boolean;
  randomize_keys?: boolean;
  enabled: boolean;
  candidates: RoutingCandidate[];
  created_at: string;
  updated_at: string;
}

export interface FusionParticipant {
  id: number;
  participant_type?: "model" | "profile";
  target_profile_id?: number | null;
  target_profile_name?: string | null;
  target_profile_slug?: string | null;
  provider_id?: number | null;
  provider_name?: string | null;
  credential_id?: number | null;
  credential_name?: string | null;
  credential_group?: string | null;
  model_id?: number | null;
  model_name?: string | null;
  canonical_slug?: string | null;
  label: string;
  thinking_effort?: string | null;
  temperature?: number | null;
  priority_order?: number;
  is_active: boolean;
}

export interface FusionProfile {
  id: number;
  name: string;
  slug: string;
  description?: string;
  strategy: "synthesize" | "best_of_n" | "consensus" | "critique_and_rewrite";
  judge_type?: "model" | "profile";
  judge_routing_profile_id?: number | null;
  judge_routing_profile_name?: string | null;
  judge_routing_profile_slug?: string | null;
  judge_provider_id?: number | null;
  judge_provider_name?: string | null;
  judge_credential_id?: number | null;
  judge_credential_name?: string | null;
  judge_credential_group?: string | null;
  judge_model_id?: number | null;
  judge_model_name?: string | null;
  judge_thinking_effort?: string | null;
  judge_temperature?: number | null;
  temperature?: number | null;
  system_prompt?: string;
  min_successful_candidates: number;
  max_parallelism: number;
  timeout_seconds: number;
  enabled: boolean;
  participants: FusionParticipant[];
  created_at: string;
  updated_at: string;
}

export interface JudgeCandidate {
  id?: number;
  candidate_type: "model" | "profile";
  target_profile_id?: number | null;
  target_profile_name?: string | null;
  target_profile_slug?: string | null;
  provider_id?: number | null;
  provider_name?: string | null;
  credential_id?: number | null;
  credential_name?: string | null;
  credential_group?: string | null;
  model_id?: number | null;
  model_name?: string | null;
  canonical_slug?: string | null;
  label: string;
  task_types: string[];
  complexity_level: "low" | "medium" | "high" | "all" | string;
  description?: string | null;
  thinking_effort?: string | null;
  temperature?: number | null;
  priority_order?: number;
  is_active: boolean;
}

export interface JudgeProfile {
  id: number;
  name: string;
  slug: string;
  description?: string;
  strategy: "auto" | "complexity" | "task_type" | string;
  judge_type?: "model" | "profile";
  judge_routing_profile_id?: number | null;
  judge_routing_profile_name?: string | null;
  judge_routing_profile_slug?: string | null;
  judge_provider_id?: number | null;
  judge_provider_name?: string | null;
  judge_credential_id?: number | null;
  judge_credential_name?: string | null;
  judge_credential_group?: string | null;
  judge_model_id?: number | null;
  judge_model_name?: string | null;
  judge_canonical_slug?: string | null;
  judge_model_type?: string | null;
  judge_thinking_effort?: string | null;
  judge_temperature?: number | null;
  system_prompt?: string;
  fallback_candidate_id?: number | null;
  fallback_strongest_on_overflow?: boolean;
  context_length?: number | null;
  timeout_seconds: number;
  enabled: boolean;
  candidates: JudgeCandidate[];
  created_at: string;
  updated_at: string;
}

export interface JudgeTestResponse {
  selected_candidate_id?: number | null;
  selected_candidate_label: string;
  selected_target: string;
  strategy: string;
  estimated_complexity: string;
  detected_task_type?: string | null;
  judge_reasoning: string;
  judge_model_name: string;
  latency_ms: number;
  status: string;
  error?: string | null;
}

export interface RouterApiKey {
  id: number;
  name: string;
  key_prefix: string;
  masked_key: string;
  enabled: boolean;
  permissions: string[];
  allowed_models: string[];
  allowed_routes: string[];
  allowed_fusions: string[];
  allowed_judges?: string[];
  rate_limit_rpm?: number;
  rate_limit_tpm?: number;
  request_limit?: number;
  total_requests: number;
  expiration_date?: string;
  ip_restrictions: string[];
  last_used_at?: string;
  created_at: string;
}

export interface RouterApiKeyCreated extends RouterApiKey {
  raw_api_key: string;
}

export interface RequestAttempt {
  id: number;
  attempt_number: number;
  provider_name: string;
  credential_name: string;
  model_name: string;
  status: string;
  http_status?: number;
  error_category?: string;
  error_message?: string;
  latency_ms: number;
}

export interface RequestLog {
  id: number;
  request_id: string;
  router_key_id?: number;
  router_key_name?: string;
  resolved_provider_name?: string;
  resolved_credential_name?: string;
  requested_model: string;
  mode: string;
  upstream_model?: string;
  latency_ms: number;
  status_code: number;
  status: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
  estimated_cost_usd: number;
  error_category?: string;
  error_message?: string;
  prompt_content?: string;
  response_content?: string;
  metadata_json: Record<string, any>;
  created_at: string;
  attempts: RequestAttempt[];
}

export interface LogsSummaryResponse {
  total_requests: number;
  total_errors: number;
  error_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cached_tokens: number;
  total_reasoning_tokens: number;
  total_cost_usd: number;
  total_fallback_rescued: number;
}

export interface RouterApiKeyCreate {
  name: string;
  permissions?: string[];
  allowed_models?: string[];
  allowed_routes?: string[];
  allowed_fusions?: string[];
  allowed_judges?: string[];
  rate_limit_rpm?: number;
}

export interface StatusCodeItem {
  code: number;
  count: number;
  percentage: number;
}

export interface TopErrorItem {
  error_message: string;
  error_category: string;
  count: number;
  last_seen?: string | null;
}

export interface FallbackFunnelStats {
  total_profile_requests: number;
  primary_direct_success: number;
  primary_key_failover_success: number;
  fallback_model_success: number;
  chain_failures: number;
  baseline_success_rate: number;
  final_success_rate: number;
  reliability_gain_pct: number;
}

export interface SummaryComparison {
  requests_change_pct?: number | null;
  success_rate_change_pct?: number | null;
  tokens_change_pct?: number | null;
  cost_change_pct?: number | null;
  latency_change_pct?: number | null;
}

export interface KeyStatsItem {
  id?: number;
  name: string;
  prefix: string;
  requests_count: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens?: number;
  reasoning_tokens?: number;
  total_tokens: number;
  estimated_cost_usd: number;
  avg_latency_ms: number;
  p50_latency_ms?: number;
  p90_latency_ms?: number;
  tokens_per_sec?: number;
}

export interface CredentialStatsItem {
  id?: number;
  name: string;
  provider_name: string;
  status: string;
  requests_count: number;
  success_count: number;
  failure_count: number;
  fallback_success_count: number;
  success_rate: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens?: number;
  reasoning_tokens?: number;
  total_tokens: number;
  avg_latency_ms: number;
  p50_latency_ms?: number;
  p90_latency_ms?: number;
  tokens_per_sec?: number;
}

export interface ProviderStatsItem {
  id?: number;
  name: string;
  slug: string;
  requests_count: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens?: number;
  reasoning_tokens?: number;
  total_tokens: number;
  estimated_cost_usd: number;
  avg_latency_ms: number;
  p50_latency_ms?: number;
  p90_latency_ms?: number;
  tokens_per_sec?: number;
}

export interface ModelStatsItem {
  model_name: string;
  provider_name: string;
  requests_count: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  avg_latency_ms: number;
  p50_latency_ms?: number;
  p90_latency_ms?: number;
  tokens_per_sec?: number;
}

export interface ProfileCandidateStat {
  priority_order: number;
  name: string;
  model_id?: string | null;
  candidate_type: string;
  requests_count: number;
  success_count: number;
}

export interface ProfileStatsItem {
  slug: string;
  name: string;
  mode: string;
  is_active: boolean;
  candidates_count: number;
  requests_count: number;
  success_count: number;
  first_candidate_success_count: number;
  fallback_success_count: number;
  key_failover_count: number;
  failure_count: number;
  fallback_rate: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens?: number;
  reasoning_tokens?: number;
  total_tokens: number;
  estimated_cost_usd: number;
  avg_latency_ms: number;
  p50_latency_ms?: number;
  p90_latency_ms?: number;
  tokens_per_sec?: number;
  candidates: ProfileCandidateStat[];
}

export interface SummaryStats {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  fallback_requests: number;
  success_rate: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cached_tokens: number;
  total_reasoning_tokens: number;
  estimated_cost_usd: number;
  avg_latency_ms: number;
  p50_latency_ms?: number;
  p90_latency_ms?: number;
  p99_latency_ms?: number;
  tokens_per_sec?: number;
  cached_tokens_cost_saved_usd?: number;
  projected_daily_cost_usd?: number;
  projected_monthly_cost_usd?: number;
}

export interface TimeBucketStatsItem {
  time_label: string;
  timestamp: string;
  requests: number;
  errors: number;
  fallbacks: number;
  tokens: number;
  cost?: number;
  avg_latency_ms?: number;
}

export interface DetailedAnalyticsResponse {
  period: "today" | "yesterday" | "24h" | "7d" | "30d" | "this_month" | "custom" | "all" | string;
  start_date?: string | null;
  end_date?: string | null;
  granularity?: "hour" | "day";
  filter_type?: string | null;
  filter_value?: string | null;
  summary: SummaryStats;
  comparison?: SummaryComparison | null;
  fallback_funnel?: FallbackFunnelStats | null;
  status_codes: StatusCodeItem[];
  top_errors: TopErrorItem[];
  timeline: TimeBucketStatsItem[];
  by_router_keys: KeyStatsItem[];
  by_credentials: CredentialStatsItem[];
  by_providers: ProviderStatsItem[];
  by_models: ModelStatsItem[];
  by_profiles: ProfileStatsItem[];
}

export interface BackupExportRequest {
  provider_ids?: number[];
  include_proxies?: boolean;
  passphrase: string;
}

export interface BackupProviderSummary {
  name: string;
  slug: string;
  adapter_type: string;
  base_url: string;
  keys_count: number;
  existing_keys_count: number;
  exists_in_target: boolean;
}

export interface BackupPreviewResponse {
  valid: boolean;
  exported_at?: string;
  total_providers: number;
  new_providers: number;
  existing_providers: number;
  total_credentials: number;
  existing_credentials: number;
  new_credentials: number;
  total_proxies: number;
  groups: string[];
  providers_summary: BackupProviderSummary[];
}

export interface BackupImportRequest {
  raw_payload: any;
  passphrase: string;
  update_existing_providers?: boolean;
  skip_duplicate_credentials?: boolean;
  auto_discover_models?: boolean;
}

export interface BackupImportResponse {
  success: boolean;
  imported_providers: number;
  updated_providers: number;
  skipped_providers: number;
  imported_credentials: number;
  updated_credentials: number;
  skipped_credentials: number;
  imported_proxies: number;
  errors: string[];
  discovery_triggered: boolean;
}

// Jev / System One Decision Interfaces
export type JevModelType = "openai" | "jev";

export interface JevChoiceQuestion {
  criteria: Record<string, string>;
}

export interface JevScoreQuestion {
  rubric: string[];
}

export interface JevNoulQuestion {
  description?: string;
}

export type JevQuestion =
  | { choice: JevChoiceQuestion }
  | { score: JevScoreQuestion }
  | { noul: JevNoulQuestion };

export interface JevRequest {
  model: string;
  state: string;
  questions: Record<string, JevQuestion>;
}

export interface JevChoiceAnswer {
  decision: string;
  probabilities: Record<string, number>;
  confidence?: number;
}

export interface JevScoreAnswer {
  level: string;
  index: number;
  distribution: Record<string, number>;
  confidence?: number;
}

export interface JevNoulAnswer {
  probability: number;
  judgment: boolean;
}

export type JevAnswer = JevChoiceAnswer | JevScoreAnswer | JevNoulAnswer;

export interface JevUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface JevResponse {
  id: string;
  model: string;
  answers: Record<string, any>;
  usage: JevUsage;
  latency_ms?: number;
}
