export type Language =
  | "en" // English (Default / Primary standard)
  | "zh" // Chinese Simplified (Top 10)
  | "hi" // Hindi (Top 10)
  | "es" // Spanish (Top 10)
  | "fr" // French (Top 10)
  | "ar" // Arabic (Top 10)
  | "bn" // Bengali (Top 10)
  | "pt" // Portuguese (Top 10)
  | "ru" // Russian (Top 10)
  | "ja" // Japanese (Top 10)
  | "de" // German (Top 10)
  | "uk" // Ukrainian (Requested)
  | "be"; // Belarusian (Requested)

export interface LanguageInfo {
  code: Language;
  name: string;
  nativeName: string;
  flag: string;
  dir: "ltr" | "rtl";
}

export const SUPPORTED_LANGUAGES: LanguageInfo[] = [
  { code: "en", name: "English", nativeName: "English", flag: "🇬🇧", dir: "ltr" },
  { code: "zh", name: "Chinese (Simplified)", nativeName: "中文 (简体)", flag: "🇨🇳", dir: "ltr" },
  { code: "hi", name: "Hindi", nativeName: "हिन्दी", flag: "🇮🇳", dir: "ltr" },
  { code: "es", name: "Spanish", nativeName: "Español", flag: "🇪🇸", dir: "ltr" },
  { code: "fr", name: "French", nativeName: "Français", flag: "🇫🇷", dir: "ltr" },
  { code: "ar", name: "Arabic", nativeName: "العربية", flag: "🇸🇦", dir: "rtl" },
  { code: "bn", name: "Bengali", nativeName: "বাংলা", flag: "🇧🇩", dir: "ltr" },
  { code: "pt", name: "Portuguese", nativeName: "Português", flag: "🇵🇹", dir: "ltr" },
  { code: "ru", name: "Russian", nativeName: "Русский", flag: "🇷🇺", dir: "ltr" },
  { code: "ja", name: "Japanese", nativeName: "日本語", flag: "🇯🇵", dir: "ltr" },
  { code: "de", name: "German", nativeName: "Deutsch", flag: "🇩🇪", dir: "ltr" },
  { code: "uk", name: "Ukrainian", nativeName: "Українська", flag: "🇺🇦", dir: "ltr" },
  { code: "be", name: "Belarusian", nativeName: "Беларуская", flag: "🇧🇾", dir: "ltr" },
];

export interface TranslationSchema {
  common: {
    save: string;
    cancel: string;
    delete: string;
    edit: string;
    create: string;
    test: string;
    testing: string;
    copy: string;
    copied: string;
    search: string;
    filter: string;
    refresh: string;
    close: string;
    back: string;
    next: string;
    loading: string;
    error: string;
    success: string;
    status: string;
    enabled: string;
    disabled: string;
    active: string;
    inactive: string;
    yes: string;
    no: string;
    all: string;
    none: string;
    custom: string;
    actions: string;
    view: string;
    name: string;
    slug: string;
    description: string;
    details: string;
    export: string;
    import: string;
    confirmDelete: string;
    online: string;
    offline: string;
    total: string;
    seconds: string;
    tokens: string;
    model: string;
    provider: string;
    credential: string;
    group: string;
    temperature: string;
  };
  nav: {
    dashboard: string;
    analytics: string;
    logs: string;
    providers: string;
    credentials: string;
    models: string;
    routing: string;
    fusion: string;
    judge?: string;
    modules?: string;
    compression?: string;
    keys: string;
    proxies: string;
    playground: string;
    docs: string;
    settings: string;
    logout: string;
    groups: {
      overview: string;
      providersModels: string;
      routingResilience: string;
      securityAccess: string;
      testingDocs: string;
      admin: string;
    };
  };
  header: {
    gateway: string;
    gatewayOnline: string;
    connecting: string;
    playground: string;
    language: string;
  };
  login: {
    title: string;
    tagline: string;
    subtitle: string;
    username: string;
    password: string;
    loginBtn: string;
    signingIn: string;
    loginFailed: string;
    defaultCredentialsNotice: string;
  };
  dashboard: {
    title: string;
    subtitle: string;
    totalRequests: string;
    successRate: string;
    activeProviders: string;
    totalModels: string;
    activeKeys: string;
    p95Latency: string;
    quickActions: string;
    testPlayground: string;
    manageRoutes: string;
    createFusion: string;
    viewLogs: string;
    systemHealth: string;
    circuitBreakers: string;
    recentActivity: string;
    noRecentActivity: string;
  };
  analytics: {
    title: string;
    subtitle: string;
    timeRange: string;
    totalCalls: string;
    promptTokens: string;
    completionTokens: string;
    avgLatency: string;
    errorRate: string;
    statusDistribution: string;
    topErrors: string;
    keyMetrics: string;
    providerBreakdown: string;
  };
  logs: {
    title: string;
    subtitle: string;
    searchPlaceholder: string;
    autoRefresh: string;
    clearLogs: string;
    exportLogs: string;
    inspectTrace: string;
    waterfall: string;
    attempts: string;
    prompt: string;
    response: string;
    reasoning: string;
    noLogsFound: string;
  };
  providers: {
    title: string;
    subtitle: string;
    addProvider: string;
    editProvider: string;
    providerName: string;
    adapterType: string;
    baseUrl: string;
    modelsCount: string;
    credentialsCount: string;
    testConnection: string;
  };
  credentials: {
    title: string;
    subtitle: string;
    addKey: string;
    editKey: string;
    keyName: string;
    apiKey: string;
    group: string;
    noGroup: string;
    priority: string;
    weight: string;
    proxy: string;
    testKey: string;
  };
  models: {
    title: string;
    subtitle: string;
    syncModels: string;
    searchModels: string;
    showHidden: string;
    canonicalSlug: string;
    contextLength: string;
    maxOutputTokens: string;
    modelTemperature: string;
  };
  routing: {
    title: string;
    subtitle: string;
    createRoute: string;
    editRoute: string;
    routeName: string;
    slug: string;
    defaultTemperature: string;
    candidates: string;
    addCandidate: string;
    priorityChain: string;
    reasoningEffort: string;
    tempOverride: string;
    randomize: string;
  };
  fusion: {
    title: string;
    subtitle: string;
    createFusion: string;
    editFusion: string;
    fusionName: string;
    strategy: string;
    judge: string;
    judgeType: string;
    judgeModel: string;
    judgeRoute: string;
    judgeThinking: string;
    judgeTemperature: string;
    participants: string;
    addParticipant: string;
    minSuccess: string;
    timeout: string;
  };
  keys: {
    title: string;
    subtitle: string;
    createKey: string;
    keyName: string;
    allowedModels: string;
    rateLimitRpm: string;
    rateLimitTpm: string;
    createdKeyWarning: string;
  };
  proxies: {
    title: string;
    subtitle: string;
    addProxy: string;
    editProxy: string;
    host: string;
    port: string;
    country: string;
    testProxy: string;
    testAll: string;
  };
  playground: {
    title: string;
    subtitle: string;
    selectModel: string;
    systemPrompt: string;
    userPrompt: string;
    send: string;
    streaming: string;
    clearChat: string;
    statsLatency: string;
    statsTokens: string;
  };
  docs: {
    title: string;
    subtitle: string;
    quickStart: string;
    endpointBase: string;
    routingSyntax: string;
    fusionSyntax: string;
  };
  settings: {
    title: string;
    subtitle: string;
    encryption: string;
    encryptionDesc: string;
    privacy: string;
    privacyDesc: string;
    adminPassword: string;
    changePassword: string;
    newPassword: string;
    backupRestore: string;
    exportBackup: string;
    importBackup: string;
    languageSection: string;
    languageDesc: string;
  };
}
