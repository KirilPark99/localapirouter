import React, { useEffect, useState, useMemo, useRef } from "react";
import {
  Send,
  Square,
  Terminal,
  Sparkles,
  Clock,
  Zap,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Copy,
  Check,
  Code,
  Columns,
  MessageSquare,
  Trash2,
  Search,
  SlidersHorizontal,
  ShieldCheck,
  Bot,
  User,
  GitFork,
  Merge,
  Boxes,
  X,
  Plus,
  Brain,
  Cpu,
  HelpCircle,
  Layers,
  BarChart3,
  CheckSquare,
} from "lucide-react";
import { apiRequest, expireSession } from "../api/client";
import {
  DiscoveredModel,
  RoutingProfile,
  FusionProfile,
  JudgeProfile,
  RouterApiKey,
  Provider,
  JevRequest,
  JevResponse,
  JevQuestion,
} from "../types";
import { getHiddenModelIds, groupModelsByProvider, getVisibleModels } from "../utils/models";
import { useI18n } from "../i18n";

type PlaygroundMode = "single" | "chat" | "compare" | "jev";
type ThinkingEffort = "auto" | "low" | "medium" | "high" | "off" | "custom";

export interface JevPreset {
  id: string;
  name: string;
  description: string;
  state: string;
  questions: Record<string, JevQuestion>;
}

export const JEV_PRESETS: JevPreset[] = [
  {
    id: "support-escalation",
    name: "Support Escalation",
    description: "Evaluates ticket urgency, intent classification, and customer churn risk.",
    state: "Customer Message: 'My account has been locked without any prior notice and my sales team is blocked from closing deals! This is unacceptable and costing us thousands. Fix this in the next 30 minutes or we are cancelling our enterprise contract and issuing a chargeback!'\nCustomer Details: Tier: Enterprise VIP, MRR: $4,500/mo, Past escalations: 0.",
    questions: {
      intent: {
        choice: {
          criteria: {
            executive_escalation: "Requires immediate human VIP manager intervention",
            automated_reset: "Standard automated credential reset flow",
            technical_support: "Standard tier-2 technical triage queue",
          },
        },
      },
      urgency_score: {
        score: {
          rubric: [
            "Level 1 (Low): Casual inquiry or routine request",
            "Level 2 (Medium): Standard issue with minor operational delay",
            "Level 3 (High): Direct financial loss or team-wide blockage",
            "Level 4 (Critical): Imminent churn threat or legal / chargeback action",
          ],
        },
      },
      is_churn_risk: {
        noul: {
          description: "Is this high-value customer at immediate risk of cancelling their subscription?",
        },
      },
    },
  },
  {
    id: "content-safety",
    name: "Content Moderation",
    description: "Classifies toxic comments, harassment level, and auto-flagging.",
    state: "User Comment: 'Whoever developed this hideous trash update should be publicly fired and never allowed near a keyboard again. You all are complete frauds!'",
    questions: {
      action: {
        choice: {
          criteria: {
            allow: "Harmless criticism, frustration, or venting without personal threats",
            flag_warning: "Aggressive or borderline abusive language requiring warning",
            delete_ban: "Severe targeted harassment or hateful conduct",
          },
        },
      },
      hostility_level: {
        score: {
          rubric: [
            "Safe: Constructive or neutral",
            "Mild: Emotional venting or sarcastic",
            "Aggressive: Insulting or inflammatory language",
            "Severe: Explicit threats or abusive hate speech",
          ],
        },
      },
      needs_human_moderator: {
        noul: {
          description: "Does this comment require review by a human safety moderator?",
        },
      },
    },
  },
  {
    id: "code-review",
    name: "PR Code Review",
    description: "Evaluates pull request readiness, risk score, and test coverage sufficiency.",
    state: "Pull Request: #482 Add Redis distributed cache layer for user permissions.\nDiff summary: 14 files changed, +380 / -45 lines.\nNotes: Added caching on permission lookups with 60s TTL. Cache invalidation on role update not yet implemented in all admin paths. Test coverage for modified lines: 42%.",
    questions: {
      review_verdict: {
        choice: {
          criteria: {
            approve: "Clean implementation, ready for production merge",
            request_changes: "Functional gaps, stale cache risk, or missing tests require changes",
            block_redesign: "Fundamental architecture flaw requiring complete redesign",
          },
        },
      },
      readiness_score: {
        score: {
          rubric: [
            "Draft: Incomplete functionality",
            "Needs Polish: Works in happy path but lacks edge case handling",
            "Merge Candidate: Sound architecture with minor remarks",
            "Production Grade: Fully tested, safe cache invalidation and rollback plan",
          ],
        },
      },
      security_leak_risk: {
        noul: {
          description: "Is there a potential security or privilege escalation risk due to stale permissions cache?",
        },
      },
    },
  },
  {
    id: "transaction-fraud",
    name: "Financial Risk",
    description: "Real-time payment fraud detection, risk scoring, and authorization gate.",
    state: "Transaction ID: tx_99214\nAmount: $1,850.00 USD\nCard Origin: Germany | IP Location: Nigeria | Device Fingerprint: New Linux VM (User-Agent: curl/7.88)\nAccount Age: 2 hours | Shipping Address mismatch: Billing DE, Shipping NG.\nCardholder 3DS: Not enrolled.",
    questions: {
      decision: {
        choice: {
          criteria: {
            approve: "Legitimate low-risk transaction",
            challenge_2fa: "Suspicious factors requiring biometric or SMS step-up auth",
            block_fraud: "High probability fraud, block and alert security team",
          },
        },
      },
      risk_tier: {
        score: {
          rubric: [
            "Tier 1: Minimal risk, verified historical patterns",
            "Tier 2: Elevated risk, minor geolocation mismatch",
            "Tier 3: High risk, multiple red flags (IP mismatch, new device)",
            "Tier 4: Critical fraud probability, automated bot or stolen credential pattern",
          ],
        },
      },
      is_stolen_card_signature: {
        noul: {
          description: "Does this transaction pattern strongly match stolen credential fraud?",
        },
      },
    },
  },
];

interface ChatMessageItem {
  id: string;
  role: "system" | "user" | "assistant";
  content: string;
  reasoning_content?: string;
  latency_ms?: number;
  tokens?: { prompt: number; completion: number; total: number };
}

export const PlaygroundPage: React.FC = () => {
  const { t } = useI18n();
  // Data State
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routes, setRoutes] = useState<RoutingProfile[]>([]);
  const [fusions, setFusions] = useState<FusionProfile[]>([]);
  const [judges, setJudges] = useState<JudgeProfile[]>([]);
  const [keys, setKeys] = useState<RouterApiKey[]>([]);

  // Mode: "single" prompt, "chat" multi-turn, "compare" side-by-side
  const [mode, setMode] = useState<PlaygroundMode>("chat");

  // Targets
  const [targetA, setTargetA] = useState<string>("");
  const [targetB, setTargetB] = useState<string>("");
  const [selectedKey, setSelectedKey] = useState<string>("");

  // Target Filter & Search
  const [targetSearch, setTargetSearch] = useState("");
  const [targetTypeFilter, setTargetTypeFilter] = useState<"all" | "models" | "routes" | "fusion" | "judge">("all");

  // Generation Parameters
  const [systemPrompt, setSystemPrompt] = useState("You are an intelligent, helpful AI coding assistant.");
  const [userPrompt, setUserPrompt] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [topP, setTopP] = useState(1.0);
  const [isStream, setIsStream] = useState(true);

  // Thinking / Reasoning Level State
  const [thinkingEffortA, setThinkingEffortA] = useState<ThinkingEffort>("auto");
  const [customThinkingA, setCustomThinkingA] = useState("8192");
  const [thinkingEffortB, setThinkingEffortB] = useState<ThinkingEffort>("auto");
  const [customThinkingB, setCustomThinkingB] = useState("8192");

  // Chat History
  const [chatMessages, setChatMessages] = useState<ChatMessageItem[]>([
    {
      id: "init-1",
      role: "assistant",
      content: "Hello! I am ready to assist. How can I help you today?",
    },
  ]);

  // Single Response Output
  const [loadingA, setLoadingA] = useState(false);
  const [responseContentA, setResponseContentA] = useState("");
  const [reasoningContentA, setReasoningContentA] = useState("");
  const [responseMetaA, setResponseMetaA] = useState<any>(null);
  const [errorA, setErrorA] = useState<string | null>(null);

  // Compare Response B Output
  const [loadingB, setLoadingB] = useState(false);
  const [responseContentB, setResponseContentB] = useState("");
  const [reasoningContentB, setReasoningContentB] = useState("");
  const [responseMetaB, setResponseMetaB] = useState<any>(null);
  const [errorB, setErrorB] = useState<string | null>(null);

  // Abort Controllers
  const abortControllerRefA = useRef<AbortController | null>(null);
  const abortControllerRefB = useRef<AbortController | null>(null);

  // UI state
  const [copiedResponseA, setCopiedResponseA] = useState(false);
  const [copiedResponseB, setCopiedResponseB] = useState(false);
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [codeTab, setCodeTab] = useState<"python" | "curl" | "node">("python");
  const [copiedCode, setCopiedCode] = useState(false);

  // Jev (System One) Mode State
  const [jevState, setJevState] = useState<string>(JEV_PRESETS[0].state);
  const [jevQuestions, setJevQuestions] = useState<Record<string, JevQuestion>>(JEV_PRESETS[0].questions);
  const [jevRawJson, setJevRawJson] = useState<string>(() => JSON.stringify(JEV_PRESETS[0].questions, null, 2));
  const [jevEditorMode, setJevEditorMode] = useState<"visual" | "json">("visual");
  const [jevLoading, setJevLoading] = useState(false);
  const [jevResponse, setJevResponse] = useState<JevResponse | null>(null);
  const [jevError, setJevError] = useState<string | null>(null);
  const [jevActiveTab, setJevActiveTab] = useState<"results" | "json">("results");
  const [copiedJevJson, setCopiedJevJson] = useState(false);

  // Quick prompt presets
  const presets = [
    { label: "💻 Code Generation", prompt: "Write a fast prime sieve function in Python with Sieve of Eratosthenes." },
    { label: "🔍 Bug Analysis", prompt: "Find potential race conditions and memory leaks in this code: ..." },
    { label: "📝 Concise Summary", prompt: "Explain in 3 short bullet points the difference between synchronous and asynchronous I/O." },
    { label: "🧮 Logic Riddle", prompt: "A farmer has 17 sheep, all but 9 ran away. How many sheep are left? Explain your reasoning." },
    { label: "⚡ Quick Ping", prompt: "Respond with one single word: 'OK'." },
  ];

  const loadData = async () => {
    try {
      const [m, p, r, f, j, k] = await Promise.all([
        apiRequest<DiscoveredModel[]>("/api/admin/models"),
        apiRequest<Provider[]>("/api/admin/providers"),
        apiRequest<RoutingProfile[]>("/api/admin/routes"),
        apiRequest<FusionProfile[]>("/api/admin/fusion"),
        apiRequest<JudgeProfile[]>("/api/admin/judges"),
        apiRequest<RouterApiKey[]>("/api/admin/keys"),
      ]);
      setModels(m);
      setProviders(p);
      setRoutes(r);
      setFusions(f);
      setJudges(j);
      setKeys(k);

      // Default Target A
      const hiddenIds = getHiddenModelIds();
      const visibleModels = getVisibleModels(m, hiddenIds);

      const urlParams = new URLSearchParams(window.location.search);
      const queryModel = urlParams.get("model");
      const replayDataStr = sessionStorage.getItem("replay_log_data");
      if (replayDataStr) {
        try {
          const replay = JSON.parse(replayDataStr);
          sessionStorage.removeItem("replay_log_data");
          if (replay.model) {
            setTargetA(replay.model);
            if (replay.model.startsWith("fusion/")) {
              setTargetTypeFilter("fusion");
            } else if (replay.model.startsWith("judge/") || replay.model.startsWith("smart/")) {
              setTargetTypeFilter("judge");
            } else if (replay.model.startsWith("route/")) {
              setTargetTypeFilter("routes");
            } else {
              setTargetTypeFilter("models");
            }
          }
          if (replay.prompt) {
            setUserPrompt(replay.prompt);
            setChatInput(replay.prompt);
          }
        } catch (e) {
          console.error("Failed to parse replay_log_data", e);
        }
      } else if (queryModel) {
        setTargetA(queryModel);
        if (queryModel.startsWith("fusion/")) {
          setTargetTypeFilter("fusion");
        } else if (queryModel.startsWith("judge/") || queryModel.startsWith("smart/")) {
          setTargetTypeFilter("judge");
        } else if (queryModel.startsWith("route/")) {
          setTargetTypeFilter("routes");
        } else {
          setTargetTypeFilter("models");
        }
      } else if (r.length > 0 && r[0].enabled) {
        setTargetA(`route/${r[0].slug}`);
      } else if (f.length > 0 && f[0].enabled) {
        setTargetA(`fusion/${f[0].slug}`);
      } else if (j.length > 0 && j[0].enabled) {
        setTargetA(`judge/${j[0].slug}`);
      } else if (visibleModels.length > 0) {
        setTargetA(visibleModels[0].canonical_slug);
      }

      // Default Target B for comparison
      if (visibleModels.length > 1) {
        setTargetB(visibleModels[1].canonical_slug);
      } else if (visibleModels.length > 0) {
        setTargetB(visibleModels[0].canonical_slug);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filtered and grouped visible models
  const visibleProviderGroups = useMemo(() => {
    const hiddenIds = getHiddenModelIds();
    return groupModelsByProvider(models, providers, true, hiddenIds);
  }, [models, providers]);

  // Combined searchable target items
  const allTargets = useMemo(() => {
    const list: { id: string; name: string; type: "route" | "fusion" | "judge" | "model"; group: string; subtitle?: string }[] = [];

    // Routes
    routes.filter((r) => r.enabled).forEach((r) => {
      list.push({
        id: `route/${r.slug}`,
        name: `route/${r.slug}`,
        type: "route",
        group: "Routing Profiles",
        subtitle: `${r.candidates.length} candidates (Fallback)`,
      });
    });

    // Fusions
    fusions.filter((f) => f.enabled).forEach((f) => {
      list.push({
        id: `fusion/${f.slug}`,
        name: `fusion/${f.slug}`,
        type: "fusion",
        group: "Fusion Profiles",
        subtitle: `Judge: ${f.judge_model_name} (${f.strategy})`,
      });
    });

    // Judges
    judges.filter((j) => j.enabled).forEach((j) => {
      list.push({
        id: `judge/${j.slug}`,
        name: `judge/${j.slug}`,
        type: "judge",
        group: "Judge Profiles",
        subtitle: `Judge: ${j.judge_model_name} (${j.candidates.length} candidates)`,
      });
    });

    // Direct Models
    visibleProviderGroups.forEach(({ provider, models: pModels }) => {
      pModels.forEach((m) => {
        list.push({
          id: m.canonical_slug,
          name: m.canonical_slug,
          type: "model",
          group: provider.name,
          subtitle: m.display_name && m.display_name !== m.canonical_slug ? m.display_name : undefined,
        });
      });
    });

    return list;
  }, [routes, fusions, judges, visibleProviderGroups]);

  // Filtered targets based on search & category
  const filteredTargets = useMemo(() => {
    return allTargets.filter((item) => {
      if (targetTypeFilter === "routes" && item.type !== "route") return false;
      if (targetTypeFilter === "fusion" && item.type !== "fusion") return false;
      if (targetTypeFilter === "judge" && item.type !== "judge") return false;
      if (targetTypeFilter === "models" && item.type !== "model") return false;
      if (!targetSearch.trim()) return true;
      const q = targetSearch.toLowerCase();
      return (
        item.name.toLowerCase().includes(q) ||
        item.group.toLowerCase().includes(q) ||
        (item.subtitle && item.subtitle.toLowerCase().includes(q))
      );
    });
  }, [allTargets, targetTypeFilter, targetSearch]);

  // Auto-sync targetA when category filter changes or search filters out the currently selected target
  useEffect(() => {
    if (filteredTargets.length > 0 && !filteredTargets.some((t) => t.id === targetA)) {
      setTargetA(filteredTargets[0].id);
    }
  }, [filteredTargets, targetA]);

  const getTargetInfo = (targetId: string) => {
    return allTargets.find((t) => t.id === targetId);
  };

  const supportsSampling = (targetId: string) => {
    const model = models.find((m) => m.canonical_slug === targetId || m.provider_model_id === targetId);
    const provider = providers.find((p) => p.id === model?.provider_id);
    return !targetId.startsWith("codex_cli/") && provider?.configuration?.module_id !== "codex_cli";
  };
  const samplingDisabled = !supportsSampling(targetA) && (mode !== "compare" || !supportsSampling(targetB));

  // Check if a model/route supports thinking / reasoning
  const isReasoningName = (name: string): boolean => {
    if (!name) return false;
    const n = name.toLowerCase();
    return (
      n.includes("think") ||
      n.includes("reason") ||
      n.includes("r1") ||
      n.includes("o1") ||
      n.includes("o3") ||
      n.includes("o4") ||
      n.includes("3-7") ||
      n.includes("3.7") ||
      n.includes("2.5-pro") ||
      n.includes("qwq") ||
      n.includes("gemma-4") ||
      n.includes("gemma4") ||
      n.includes("thought")
    );
  };

  const checkModelSupportsThinking = (targetId: string): boolean => {
    if (!targetId) return false;
    if (targetId.startsWith("route/")) {
      const slug = targetId.replace("route/", "");
      const r = routes.find((x) => x.slug === slug);
      if (r) {
        return r.candidates.some((c) => {
          if (c.model_name && isReasoningName(c.model_name)) return true;
          if (c.canonical_slug && isReasoningName(c.canonical_slug)) return true;
          return false;
        });
      }
      return false;
    }
    if (targetId.startsWith("fusion/") || targetId.startsWith("judge/") || targetId.startsWith("smart/")) {
      return false;
    }
    const m = models.find((x) => x.canonical_slug === targetId || x.provider_model_id === targetId);
    if (m) {
      if (m.capabilities?.reasoning === true) return true;
      return isReasoningName(m.provider_model_id) || isReasoningName(m.canonical_slug) || isReasoningName(m.display_name);
    }
    return isReasoningName(targetId);
  };

  const supportsThinkingA = useMemo(() => checkModelSupportsThinking(targetA), [targetA, models, routes]);
  const supportsThinkingB = useMemo(() => checkModelSupportsThinking(targetB), [targetB, models, routes]);

  // Helper to parse <think>...</think>, <thought>...</thought>, <reasoning>...</reasoning> from output text
  const parseThinking = (text: string, explicitReasoning: string) => {
    let thought = explicitReasoning ? explicitReasoning.trim() : "";
    let mainContent = text || "";

    // Search for opening thinking/reasoning tags
    const tagMatch = mainContent.match(/<(think|thought|reasoning)>/i);
    if (tagMatch && tagMatch.index !== undefined) {
      const tagName = tagMatch[1].toLowerCase();
      const closeTag = `</${tagName}>`;
      const openTagIndex = tagMatch.index;
      const openTagLength = tagMatch[0].length;

      const beforeTag = mainContent.slice(0, openTagIndex).trim();
      const afterOpenTag = mainContent.slice(openTagIndex + openTagLength);

      const closeIndex = afterOpenTag.toLowerCase().indexOf(closeTag);
      if (closeIndex !== -1) {
        // Tag is closed
        const extractedThought = afterOpenTag.slice(0, closeIndex).trim();
        const afterClose = afterOpenTag.slice(closeIndex + closeTag.length).trim();
        if (!thought) {
          thought = extractedThought;
        } else {
          thought = `${thought}\n\n${extractedThought}`.trim();
        }
        mainContent = beforeTag ? `${beforeTag}\n\n${afterClose}`.trim() : afterClose;
      } else {
        // Tag is open (still streaming or cut off by max_tokens limit)
        const extractedThought = afterOpenTag.trim();
        if (!thought) {
          thought = extractedThought;
        } else {
          thought = `${thought}\n\n${extractedThought}`.trim();
        }
        mainContent = beforeTag;
      }
    }

    return { thought, mainContent };
  };

  const requestHeaders = (): Record<string, string> => {
    const token = localStorage.getItem("myairouter_token");
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(selectedKey ? { "X-Router-Key-Id": String(selectedKey) } : {}),
    };
  };

  // Execute request to a target
  const executeTargetRequest = async (
    targetId: string,
    messages: { role: string; content: string }[],
    isCompareB: boolean = false
  ) => {
    const setLoad = isCompareB ? setLoadingB : setLoadingA;
    const setContent = isCompareB ? setResponseContentB : setResponseContentA;
    const setReasoning = isCompareB ? setReasoningContentB : setReasoningContentA;
    const setMeta = isCompareB ? setResponseMetaB : setResponseMetaA;
    const setErr = isCompareB ? setErrorB : setErrorA;
    const effort = isCompareB ? thinkingEffortB : thinkingEffortA;
    const customEff = isCompareB ? customThinkingB : customThinkingA;
    const supportsThinking = checkModelSupportsThinking(targetId);

    const controller = new AbortController();

    if (isCompareB) {
      abortControllerRefB.current = controller;
    } else {
      abortControllerRefA.current = controller;
    }

    setLoad(true);
    setContent("");
    setReasoning("");
    setMeta(null);
    setErr(null);

    const t0 = performance.now();
    const headers = requestHeaders();

    const payload: Record<string, any> = {
      model: targetId,
      messages,
      ...(supportsSampling(targetId) ? { temperature, top_p: topP } : {}),
      max_tokens: maxTokens,
      stream: isStream,
    };

    if (isStream) payload.stream_options = { include_usage: true };

    // Apply Reasoning Effort parameter (reasoning_effort) if supported
    if (supportsThinking && effort !== "off") {
      if (effort !== "auto") {
        const effVal = effort === "custom" ? (customEff.trim() || "medium") : effort;
        payload.reasoning_effort = effVal;
        // If custom effort is a numeric token count, also supply thinking object for Anthropic
        const numTokens = parseInt(effVal, 10);
        if (!isNaN(numTokens) && numTokens > 0) {
          payload.thinking = { type: "enabled", budget_tokens: numTokens };
        }
      }
    } else if (supportsThinking && effort === "off") {
      payload.reasoning_effort = "none";
      payload.thinking = { type: "disabled" };
    }

    try {
      if (isStream) {
        const res = await fetch("/v1/chat/completions", {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
          signal: controller.signal,
        });

        if (res.status === 401) expireSession();
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error?.message || `HTTP ${res.status}`);
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder("utf-8");
        let accumulated = "";
        let accumulatedReasoning = "";
        let usage: any = null;

        if (reader) {
          let carry = "";
          const consumeEvent = (event: string) => {
            const dataStr = event
              .split(/\r?\n/)
              .filter((line) => line.startsWith("data:"))
              .map((line) => line.slice(5).trimStart())
              .join("\n");
            if (!dataStr || dataStr === "[DONE]") return;

            const parsed = JSON.parse(dataStr);
            if (parsed.error) throw new Error(parsed.error.message || "Stream failed");
            if (parsed.usage) usage = parsed.usage;
            const delta = parsed.choices?.[0]?.delta?.content;
            const rDelta = parsed.choices?.[0]?.delta?.reasoning_content;
            if (rDelta) {
              accumulatedReasoning += rDelta;
              setReasoning(accumulatedReasoning);
            }
            if (delta) {
              accumulated += delta;
              setContent(accumulated);
            }
          };

          try {
            while (true) {
              const { done, value } = await reader.read();
              carry += done ? decoder.decode() : decoder.decode(value, { stream: true });
              const events = carry.split(/\r?\n\r?\n/);
              carry = events.pop() ?? "";
              for (const event of events) {
                consumeEvent(event);
              }
              if (done) break;
            }
            if (carry.trim()) {
              consumeEvent(carry);
            }
          } finally {
            await reader.cancel().catch(() => {});
            reader.releaseLock();
          }
        } else {
          throw new Error("Streaming response body is unavailable");
        }

        const latency = Math.round(performance.now() - t0);
        const tokenCount = usage?.completion_tokens;
        const tokensPerSec = typeof tokenCount === "number" && latency > 0
          ? ((tokenCount / latency) * 1000).toFixed(1) : null;

        setMeta({
          latency_ms: latency,
          tokens_per_sec: tokensPerSec,
          token_count: tokenCount,
          usage,
          mode: targetId.startsWith("route/")
            ? "PRIORITY"
            : targetId.startsWith("fusion/")
            ? "FUSION"
            : targetId.startsWith("judge/") || targetId.startsWith("smart/")
            ? "JUDGE"
            : "DIRECT",
        });
        return { content: accumulated, reasoning: accumulatedReasoning };
      } else {
        const res = await fetch("/v1/chat/completions", {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
          signal: controller.signal,
        });

        const latency = Math.round(performance.now() - t0);
        const data = await res.json();

        if (res.status === 401) expireSession();
        if (!res.ok) {
          throw new Error(data.error?.message || `HTTP ${res.status}`);
        }

        const choice = data.choices?.[0];
        const content = choice?.message?.content || "";
        const reasoning = choice?.message?.reasoning_content || "";

        setContent(content);
        setReasoning(reasoning);

        const compTokens = data.usage?.completion_tokens || 0;
        const tokensPerSec = latency > 0 ? ((compTokens / latency) * 1000).toFixed(1) : "0";

        setMeta({
          latency_ms: latency,
          model: data.model,
          usage: data.usage,
          tokens_per_sec: tokensPerSec,
          mode: targetId.startsWith("route/")
            ? "PRIORITY"
            : targetId.startsWith("fusion/")
            ? "FUSION"
            : targetId.startsWith("judge/") || targetId.startsWith("smart/")
            ? "JUDGE"
            : "DIRECT",
        });
        return { content, reasoning };
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        setErr("Request aborted by user.");
      } else {
        setErr(err.message || "Request failed");
      }
      return null;
    } finally {
      setLoad(false);
    }
  };

  // Stop Generation
  const handleStop = (isCompareB: boolean = false) => {
    if (isCompareB && abortControllerRefB.current) {
      abortControllerRefB.current.abort();
    } else if (!isCompareB && abortControllerRefA.current) {
      abortControllerRefA.current.abort();
    }
  };

  const handleStopAll = () => {
    if (abortControllerRefA.current) abortControllerRefA.current.abort();
    if (abortControllerRefB.current) abortControllerRefB.current.abort();
  };

  // Send Handler for Single / Compare Mode
  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetA || !userPrompt.trim()) return;

    const messages = [];
    if (systemPrompt.trim()) {
      messages.push({ role: "system", content: systemPrompt.trim() });
    }
    messages.push({ role: "user", content: userPrompt.trim() });

    if (mode === "compare" && targetB) {
      await Promise.all([
        executeTargetRequest(targetA, messages, false),
        executeTargetRequest(targetB, messages, true),
      ]);
    } else {
      await executeTargetRequest(targetA, messages, false);
    }
  };

  // Send Handler for Chat Mode
  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !targetA || loadingA) return;

    const userText = chatInput.trim();
    setChatInput("");

    const newMsg: ChatMessageItem = {
      id: `usr-${Date.now()}`,
      role: "user",
      content: userText,
    };

    const updatedHistory = [...chatMessages, newMsg];
    setChatMessages(updatedHistory);

    // Build OpenAI messages array
    const apiMessages: { role: string; content: string }[] = [];
    if (systemPrompt.trim()) {
      apiMessages.push({ role: "system", content: systemPrompt.trim() });
    }
    for (const m of updatedHistory) {
      apiMessages.push({ role: m.role, content: m.content });
    }

    const t0 = performance.now();
    const result = await executeTargetRequest(targetA, apiMessages, false);

    if (result) {
      const latency = Math.round(performance.now() - t0);
      setChatMessages((prev) => [
        ...prev,
        {
          id: `ast-${Date.now()}`,
          role: "assistant",
          content: result.content,
          reasoning_content: result.reasoning,
          latency_ms: latency,
        },
      ]);
    }
  };

  const handleCopyText = (text: string, isB: boolean = false) => {
    navigator.clipboard.writeText(text);
    if (isB) {
      setCopiedResponseB(true);
      setTimeout(() => setCopiedResponseB(false), 2000);
    } else {
      setCopiedResponseA(true);
      setTimeout(() => setCopiedResponseA(false), 2000);
    }
  };

  // Jev helper handlers
  const handleLoadJevPreset = (preset: JevPreset) => {
    setJevState(preset.state);
    setJevQuestions(preset.questions);
    setJevRawJson(JSON.stringify(preset.questions, null, 2));
    setJevResponse(null);
    setJevError(null);
  };

  const handleAddJevQuestion = (type: "choice" | "score" | "noul") => {
    const baseKey = type === "choice" ? "choice_q" : type === "score" ? "score_q" : "noul_q";
    let newKey = baseKey;
    let counter = 1;
    while (jevQuestions[newKey]) {
      newKey = `${baseKey}_${counter++}`;
    }

    let qObj: JevQuestion;
    if (type === "choice") {
      qObj = {
        choice: {
          criteria: {
            option_a: "First criterion description",
            option_b: "Second criterion description",
          },
        },
      };
    } else if (type === "score") {
      qObj = {
        score: {
          rubric: ["Level 1: Low", "Level 2: Medium", "Level 3: High"],
        },
      };
    } else {
      qObj = {
        noul: {
          description: "Binary True / False judgment criterion",
        },
      };
    }

    const updated = { ...jevQuestions, [newKey]: qObj };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleRemoveJevQuestion = (qKey: string) => {
    const updated = { ...jevQuestions };
    delete updated[qKey];
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleUpdateJevQuestionKey = (oldKey: string, newKey: string) => {
    if (!newKey.trim() || oldKey === newKey) return;
    const entries = Object.entries(jevQuestions);
    const updated: Record<string, JevQuestion> = {};
    for (const [k, v] of entries) {
      if (k === oldKey) {
        updated[newKey.trim()] = v;
      } else {
        updated[k] = v;
      }
    }
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleAddChoiceCriterion = (qKey: string) => {
    const q = jevQuestions[qKey];
    if (!q || !("choice" in q)) return;
    let newOptKey = "option";
    let counter = 1;
    while (q.choice.criteria[`${newOptKey}_${counter}`]) {
      counter++;
    }
    const finalKey = `${newOptKey}_${counter}`;
    const updatedCriteria = { ...q.choice.criteria, [finalKey]: "New criterion description" };
    const updated = {
      ...jevQuestions,
      [qKey]: { choice: { ...q.choice, criteria: updatedCriteria } },
    };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleUpdateChoiceCriterion = (qKey: string, optKey: string, optVal: string) => {
    const q = jevQuestions[qKey];
    if (!q || !("choice" in q)) return;
    const updatedCriteria = { ...q.choice.criteria, [optKey]: optVal };
    const updated = {
      ...jevQuestions,
      [qKey]: { choice: { ...q.choice, criteria: updatedCriteria } },
    };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleRemoveChoiceCriterion = (qKey: string, optKey: string) => {
    const q = jevQuestions[qKey];
    if (!q || !("choice" in q)) return;
    const updatedCriteria = { ...q.choice.criteria };
    delete updatedCriteria[optKey];
    const updated = {
      ...jevQuestions,
      [qKey]: { choice: { ...q.choice, criteria: updatedCriteria } },
    };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleAddScoreLevel = (qKey: string) => {
    const q = jevQuestions[qKey];
    if (!q || !("score" in q)) return;
    const updatedRubric = [...q.score.rubric, `Level ${q.score.rubric.length + 1}: Description`];
    const updated = {
      ...jevQuestions,
      [qKey]: { score: { ...q.score, rubric: updatedRubric } },
    };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleUpdateScoreLevel = (qKey: string, index: number, val: string) => {
    const q = jevQuestions[qKey];
    if (!q || !("score" in q)) return;
    const updatedRubric = [...q.score.rubric];
    updatedRubric[index] = val;
    const updated = {
      ...jevQuestions,
      [qKey]: { score: { ...q.score, rubric: updatedRubric } },
    };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleRemoveScoreLevel = (qKey: string, index: number) => {
    const q = jevQuestions[qKey];
    if (!q || !("score" in q)) return;
    const updatedRubric = q.score.rubric.filter((_, i) => i !== index);
    const updated = {
      ...jevQuestions,
      [qKey]: { score: { ...q.score, rubric: updatedRubric } },
    };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleUpdateNoulDescription = (qKey: string, desc: string) => {
    const q = jevQuestions[qKey];
    if (!q || !("noul" in q)) return;
    const updated = {
      ...jevQuestions,
      [qKey]: { noul: { ...q.noul, description: desc } },
    };
    setJevQuestions(updated);
    setJevRawJson(JSON.stringify(updated, null, 2));
  };

  const handleRunJevDecision = async () => {
    if (!targetA) {
      setJevError("Please select a target model first.");
      return;
    }
    setJevLoading(true);
    setJevError(null);
    const t0 = performance.now();
    try {
      let questionsPayload = jevQuestions;
      if (jevEditorMode === "json") {
        try {
          questionsPayload = JSON.parse(jevRawJson);
        } catch (jsonErr: any) {
          setJevError("Invalid JSON in Questions editor: " + jsonErr.message);
          setJevLoading(false);
          return;
        }
      }

      const payload: JevRequest = {
        model: targetA,
        state: jevState,
        questions: questionsPayload,
      };

      const headers = requestHeaders();

      const res = await apiRequest<JevResponse>("/v1/systemone", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const lat = Math.round(performance.now() - t0);
      setJevResponse({
        ...res,
        latency_ms: res.latency_ms || lat,
      });
    } catch (err: any) {
      setJevError(err.message || "Decision evaluation failed");
    } finally {
      setJevLoading(false);
    }
  };

  // Generate Export Code
  const getExportCode = () => {
    const token = "sk-router-YOUR-KEY";
    const target = targetA || "google-ai/gemini-2.5-flash";

    if (mode === "jev") {
      let questionsPayload = jevQuestions;
      if (jevEditorMode === "json") {
        try {
          questionsPayload = JSON.parse(jevRawJson);
        } catch {}
      }
      const jevBody = {
        model: targetA || "typesafe/jev-latest",
        state: jevState,
        questions: questionsPayload,
      };

      if (codeTab === "curl") {
        return `curl http://localhost:8000/v1/systemone \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(jevBody, null, 2)}'`;
      }

      if (codeTab === "python") {
        return `import requests

url = "http://localhost:8000/v1/systemone"
headers = {
    "Authorization": "Bearer ${token}",
    "Content-Type": "application/json"
}
payload = ${JSON.stringify(jevBody, null, 4)}

response = requests.post(url, json=payload, headers=headers)
print(response.json())`;
      }

      return `import fetch from "node-fetch";

const response = await fetch("http://localhost:8000/v1/systemone", {
  method: "POST",
  headers: {
    "Authorization": "Bearer ${token}",
    "Content-Type": "application/json"
  },
  body: JSON.stringify(${JSON.stringify(jevBody, null, 2)})
});

const data = await response.json();
console.log(JSON.stringify(data, null, 2));`;
    }

    const promptText = mode === "chat" ? (chatInput || "Hello!") : (userPrompt || "Hello!");
    const msgs = [];
    if (systemPrompt) msgs.push({ role: "system", content: systemPrompt });
    msgs.push({ role: "user", content: promptText });

    const extraKwargs: Record<string, any> = {};
    if (supportsThinkingA && thinkingEffortA !== "off" && thinkingEffortA !== "auto") {
      extraKwargs["reasoning_effort"] = thinkingEffortA === "custom" ? (customThinkingA.trim() || "medium") : thinkingEffortA;
    }

    if (codeTab === "python") {
      return `from openai import OpenAI

client = OpenAI(
    api_key="${token}",
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="${target}",
    messages=${JSON.stringify(msgs, null, 4)},${supportsSampling(target) ? `\n    temperature=${temperature},` : ""}
    max_tokens=${maxTokens},
    stream=${isStream ? "True" : "False"}${
      extraKwargs.reasoning_effort ? `,\n    extra_body={"reasoning_effort": "${extraKwargs.reasoning_effort}"}` : ""
    }
)

${
  isStream
    ? `for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")`
    : `print(response.choices[0].message.content)`
}`;
    }

    if (codeTab === "curl") {
      const curlBody: any = {
        model: target,
        messages: msgs,
        ...(supportsSampling(target) ? { temperature } : {}),
        max_tokens: maxTokens,
        stream: isStream,
        ...extraKwargs,
      };
      return `curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(curlBody, null, 2)}'`;
    }

    return `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "${token}",
  baseURL: "http://localhost:8000/v1",
});

async function main() {
  const response = await client.chat.completions.create({
    model: "${target}",
    messages: ${JSON.stringify(msgs, null, 2)},${supportsSampling(target) ? `\n    temperature: ${temperature},` : ""}
    max_tokens: ${maxTokens},
    stream: ${isStream},${
      extraKwargs.reasoning_effort ? `\n    extra_body: { reasoning_effort: "${extraKwargs.reasoning_effort}" },` : ""
    }
  });

  ${
    isStream
      ? `for await (const chunk of response) {
    process.stdout.write(chunk.choices[0]?.delta?.content || "");
  }`
      : `console.log(response.choices[0].message.content);`
  }
}

main();`;
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(getExportCode());
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const isAnyLoading = loadingA || loadingB;

  // Parsed thinking for Single Mode
  const parsedA = parseThinking(responseContentA, reasoningContentA);
  const parsedB = parseThinking(responseContentB, reasoningContentB);

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-8">
      {/* Top Header & Mode Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 glass-panel card-specular rounded-2xl p-4 shadow-xl border border-white/[0.07]">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shadow-xs">
              <Terminal size={16} />
            </div>
            <h2 className="text-base font-bold text-slate-100 tracking-tight">{t.playground.title}</h2>
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {t.playground.subtitle}
          </p>
        </div>

        {/* Mode Selector & Action Buttons */}
        <div className="flex items-center gap-2.5 self-stretch sm:self-auto">
          {/* Mode Switcher */}
          <div className="flex bg-slate-950/80 p-1 rounded-xl border border-white/[0.07] text-xs">
            <button
              onClick={() => setMode("chat")}
              className={`btn-press flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition-all ${
                mode === "chat"
                  ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-xs"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
              }`}
            >
              <MessageSquare size={13} />
              Chat
            </button>
            <button
              onClick={() => setMode("single")}
              className={`btn-press flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition-all ${
                mode === "single"
                  ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-xs"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
              }`}
            >
              <Terminal size={13} />
              Single
            </button>
            <button
              onClick={() => setMode("compare")}
              className={`btn-press flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition-all ${
                mode === "compare"
                  ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-xs"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
              }`}
            >
              <Columns size={13} />
              Compare (x2)
            </button>
            <button
              onClick={() => setMode("jev")}
              className={`btn-press flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition-all ${
                mode === "jev"
                  ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white shadow-xs"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
              }`}
            >
              <Zap size={13} className={mode === "jev" ? "text-amber-300" : "text-violet-400"} />
              Jev (System One)
            </button>
          </div>

          {/* Code Export Button */}
          <button
            onClick={() => setShowCodeModal(true)}
            className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.05] hover:bg-white/[0.1] text-slate-200 rounded-xl text-xs font-semibold border border-white/[0.08] transition-all shadow-xs"
            title="Export code (cURL / Python / Node.js)"
          >
            <Code size={13} className="text-indigo-400" />
            Code
          </button>
        </div>
      </div>

      {/* Main Grid: Controls on Left, Output on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Sidebar: Controls & Parameters (4 Cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Target A Selector Card */}
          <div className="glass-panel card-specular rounded-2xl p-4 space-y-3 shadow-xl border border-white/[0.07]">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Boxes size={14} className="text-indigo-400" />
                {mode === "compare" ? "Target Model A" : t.playground.selectModel}
              </label>
              <span className="text-[10px] text-slate-400 font-mono">
                {getTargetInfo(targetA)?.type.toUpperCase() || "DIRECT"}
              </span>
            </div>

            {/* Target Category Tabs */}
            <div className="grid grid-cols-5 gap-1 p-1 bg-slate-950/80 rounded-xl border border-white/[0.06] text-[10px] font-medium text-slate-400">
              <button
                type="button"
                onClick={() => setTargetTypeFilter("all")}
                className={`btn-press py-1.5 rounded-lg text-center transition-all ${
                  targetTypeFilter === "all" ? "bg-slate-800 text-slate-100 font-bold shadow-xs" : "hover:text-slate-200"
                }`}
              >
                {t.common.all}
              </button>
              <button
                type="button"
                onClick={() => {
                  setTargetTypeFilter("models");
                  const firstModel = allTargets.find((t) => t.type === "model");
                  if (firstModel && (!targetA || targetA.startsWith("route/") || targetA.startsWith("fusion/") || targetA.startsWith("judge/") || targetA.startsWith("smart/"))) {
                    setTargetA(firstModel.id);
                  }
                }}
                className={`btn-press py-1.5 rounded-lg text-center transition-all ${
                  targetTypeFilter === "models" ? "bg-slate-800 text-slate-100 font-bold shadow-xs" : "hover:text-slate-200"
                }`}
              >
                Models
              </button>
              <button
                type="button"
                onClick={() => {
                  setTargetTypeFilter("routes");
                  const firstRoute = allTargets.find((t) => t.type === "route");
                  if (firstRoute && (!targetA || !targetA.startsWith("route/"))) {
                    setTargetA(firstRoute.id);
                  }
                }}
                className={`btn-press py-1.5 rounded-lg text-center transition-all ${
                  targetTypeFilter === "routes" ? "bg-slate-800 text-slate-100 font-bold shadow-xs" : "hover:text-slate-200"
                }`}
              >
                Routes
              </button>
              <button
                type="button"
                onClick={() => {
                  setTargetTypeFilter("fusion");
                  const firstFusion = allTargets.find((t) => t.type === "fusion");
                  if (firstFusion && (!targetA || !targetA.startsWith("fusion/"))) {
                    setTargetA(firstFusion.id);
                  }
                }}
                className={`btn-press py-1.5 rounded-lg text-center transition-all ${
                  targetTypeFilter === "fusion" ? "bg-purple-900/60 text-purple-200 font-bold shadow-xs border border-purple-700/50" : "hover:text-slate-200"
                }`}
              >
                Fusion
              </button>
              <button
                type="button"
                onClick={() => {
                  setTargetTypeFilter("judge");
                  const firstJudge = allTargets.find((t) => t.type === "judge");
                  if (firstJudge && (!targetA || (!targetA.startsWith("judge/") && !targetA.startsWith("smart/")))) {
                    setTargetA(firstJudge.id);
                  }
                }}
                className={`btn-press py-1.5 rounded-lg text-center transition-all ${
                  targetTypeFilter === "judge" ? "bg-amber-900/60 text-amber-200 font-bold shadow-xs border border-amber-700/50" : "hover:text-slate-200"
                }`}
              >
                Judge
              </button>
            </div>

            {/* Target Search Box */}
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder={t.common.search + "..."}
                value={targetSearch}
                onChange={(e) => setTargetSearch(e.target.value)}
                className="w-full pl-7 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              />
              {targetSearch && (
                <button
                  onClick={() => setTargetSearch("")}
                  className="absolute right-2 top-2 text-slate-500 hover:text-slate-300"
                >
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Target Select Dropdown */}
            <select
              value={targetA}
              onChange={(e) => setTargetA(e.target.value)}
              className="w-full px-2.5 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs font-mono focus:border-indigo-500 focus:outline-none truncate"
            >
              {!filteredTargets.some((item) => item.id === targetA) && targetA && (
                <option value={targetA}>
                  [{targetA.startsWith("route/") ? "ROUTE" : targetA.startsWith("fusion/") ? "FUSION" : targetA.startsWith("judge/") || targetA.startsWith("smart/") ? "JUDGE" : "DIRECT"}] {targetA}
                </option>
              )}
              {filteredTargets.map((item) => (
                <option key={item.id} value={item.id}>
                  [{item.type === "route" ? "ROUTE" : item.type === "fusion" ? "FUSION" : item.type === "judge" ? "JUDGE" : item.group}] {item.name}
                  {item.subtitle ? ` — ${item.subtitle}` : ""}
                </option>
              ))}
            </select>

            {/* Active Selected Target Badge */}
            <div className="flex items-center justify-between text-[11px] px-2 py-1 bg-slate-950/80 rounded-lg border border-slate-800/80">
              <span className="text-slate-400 font-mono truncate mr-2">
                Selected: <span className="text-slate-200 font-semibold">{targetA || t.common.none}</span>
              </span>
              <span
                className={`text-[9px] uppercase px-1.5 py-0.5 rounded font-bold shrink-0 ${
                  targetA.startsWith("judge/") || targetA.startsWith("smart/")
                    ? "bg-amber-950 text-amber-300 border border-amber-800/70"
                    : targetA.startsWith("fusion/")
                    ? "bg-purple-950 text-purple-300 border border-purple-800/70"
                    : targetA.startsWith("route/")
                    ? "bg-indigo-950 text-indigo-300 border border-indigo-800/70"
                    : "bg-emerald-950 text-emerald-300 border border-emerald-800/70"
                }`}
              >
                {targetA.startsWith("judge/") || targetA.startsWith("smart/")
                  ? "Judge Classifier"
                  : targetA.startsWith("fusion/")
                  ? "Fusion Ensemble"
                  : targetA.startsWith("route/")
                  ? "Route Fallback"
                  : "Direct Model"}
              </span>
            </div>
          </div>

          {/* Thinking Level Card for Target A (When Supported) */}
          {supportsThinkingA && (
            <div className="bg-slate-900/90 border border-purple-900/60 rounded-xl p-3.5 space-y-2.5 shadow-sm">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-purple-200 flex items-center gap-1.5">
                  <Brain size={15} className="text-purple-400" />
                  Reasoning Effort (reasoning_effort)
                </label>
                <span className="text-[10px] bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded font-mono font-medium border border-purple-500/30">
                  reasoning_effort
                </span>
              </div>

              <p className="text-[11px] text-slate-400 leading-tight">
                Controls compute effort allocated to Chain of Thought reasoning, beyond max output token limits.
              </p>

              {/* Effort Buttons */}
              <div className="grid grid-cols-6 gap-1 p-0.5 bg-slate-950 rounded-lg border border-slate-800 text-[10px] font-medium text-slate-300">
                <button
                  type="button"
                  onClick={() => setThinkingEffortA("auto")}
                  className={`py-1 rounded text-center transition-all ${
                    thinkingEffortA === "auto"
                      ? "bg-purple-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                  title="Model default (typically medium)"
                >
                  Auto
                </button>
                <button
                  type="button"
                  onClick={() => setThinkingEffortA("low")}
                  className={`py-1 rounded text-center transition-all ${
                    thinkingEffortA === "low"
                      ? "bg-purple-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                  title="Low effort: fast response, basic checks"
                >
                  Low
                </button>
                <button
                  type="button"
                  onClick={() => setThinkingEffortA("medium")}
                  className={`py-1 rounded text-center transition-all ${
                    thinkingEffortA === "medium"
                      ? "bg-purple-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                  title="Medium effort: balanced depth and latency"
                >
                  Medium
                </button>
                <button
                  type="button"
                  onClick={() => setThinkingEffortA("high")}
                  className={`py-1 rounded text-center transition-all ${
                    thinkingEffortA === "high"
                      ? "bg-purple-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                  title="High effort: deep analysis for complex reasoning"
                >
                  High
                </button>
                <button
                  type="button"
                  onClick={() => setThinkingEffortA("off")}
                  className={`py-1 rounded text-center transition-all ${
                    thinkingEffortA === "off"
                      ? "bg-rose-900/70 text-rose-200 font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                  title="Disable reasoning (reasoning_effort: none)"
                >
                  Off
                </button>
                <button
                  type="button"
                  onClick={() => setThinkingEffortA("custom")}
                  className={`py-1 rounded text-center transition-all ${
                    thinkingEffortA === "custom"
                      ? "bg-indigo-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                  title="Custom parameter: minimal, max, xhigh or token budget"
                >
                  Custom ✏️
                </button>
              </div>

              {thinkingEffortA === "custom" && (
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[11px] text-purple-300 font-medium shrink-0">Parameter:</span>
                  <input
                    type="text"
                    value={customThinkingA}
                    onChange={(e) => setCustomThinkingA(e.target.value)}
                    placeholder="minimal, max, xhigh or 8192"
                    className="flex-1 px-2 py-1 bg-slate-950 border border-purple-500/50 rounded text-xs text-purple-100 font-mono focus:border-purple-400 focus:outline-none"
                  />
                </div>
              )}

              <div className="flex items-center justify-between text-[10px] text-purple-300 font-mono px-0.5">
                <span>API payload:</span>
                <span className="font-semibold text-slate-200">
                  {thinkingEffortA === "auto"
                    ? "auto (default)"
                    : thinkingEffortA === "low"
                    ? 'reasoning_effort: "low"'
                    : thinkingEffortA === "medium"
                    ? 'reasoning_effort: "medium"'
                    : thinkingEffortA === "high"
                    ? 'reasoning_effort: "high"'
                    : thinkingEffortA === "off"
                    ? 'reasoning_effort: "none"'
                    : thinkingEffortA === "custom"
                    ? `reasoning_effort: "${customThinkingA || 'custom'}"`
                    : "auto"}
                </span>
              </div>
            </div>
          )}

          {/* Target B Selector & Thinking (Only in Compare Mode) */}
          {mode === "compare" && (
            <div className="bg-slate-900/90 border border-purple-900/50 rounded-xl p-3.5 space-y-2 shadow-sm">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-purple-200 flex items-center gap-1.5">
                  <Columns size={14} className="text-purple-400" />
                  Target Model B (Comparison)
                </label>
                <span className="text-[10px] text-purple-300 font-mono">
                  {getTargetInfo(targetB)?.type.toUpperCase() || "DIRECT"}
                </span>
              </div>
              <select
                value={targetB}
                onChange={(e) => setTargetB(e.target.value)}
                className="w-full px-2.5 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs font-mono focus:border-purple-500 focus:outline-none truncate"
              >
                {allTargets.map((item) => (
                  <option key={`b-${item.id}`} value={item.id}>
                    [{item.type === "route" ? "ROUTE" : item.type === "fusion" ? "FUSION" : item.type === "judge" ? "JUDGE" : item.group}] {item.name}
                  </option>
                ))}
              </select>

              {/* Thinking Level for Model B */}
              {supportsThinkingB && (
                <div className="pt-2 border-t border-purple-950 space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] text-purple-300 font-medium">
                    <span className="flex items-center gap-1">
                      <Brain size={12} className="text-purple-400" />
                      Reasoning Effort for Model B:
                    </span>
                    <span className="font-mono text-[10px] font-semibold text-slate-200">
                      {thinkingEffortB === "custom" ? (customThinkingB || "CUSTOM") : thinkingEffortB.toUpperCase()}
                    </span>
                  </div>
                  <div className="grid grid-cols-6 gap-1 p-0.5 bg-slate-950 rounded-lg border border-slate-800 text-[10px]">
                    {(["auto", "low", "medium", "high", "off", "custom"] as ThinkingEffort[]).map((eff) => (
                      <button
                        key={eff}
                        type="button"
                        onClick={() => setThinkingEffortB(eff)}
                        className={`py-1 rounded text-center transition-colors ${
                          thinkingEffortB === eff ? "bg-purple-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        {eff === "auto" ? "Auto" : eff === "off" ? "Off" : eff === "custom" ? "Custom" : eff.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  {thinkingEffortB === "custom" && (
                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-[10px] text-purple-300 font-medium shrink-0">Parameter:</span>
                      <input
                        type="text"
                        value={customThinkingB}
                        onChange={(e) => setCustomThinkingB(e.target.value)}
                        placeholder="8192 or extreme"
                        className="flex-1 px-2 py-0.5 bg-slate-950 border border-purple-500/50 rounded text-[11px] text-purple-100 font-mono focus:border-purple-400 focus:outline-none"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Key & Auth Selector Card */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-2.5 shadow-sm">
            <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-emerald-400" />
              Authorization / Router API Key
            </label>
            <select
              value={selectedKey}
              onChange={(e) => setSelectedKey(e.target.value)}
              className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 text-xs focus:border-indigo-500 focus:outline-none truncate"
            >
              <option value="">Admin Session (Full Access)</option>
              {keys.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name} ({k.key_prefix}...) — {k.permissions.join(", ")}
                </option>
              ))}
            </select>
            <p className="text-[10px] text-slate-400 leading-tight">
              Select a Router API Key to verify its assigned model whitelist and permissions.
            </p>
          </div>

          {/* Mode-specific Left Sidebar Controls */}
          {mode === "jev" ? (
            <>
              {/* Jev Decision Presets Card */}
              <div className="bg-slate-900/90 border border-violet-500/30 rounded-xl p-3.5 space-y-2.5 shadow-sm">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-violet-200 flex items-center gap-1.5">
                    <Zap size={14} className="text-amber-400" />
                    Jev Decision Presets
                  </label>
                  <span className="text-[10px] text-violet-400 font-mono">System One</span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Select a pre-configured decision benchmark to test state evaluation against choice, score, and noul primitives:
                </p>
                <div className="space-y-1.5">
                  {JEV_PRESETS.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleLoadJevPreset(p)}
                      className="w-full text-left p-2.5 bg-slate-950/80 hover:bg-violet-950/40 border border-slate-800 hover:border-violet-500/40 rounded-lg transition-all group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-200 group-hover:text-violet-200">{p.name}</span>
                        <span className="text-[10px] text-slate-500 font-mono group-hover:text-violet-400">
                          {Object.keys(p.questions).length} questions
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 group-hover:text-slate-300 line-clamp-1 mt-0.5">
                        {p.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Jev Primitives Info Card */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-2.5 shadow-sm">
                <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <HelpCircle size={13} className="text-indigo-400" />
                  Jev Primitive Types
                </label>
                <div className="space-y-2 text-[11px] text-slate-400">
                  <div className="p-2 bg-slate-950/80 border border-slate-800/80 rounded-lg">
                    <div className="flex items-center gap-1.5 text-violet-300 font-semibold mb-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
                      Choice
                    </div>
                    Selects from discrete criteria and outputs full normalized probability distribution.
                  </div>
                  <div className="p-2 bg-slate-950/80 border border-slate-800/80 rounded-lg">
                    <div className="flex items-center gap-1.5 text-emerald-300 font-semibold mb-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      Score
                    </div>
                    Evaluates state against ordered rubric levels with expected continuous score.
                  </div>
                  <div className="p-2 bg-slate-950/80 border border-slate-800/80 rounded-lg">
                    <div className="flex items-center gap-1.5 text-amber-300 font-semibold mb-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      Noul
                    </div>
                    Fast binary True/False judgment on instructions with calibrated probability.
                  </div>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Generation Parameters Card */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-3.5 shadow-sm">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                    <SlidersHorizontal size={14} className="text-indigo-400" />
                    Generation Parameters
                  </label>
                </div>

                {/* Temperature Slider */}
                <div>
                  <div className="flex items-center justify-between text-xs text-slate-300 mb-1">
                    <span>{t.common.temperature}</span>
                    <span className="font-mono text-indigo-300 font-semibold">{temperature}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={2}
                    step={0.05}
                    value={temperature}
                    disabled={samplingDisabled}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full accent-indigo-500"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 pt-0.5">
                    <span>0.0 Precise</span>
                    <span>0.7 Balanced</span>
                    <span>1.5+ Creative</span>
                  </div>
                </div>

                {/* Max Tokens & Top P */}
                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-[11px] text-slate-300 mb-1">Max Tokens</label>
                    <input
                      type="number"
                      value={maxTokens}
                      onChange={(e) => setMaxTokens(parseInt(e.target.value) || 2048)}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs font-mono focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-300 mb-1">Top P: {topP}</label>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={topP}
                      disabled={samplingDisabled}
                      onChange={(e) => setTopP(parseFloat(e.target.value))}
                      className="w-full accent-indigo-500 pt-1"
                    />
                  </div>
                </div>

                {/* Stream Toggle */}
                {(!supportsSampling(targetA) || (mode === "compare" && !supportsSampling(targetB))) && (
                  <p className="text-[10px] text-slate-400">Codex CLI: temperature / top_p are not sent.</p>
                )}
                <div className="pt-1 border-t border-slate-800 flex items-center justify-between">
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isStream}
                      onChange={(e) => setIsStream(e.target.checked)}
                      className="rounded border-slate-800 text-indigo-600 focus:ring-0"
                    />
                    {t.playground.streaming}
                  </label>
                  <span className="text-[10px] text-slate-500 font-mono">{isStream ? "live stream" : "blocking"}</span>
                </div>
              </div>

              {/* Quick Presets (Chips) */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-2 shadow-sm">
                <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Sparkles size={13} className="text-amber-400" />
                  Quick Presets
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {presets.map((p, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        if (mode === "chat") {
                          setChatInput(p.prompt);
                        } else {
                          setUserPrompt(p.prompt);
                        }
                      }}
                      className="px-2 py-1 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded-md text-[11px] text-slate-300 hover:text-slate-100 transition-colors"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right Output Area (8 Cols) */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          {/* ===================== MODE 1: INTERACTIVE CHAT ===================== */}
          {mode === "chat" && (
            <div className="glass-panel card-specular rounded-2xl border border-white/[0.07] flex flex-col h-[740px] shadow-xl overflow-hidden">
              {/* Chat Header Bar */}
              <div className="px-5 py-3 border-b border-white/[0.06] flex items-center justify-between bg-slate-950/40">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-bold text-slate-200">Conversation</span>
                  <span className="text-slate-600">/</span>
                  <span className="font-mono text-indigo-300 font-semibold">{targetA}</span>
                  {supportsThinkingA && (
                    <span className="flex items-center gap-1 text-[10px] bg-purple-500/15 text-purple-300 px-2 py-0.5 rounded-full border border-purple-500/30 font-mono font-semibold">
                      <Brain size={11} />
                      {thinkingEffortA === "custom" ? (customThinkingA || "CUSTOM") : thinkingEffortA.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      setChatMessages([
                        {
                          id: "init-1",
                          role: "assistant",
                          content: "Chat history cleared. Ready for new questions!",
                        },
                      ])
                    }
                    className="btn-press flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-rose-300 px-2.5 py-1 rounded-lg hover:bg-white/[0.05] transition-colors"
                    title={t.playground.clearChat}
                  >
                    <Trash2 size={12} />
                    {t.playground.clearChat}
                  </button>
                </div>
              </div>

              {/* Chat Messages Body */}
              <div className="flex-1 p-5 overflow-y-auto space-y-4">
                {/* System Prompt Collapsible Note */}
                <div className="bg-slate-950/60 border border-white/[0.05] rounded-xl p-3 text-[11px] text-slate-400">
                  <span className="font-bold text-indigo-300 uppercase tracking-wider text-[10px] mr-1">
                    System:
                  </span>
                  <input
                    type="text"
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    className="bg-transparent border-b border-white/[0.08] hover:border-white/[0.15] text-slate-300 w-full focus:outline-none focus:border-indigo-500 mt-1 transition-colors"
                    placeholder={t.playground.systemPrompt + "..."}
                  />
                </div>

                {chatMessages.map((msg) => {
                  const parsedMsg = parseThinking(msg.content, msg.reasoning_content || "");
                  return (
                    <div
                      key={msg.id}
                      className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {msg.role === "assistant" && (
                        <div className="w-7 h-7 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 shrink-0 mt-0.5 shadow-xs">
                          <Bot size={14} />
                        </div>
                      )}
                      <div
                        className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                          msg.role === "user"
                            ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-950/50 font-normal rounded-tr-xs"
                            : "bg-slate-950/70 border border-white/[0.07] text-slate-100 rounded-tl-xs shadow-xs"
                        }`}
                      >
                        {/* Thinking Block in Chat Message */}
                        {parsedMsg.thought && (
                          <details className="mb-3 rounded-xl border border-purple-500/30 bg-purple-950/20 p-3 text-[11px] text-purple-200">
                            <summary className="cursor-pointer font-bold flex items-center gap-1.5 text-purple-300 select-none">
                              <Brain size={13} className="text-purple-400" />
                              <span>Chain of Thought</span>
                            </summary>
                            <div className="mt-2.5 pl-3 border-l-2 border-purple-500/40 whitespace-pre-wrap font-mono text-[10px] text-purple-200/90 max-h-96 overflow-y-auto leading-relaxed">
                              {parsedMsg.thought}
                            </div>
                          </details>
                        )}

                        {parsedMsg.mainContent ? (
                          <div className="whitespace-pre-wrap font-mono text-[12px]">{parsedMsg.mainContent}</div>
                        ) : parsedMsg.thought ? (
                          <div className="text-[11px] text-amber-300/90 italic font-sans flex items-center gap-1.5 pt-1">
                            <AlertCircle size={12} className="shrink-0 text-amber-400" />
                            <span>Generation stopped at reasoning stage (token budget reached). Increase Max Tokens or disable Thinking (Off).</span>
                          </div>
                        ) : null}

                        {msg.latency_ms && (
                          <div className="text-[10px] text-slate-400 font-mono mt-2 flex items-center gap-1.5 border-t border-white/[0.06] pt-1.5">
                            <Clock size={11} className="text-slate-500" />
                            {msg.latency_ms}ms
                          </div>
                        )}
                      </div>
                      {msg.role === "user" && (
                        <div className="w-7 h-7 rounded-xl bg-slate-800 border border-white/[0.08] flex items-center justify-center text-slate-300 shrink-0 mt-0.5 shadow-xs">
                          <User size={14} />
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Live Streaming Delta Bubble with Thinking */}
                {loadingA && (
                  <div className="flex gap-3 justify-start">
                    <div className="w-7 h-7 rounded-xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 shrink-0 animate-pulse">
                      <Sparkles size={14} />
                    </div>
                    <div className="max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed bg-slate-950/80 border border-indigo-500/40 text-slate-100 shadow-md">
                      {/* Live Thinking Block */}
                      {parsedA.thought && (
                        <details open className="mb-3 rounded-xl border border-purple-500/30 bg-purple-950/30 p-2.5 text-[11px] text-purple-200">
                          <summary className="cursor-pointer font-bold flex items-center justify-between text-purple-300 select-none">
                            <span className="flex items-center gap-1.5">
                              <Brain size={13} className="text-purple-400" />
                              Reasoning...
                            </span>
                          </summary>
                          <div className="mt-2 pl-3 border-l-2 border-purple-500/40 whitespace-pre-wrap font-mono text-[10px] text-purple-200/90 max-h-96 overflow-y-auto">
                            {parsedA.thought}
                            {!parsedA.mainContent && <span className="inline-block w-1.5 h-3 bg-purple-400 animate-pulse ml-1" />}
                          </div>
                        </details>
                      )}

                      {parsedA.mainContent ? (
                        <div className="whitespace-pre-wrap font-mono text-[12px]">
                          {parsedA.mainContent}
                          <span className="inline-block w-1.5 h-3.5 bg-indigo-400 animate-pulse ml-0.5" />
                        </div>
                      ) : !parsedA.thought ? (
                        <div className="flex items-center gap-2 text-indigo-400 animate-pulse text-[11px]">
                          <RefreshCw size={12} className="animate-spin" />
                          Routing and waiting for response...
                        </div>
                      ) : null}
                    </div>
                  </div>
                )}

                {errorA && (
                  <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-xs flex items-center gap-2.5">
                    <AlertCircle size={15} className="shrink-0 text-rose-400" />
                    <span>{errorA}</span>
                  </div>
                )}
              </div>

              {/* Chat Input Bar */}
              <form onSubmit={handleChatSubmit} className="p-3.5 bg-slate-950/70 border-t border-white/[0.06] flex gap-2.5">
                <textarea
                  rows={2}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleChatSubmit(e);
                    }
                  }}
                  placeholder="Type a message... (Enter to send, Shift+Enter for newline)"
                  className="flex-1 px-3.5 py-2.5 bg-slate-900/80 border border-white/[0.08] rounded-xl text-slate-100 text-xs placeholder-slate-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none resize-none transition-all"
                />
                {loadingA ? (
                  <button
                    type="button"
                    onClick={() => handleStop(false)}
                    className="btn-press px-4 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md shadow-rose-600/30"
                  >
                    <Square size={13} fill="currentColor" />
                    Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!chatInput.trim() || !targetA}
                    className="btn-press px-5 bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-40 text-white rounded-xl text-xs font-bold flex items-center gap-2 transition-all shadow-md shadow-indigo-600/25 border border-indigo-400/20"
                  >
                    <Send size={13} />
                    {t.playground.send}
                  </button>
                )}
              </form>
            </div>
          )}

          {/* ===================== MODE 2: SINGLE PROMPT ===================== */}
          {mode === "single" && (
            <div className="space-y-4">
              {/* Form Card */}
              <form
                onSubmit={handleSingleSubmit}
                className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-3 shadow-sm"
              >
                {/* System Prompt */}
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">{t.playground.systemPrompt}</label>
                  <input
                    type="text"
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
                    placeholder={t.playground.systemPrompt + "..."}
                  />
                </div>

                {/* User Prompt */}
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">{t.playground.userPrompt}</label>
                  <textarea
                    rows={4}
                    required
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs font-mono focus:border-indigo-500 focus:outline-none resize-none"
                    placeholder={t.playground.userPrompt + "..."}
                  />
                </div>

                {/* Send / Stop Buttons */}
                <div className="flex items-center justify-end gap-2 pt-1">
                  {loadingA ? (
                    <button
                      type="button"
                      onClick={() => handleStop(false)}
                      className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      <Square size={13} fill="currentColor" />
                      Stop Generation
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={loadingA || !userPrompt.trim()}
                      className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900/60 disabled:text-slate-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs"
                    >
                      <Send size={13} />
                      {t.playground.send}
                    </button>
                  )}
                </div>
              </form>

              {/* Output Card */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 min-h-[360px] flex flex-col justify-between shadow-sm">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3 text-xs text-slate-400">
                  <span className="flex items-center gap-1.5 font-medium text-slate-300">
                    <Terminal size={14} className="text-indigo-400" />
                    Response Output
                  </span>
                  {responseMetaA && (
                    <div className="flex items-center gap-3 font-mono text-[11px]">
                      <span className="text-emerald-400 flex items-center gap-1">
                        <Clock size={11} />
                        {responseMetaA.latency_ms}ms
                      </span>
                      {responseMetaA.tokens_per_sec && (
                        <span className="text-indigo-300 flex items-center gap-1">
                          <Zap size={11} />
                          {responseMetaA.tokens_per_sec} tok/s
                        </span>
                      )}
                      {responseMetaA.usage && (
                        <span className="text-slate-400">
                          {responseMetaA.usage.prompt_tokens}p / {responseMetaA.usage.completion_tokens}c
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {errorA ? (
                  <div className="p-3 bg-rose-950/60 border border-rose-800 rounded-lg text-rose-300 text-xs flex items-center gap-2">
                    <AlertCircle size={16} className="shrink-0 text-rose-400" />
                    <span>{errorA}</span>
                  </div>
                ) : responseContentA || reasoningContentA ? (
                  <div className="relative group flex-1">
                    <button
                      onClick={() => handleCopyText(responseContentA, false)}
                      className="absolute top-0 right-0 p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 text-xs flex items-center gap-1 opacity-80 hover:opacity-100 transition-opacity"
                      title={t.common.copy}
                    >
                      {copiedResponseA ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      <span>{copiedResponseA ? t.common.copied : t.common.copy}</span>
                    </button>

                    {/* Collapsible Thinking Block */}
                    {parsedA.thought && (
                      <details open className="mb-3 rounded-xl border border-purple-900/60 bg-purple-950/20 p-3 text-xs shadow-xs">
                        <summary className="cursor-pointer font-semibold flex items-center justify-between text-purple-300 select-none">
                          <span className="flex items-center gap-1.5">
                            <Brain size={14} className="text-purple-400" />
                            <span>Chain of Thought</span>
                          </span>
                          <span className="text-[10px] text-purple-400/70 font-mono">
                            {loadingA && !parsedA.mainContent ? "Reasoning..." : "Completed"}
                          </span>
                        </summary>
                        <div className="mt-2.5 pl-3 border-l-2 border-purple-500/40 whitespace-pre-wrap font-mono text-[11px] text-purple-200/90 max-h-96 overflow-y-auto leading-relaxed">
                          {parsedA.thought}
                          {loadingA && !parsedA.mainContent && (
                            <span className="inline-block w-1.5 h-3 bg-purple-400 animate-pulse ml-1" />
                          )}
                        </div>
                      </details>
                    )}

                    <div className="text-slate-100 text-xs whitespace-pre-wrap font-mono leading-relaxed overflow-y-auto max-h-[460px] pr-2">
                      {parsedA.mainContent ? (
                        parsedA.mainContent
                      ) : !loadingA && parsedA.thought ? (
                        <div className="text-amber-300/90 italic font-sans flex items-center gap-1.5 py-1">
                          <AlertCircle size={13} className="shrink-0 text-amber-400" />
                          <span>Generation stopped at reasoning stage (token budget reached). Increase Max Tokens or disable Thinking (Off).</span>
                        </div>
                      ) : null}
                      {loadingA && (
                        <span className="inline-block w-1.5 h-3.5 bg-indigo-400 animate-pulse ml-0.5" />
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs py-12">
                    {loadingA ? (
                      <div className="flex items-center gap-2 text-indigo-400 animate-pulse">
                        <Sparkles size={16} />
                        Routing and querying model...
                      </div>
                    ) : (
                      "Model response will appear here."
                    )}
                  </div>
                )}

                {/* Bottom Meta */}
                {responseMetaA && (
                  <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                    <span>
                      Mode: <strong className="text-slate-200">{responseMetaA.mode}</strong>
                    </span>
                    <span>
                      Model: <strong className="text-slate-200">{responseMetaA.model || targetA}</strong>
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ===================== MODE 3: SIDE-BY-SIDE COMPARE ===================== */}
          {mode === "compare" && (
            <div className="space-y-4">
              {/* Prompt Input Form */}
              <form
                onSubmit={handleSingleSubmit}
                className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-2.5 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-200">
                    Shared Prompt for Both Models
                  </label>
                  {isAnyLoading ? (
                    <button
                      type="button"
                      onClick={handleStopAll}
                      className="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded text-xs font-semibold flex items-center gap-1"
                    >
                      <Square size={12} fill="currentColor" />
                      Stop Both
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!userPrompt.trim() || isAnyLoading}
                      className="px-4 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900/60 text-white rounded text-xs font-semibold flex items-center gap-1 shadow-xs"
                    >
                      <Send size={12} />
                      Run Comparison
                    </button>
                  )}
                </div>
                <textarea
                  rows={3}
                  required
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  placeholder="Enter prompt to send simultaneously to Model A and Model B..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs font-mono focus:border-indigo-500 focus:outline-none resize-none"
                />
              </form>

              {/* 2 Side-by-side Response Columns */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Column A */}
                <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between min-h-[420px] shadow-sm">
                  <div>
                    <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-2.5">
                      <div className="truncate">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 block">
                          Model A {supportsThinkingA && `(Thinking: ${thinkingEffortA === "custom" ? (customThinkingA || "CUSTOM") : thinkingEffortA.toUpperCase()})`}
                        </span>
                        <span className="font-mono text-xs font-semibold text-slate-200 truncate block">
                          {targetA}
                        </span>
                      </div>
                      {responseMetaA && (
                        <div className="text-right text-[11px] font-mono text-emerald-400">
                          <div>{responseMetaA.latency_ms}ms</div>
                          {responseMetaA.tokens_per_sec && (
                            <div className="text-[10px] text-slate-400">{responseMetaA.tokens_per_sec} t/s</div>
                          )}
                        </div>
                      )}
                    </div>

                    {errorA ? (
                      <div className="p-2.5 bg-rose-950/60 border border-rose-800 rounded-lg text-rose-300 text-xs">
                        {errorA}
                      </div>
                    ) : responseContentA || reasoningContentA ? (
                      <div className="relative group">
                        <button
                          onClick={() => handleCopyText(responseContentA, false)}
                          className="absolute top-0 right-0 p-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[10px] flex items-center gap-1"
                        >
                          {copiedResponseA ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
                        </button>

                        {/* Thinking Block in Compare Column A */}
                        {parsedA.thought && (
                          <details open className="mb-2 rounded-lg border border-purple-900/50 bg-purple-950/20 p-2 text-xs">
                            <summary className="cursor-pointer font-semibold flex items-center gap-1 text-purple-300 select-none text-[11px]">
                              <Brain size={12} className="text-purple-400" />
                              <span>Reasoning A</span>
                            </summary>
                            <div className="mt-1.5 pl-2 border-l border-purple-500/40 whitespace-pre-wrap font-mono text-[10px] text-purple-200/90 max-h-64 overflow-y-auto">
                              {parsedA.thought}
                            </div>
                          </details>
                        )}

                        <div className="text-slate-100 text-xs whitespace-pre-wrap font-mono leading-relaxed overflow-y-auto max-h-[350px]">
                          {parsedA.mainContent ? (
                            parsedA.mainContent
                          ) : !loadingA && parsedA.thought ? (
                            <div className="text-amber-300/90 italic font-sans flex items-center gap-1.5 py-1">
                              <AlertCircle size={12} className="shrink-0 text-amber-400" />
                              <span>Stopped during reasoning (token limit reached)</span>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-16 text-slate-500 text-xs">
                        {loadingA ? (
                          <div className="animate-pulse text-indigo-400">Generating response A...</div>
                        ) : (
                          "Waiting to run"
                        )}
                      </div>
                    )}
                  </div>

                  {responseMetaA && (
                    <div className="pt-2 border-t border-slate-800 text-[10px] text-slate-400 flex justify-between">
                      <span>Mode: {responseMetaA.mode}</span>
                      <span>Tokens: {responseMetaA.usage?.total_tokens ?? responseMetaA.token_count ?? "Unavailable"}</span>
                    </div>
                  )}
                </div>

                {/* Column B */}
                <div className="bg-slate-900/90 border border-purple-900/60 rounded-xl p-3.5 flex flex-col justify-between min-h-[420px] shadow-sm">
                  <div>
                    <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-2.5">
                      <div className="truncate">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400 block">
                          Model B {supportsThinkingB && `(Thinking: ${thinkingEffortB === "custom" ? (customThinkingB || "CUSTOM") : thinkingEffortB.toUpperCase()})`}
                        </span>
                        <span className="font-mono text-xs font-semibold text-slate-200 truncate block">
                          {targetB}
                        </span>
                      </div>
                      {responseMetaB && (
                        <div className="text-right text-[11px] font-mono text-emerald-400">
                          <div>{responseMetaB.latency_ms}ms</div>
                          {responseMetaB.tokens_per_sec && (
                            <div className="text-[10px] text-slate-400">{responseMetaB.tokens_per_sec} t/s</div>
                          )}
                        </div>
                      )}
                    </div>

                    {errorB ? (
                      <div className="p-2.5 bg-rose-950/60 border border-rose-800 rounded-lg text-rose-300 text-xs">
                        {errorB}
                      </div>
                    ) : responseContentB || reasoningContentB ? (
                      <div className="relative group">
                        <button
                          onClick={() => handleCopyText(responseContentB, true)}
                          className="absolute top-0 right-0 p-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[10px] flex items-center gap-1"
                        >
                          {copiedResponseB ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
                        </button>

                        {/* Thinking Block in Compare Column B */}
                        {parsedB.thought && (
                          <details open className="mb-2 rounded-lg border border-purple-900/50 bg-purple-950/20 p-2 text-xs">
                            <summary className="cursor-pointer font-semibold flex items-center gap-1 text-purple-300 select-none text-[11px]">
                              <Brain size={12} className="text-purple-400" />
                              <span>Reasoning B</span>
                            </summary>
                            <div className="mt-1.5 pl-2 border-l border-purple-500/40 whitespace-pre-wrap font-mono text-[10px] text-purple-200/90 max-h-64 overflow-y-auto">
                              {parsedB.thought}
                            </div>
                          </details>
                        )}

                        <div className="text-slate-100 text-xs whitespace-pre-wrap font-mono leading-relaxed overflow-y-auto max-h-[350px]">
                          {parsedB.mainContent ? (
                            parsedB.mainContent
                          ) : !loadingB && parsedB.thought ? (
                            <div className="text-amber-300/90 italic font-sans flex items-center gap-1.5 py-1">
                              <AlertCircle size={12} className="shrink-0 text-amber-400" />
                              <span>Stopped during reasoning (token limit reached)</span>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-16 text-slate-500 text-xs">
                        {loadingB ? (
                          <div className="animate-pulse text-purple-400">Generating response B...</div>
                        ) : (
                          "Waiting to run"
                        )}
                      </div>
                    )}
                  </div>

                  {responseMetaB && (
                    <div className="pt-2 border-t border-slate-800 text-[10px] text-slate-400 flex justify-between">
                      <span>Mode: {responseMetaB.mode}</span>
                      <span>Tokens: {responseMetaB.usage?.total_tokens ?? responseMetaB.token_count ?? "Unavailable"}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ===================== MODE 4: JEV (SYSTEM ONE) ===================== */}
          {mode === "jev" && (
            <div className="space-y-4">
              {/* Jev Studio Main Card */}
              <div className="glass-panel card-specular rounded-2xl border border-white/[0.07] p-5 shadow-xl space-y-5">
                {/* Header Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="p-1.5 rounded-lg bg-violet-600/20 text-violet-400 border border-violet-500/30">
                        <Zap size={16} />
                      </span>
                      <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                        System One Decision Studio
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300 border border-violet-500/30">
                          Jev Engine
                        </span>
                      </h2>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      Fast, calibrated decision engine evaluating state against discrete criteria and rubrics.
                    </p>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    {/* Visual vs JSON Toggle */}
                    <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-white/[0.08] text-[11px]">
                      <button
                        type="button"
                        onClick={() => {
                          if (jevEditorMode === "json") {
                            try {
                              setJevQuestions(JSON.parse(jevRawJson));
                            } catch {}
                          }
                          setJevEditorMode("visual");
                        }}
                        className={`px-2.5 py-1 rounded-md font-semibold transition-all ${
                          jevEditorMode === "visual"
                            ? "bg-violet-600 text-white shadow-xs"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        Visual Builder
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setJevRawJson(JSON.stringify(jevQuestions, null, 2));
                          setJevEditorMode("json");
                        }}
                        className={`px-2.5 py-1 rounded-md font-semibold transition-all ${
                          jevEditorMode === "json"
                            ? "bg-violet-600 text-white shadow-xs"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        Raw JSON
                      </button>
                    </div>

                    {/* Run Decision Button */}
                    <button
                      type="button"
                      disabled={jevLoading || !targetA}
                      onClick={handleRunJevDecision}
                      className="btn-press px-4 py-1.5 bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-40 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md shadow-violet-600/25 border border-violet-400/20"
                    >
                      {jevLoading ? (
                        <>
                          <RefreshCw size={13} className="animate-spin" />
                          Evaluating...
                        </>
                      ) : (
                        <>
                          <Zap size={13} className="text-amber-300" />
                          Evaluate Decision
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* State Input Section */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                      <Layers size={13} className="text-indigo-400" />
                      State Context (Document, Log, Ticket, or Payload)
                    </label>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {jevState.length} chars
                    </span>
                  </div>
                  <textarea
                    rows={4}
                    value={jevState}
                    onChange={(e) => setJevState(e.target.value)}
                    placeholder="Enter the context / document / transaction state to evaluate..."
                    className="w-full px-3.5 py-2.5 bg-slate-950/90 border border-white/[0.08] rounded-xl text-slate-100 text-xs font-mono placeholder-slate-500 focus:border-violet-500 focus:ring-1 focus:ring-violet-500/20 focus:outline-none resize-y transition-all"
                  />
                </div>

                {/* Questions Section */}
                <div className="space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                      <HelpCircle size={13} className="text-violet-400" />
                      Questions Specification ({Object.keys(jevQuestions).length})
                    </label>

                    {jevEditorMode === "visual" && (
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleAddJevQuestion("choice")}
                          className="btn-press flex items-center gap-1 px-2.5 py-1 bg-violet-600/15 hover:bg-violet-600/25 text-violet-300 border border-violet-500/30 rounded-lg text-[11px] font-semibold transition-all"
                        >
                          <Plus size={11} />
                          + Choice
                        </button>
                        <button
                          type="button"
                          onClick={() => handleAddJevQuestion("score")}
                          className="btn-press flex items-center gap-1 px-2.5 py-1 bg-emerald-600/15 hover:bg-emerald-600/25 text-emerald-300 border border-emerald-500/30 rounded-lg text-[11px] font-semibold transition-all"
                        >
                          <Plus size={11} />
                          + Score
                        </button>
                        <button
                          type="button"
                          onClick={() => handleAddJevQuestion("noul")}
                          className="btn-press flex items-center gap-1 px-2.5 py-1 bg-amber-600/15 hover:bg-amber-600/25 text-amber-300 border border-amber-500/30 rounded-lg text-[11px] font-semibold transition-all"
                        >
                          <Plus size={11} />
                          + Noul
                        </button>
                      </div>
                    )}
                  </div>

                  {jevEditorMode === "visual" ? (
                    <div className="space-y-3">
                      {Object.keys(jevQuestions).length === 0 ? (
                        <div className="p-8 text-center bg-slate-950/40 border border-dashed border-white/[0.08] rounded-xl text-slate-500 text-xs">
                          No questions defined yet. Click + Choice, + Score, + Noul above or select a preset from the sidebar.
                        </div>
                      ) : (
                        Object.entries(jevQuestions).map(([qKey, qVal]) => {
                          const isChoice = "choice" in qVal || (qVal as any).type === "choice";
                          const isScore = "score" in qVal || (qVal as any).type === "score";
                          const isNoul = "noul" in qVal || (qVal as any).type === "noul";

                          return (
                            <div
                              key={qKey}
                              className={`p-3.5 rounded-xl border bg-slate-950/70 transition-all ${
                                isChoice
                                  ? "border-violet-500/30 hover:border-violet-500/50"
                                  : isScore
                                  ? "border-emerald-500/30 hover:border-emerald-500/50"
                                  : "border-amber-500/30 hover:border-amber-500/50"
                              }`}
                            >
                              {/* Question Card Header */}
                              <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-white/[0.06] mb-3">
                                <div className="flex items-center gap-2 flex-1">
                                  <span
                                    className={`text-[10px] uppercase font-mono font-bold px-2 py-0.5 rounded ${
                                      isChoice
                                        ? "bg-violet-500/20 text-violet-300"
                                        : isScore
                                        ? "bg-emerald-500/20 text-emerald-300"
                                        : "bg-amber-500/20 text-amber-300"
                                    }`}
                                  >
                                    {isChoice ? "Choice" : isScore ? "Score" : "Noul"}
                                  </span>
                                  <input
                                    type="text"
                                    defaultValue={qKey}
                                    onBlur={(e) => handleUpdateJevQuestionKey(qKey, e.target.value)}
                                    placeholder="question_id"
                                    className="px-2 py-1 bg-slate-900 border border-white/[0.08] rounded text-xs font-mono text-slate-200 focus:border-violet-500 focus:outline-none w-48"
                                  />
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveJevQuestion(qKey)}
                                  className="text-slate-500 hover:text-rose-400 p-1 rounded transition-colors"
                                  title="Delete question"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>

                              {/* Question Card Body */}
                              {isChoice && (
                                <div className="space-y-2">
                                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                                    <span>Choice Criteria (mutually exclusive outcomes):</span>
                                    <button
                                      type="button"
                                      onClick={() => handleAddChoiceCriterion(qKey)}
                                      className="text-violet-400 hover:text-violet-300 flex items-center gap-1 font-semibold"
                                    >
                                      <Plus size={11} /> Add Option
                                    </button>
                                  </div>
                                  <div className="space-y-1.5">
                                    {Object.entries((qVal as any).choice?.criteria || {}).map(([optKey, optDesc]) => (
                                      <div key={optKey} className="flex items-center gap-2">
                                        <input
                                          type="text"
                                          value={optKey}
                                          readOnly
                                          className="w-36 px-2 py-1 bg-slate-900 border border-white/[0.06] rounded text-[11px] font-mono text-violet-300 shrink-0"
                                        />
                                        <input
                                          type="text"
                                          value={optDesc as string}
                                          onChange={(e) => handleUpdateChoiceCriterion(qKey, optKey, e.target.value)}
                                          placeholder="Criterion description / meaning..."
                                          className="flex-1 px-2.5 py-1 bg-slate-900 border border-white/[0.06] rounded text-[11px] text-slate-200 placeholder-slate-600 focus:border-violet-500 focus:outline-none"
                                        />
                                        <button
                                          type="button"
                                          onClick={() => handleRemoveChoiceCriterion(qKey, optKey)}
                                          className="text-slate-600 hover:text-rose-400 p-1 rounded"
                                        >
                                          <X size={12} />
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {isScore && (
                                <div className="space-y-2">
                                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                                    <span>Ordered Rubric Levels (scale low to high):</span>
                                    <button
                                      type="button"
                                      onClick={() => handleAddScoreLevel(qKey)}
                                      className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-semibold"
                                    >
                                      <Plus size={11} /> Add Level
                                    </button>
                                  </div>
                                  <div className="space-y-1.5">
                                    {((qVal as any).score?.rubric || []).map((lvl: string, idx: number) => (
                                      <div key={idx} className="flex items-center gap-2">
                                        <span className="w-16 px-2 py-1 bg-slate-900 border border-white/[0.06] rounded text-[10px] font-mono text-emerald-400 text-center shrink-0">
                                          Lvl {idx + 1}
                                        </span>
                                        <input
                                          type="text"
                                          value={lvl}
                                          onChange={(e) => handleUpdateScoreLevel(qKey, idx, e.target.value)}
                                          placeholder="Level label and description..."
                                          className="flex-1 px-2.5 py-1 bg-slate-900 border border-white/[0.06] rounded text-[11px] text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none"
                                        />
                                        <button
                                          type="button"
                                          onClick={() => handleRemoveScoreLevel(qKey, idx)}
                                          className="text-slate-600 hover:text-rose-400 p-1 rounded"
                                        >
                                          <X size={12} />
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {isNoul && (
                                <div className="space-y-1">
                                  <label className="text-[11px] text-slate-400">
                                    Binary True / False Judgment Proposition:
                                  </label>
                                  <input
                                    type="text"
                                    value={(qVal as any).noul?.description || (qVal as any).instructions || ""}
                                    onChange={(e) => handleUpdateNoulDescription(qKey, e.target.value)}
                                    placeholder="Condition to judge as True or False..."
                                    className="w-full px-2.5 py-1.5 bg-slate-900 border border-white/[0.06] rounded text-[11px] text-slate-200 placeholder-slate-600 focus:border-amber-500 focus:outline-none"
                                  />
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  ) : (
                    <div>
                      <textarea
                        rows={10}
                        value={jevRawJson}
                        onChange={(e) => {
                          setJevRawJson(e.target.value);
                          try {
                            setJevQuestions(JSON.parse(e.target.value));
                          } catch {}
                        }}
                        className="w-full px-3.5 py-2.5 bg-slate-950/90 border border-white/[0.08] rounded-xl text-violet-200 text-xs font-mono focus:border-violet-500 focus:outline-none resize-y"
                      />
                      <p className="text-[10px] text-slate-500 mt-1">
                        Directly edit the Jev questions dictionary schema. Changes sync automatically to Visual Builder.
                      </p>
                    </div>
                  )}
                </div>

                {/* Error Banner */}
                {jevError && (
                  <div className="p-3 bg-rose-950/60 border border-rose-800/80 rounded-xl text-rose-300 text-xs flex items-center gap-2">
                    <AlertCircle size={15} className="shrink-0 text-rose-400" />
                    <span>{jevError}</span>
                  </div>
                )}

                {/* Results Section */}
                <div className="pt-2 border-t border-white/[0.06] space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <BarChart3 size={14} className="text-violet-400" />
                      <span className="text-xs font-bold text-slate-200">Decision Results & Probabilities</span>
                    </div>

                    {jevResponse && (
                      <div className="flex items-center gap-2 text-[11px]">
                        <span className="font-mono text-emerald-400 font-semibold">
                          {jevResponse.latency_ms}ms
                        </span>
                        {jevResponse.usage && (
                          <span className="text-slate-400 font-mono">
                            {jevResponse.usage.total_tokens || (jevResponse.usage.input_tokens + jevResponse.usage.output_tokens)} tok
                          </span>
                        )}
                        <div className="flex bg-slate-950/80 p-0.5 rounded-lg border border-white/[0.08] text-[10px] ml-2">
                          <button
                            type="button"
                            onClick={() => setJevActiveTab("results")}
                            className={`px-2 py-0.5 rounded ${
                              jevActiveTab === "results"
                                ? "bg-slate-800 text-slate-100 font-bold"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            Visual
                          </button>
                          <button
                            type="button"
                            onClick={() => setJevActiveTab("json")}
                            className={`px-2 py-0.5 rounded ${
                              jevActiveTab === "json"
                                ? "bg-slate-800 text-slate-100 font-bold"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            JSON
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {jevLoading ? (
                    <div className="p-12 text-center bg-slate-950/50 border border-white/[0.06] rounded-xl space-y-3">
                      <RefreshCw size={24} className="animate-spin mx-auto text-violet-400" />
                      <p className="text-xs font-semibold text-violet-300">
                        Evaluating System One Decision against {Object.keys(jevQuestions).length} questions...
                      </p>
                      <p className="text-[11px] text-slate-500 font-mono">
                        Target model: {targetA}
                      </p>
                    </div>
                  ) : jevResponse ? (
                    jevActiveTab === "results" ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {Object.entries(jevResponse.answers || {}).map(([ansKey, ansVal]: [string, any]) => {
                          const isChoiceAns =
                            ansVal.type === "choice" ||
                            ansVal.choice !== undefined ||
                            ansVal.decision !== undefined;
                          const isScoreAns =
                            ansVal.type === "score" ||
                            ansVal.score !== undefined ||
                            ansVal.level !== undefined;
                          const isNoulAns =
                            ansVal.type === "noul" ||
                            ansVal.answer !== undefined ||
                            ansVal.judgment !== undefined;

                          const chosen = ansVal.choice || ansVal.decision || "";
                          const scoreVal = ansVal.score !== undefined ? ansVal.score : ansVal.level;
                          const boolVal = ansVal.answer !== undefined ? ansVal.answer : ansVal.judgment;
                          const probs: Record<string, number> = ansVal.probabilities || ansVal.distribution || {};
                          const conf = ansVal.confidence !== undefined ? ansVal.confidence : null;

                          return (
                            <div
                              key={ansKey}
                              className="bg-slate-950/80 border border-white/[0.08] rounded-xl p-3.5 space-y-3 shadow-sm flex flex-col justify-between"
                            >
                              <div>
                                {/* Answer Header */}
                                <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                                  <span className="text-xs font-mono font-bold text-slate-200">{ansKey}</span>
                                  <span
                                    className={`text-[9px] uppercase font-mono font-bold px-2 py-0.5 rounded ${
                                      isChoiceAns
                                        ? "bg-violet-500/20 text-violet-300"
                                        : isScoreAns
                                        ? "bg-emerald-500/20 text-emerald-300"
                                        : "bg-amber-500/20 text-amber-300"
                                    }`}
                                  >
                                    {isChoiceAns ? "Choice" : isScoreAns ? "Score" : "Noul"}
                                  </span>
                                </div>

                                {/* Main Decision Outcome Callout */}
                                <div className="py-2.5">
                                  {isChoiceAns && (
                                    <div className="flex items-center justify-between bg-violet-950/40 border border-violet-500/30 rounded-lg p-2.5">
                                      <div>
                                        <span className="text-[10px] text-violet-300/80 uppercase font-semibold block">
                                          Decision
                                        </span>
                                        <span className="text-sm font-bold text-violet-100 font-mono">
                                          {chosen || "—"}
                                        </span>
                                      </div>
                                      {probs[chosen] !== undefined && (
                                        <div className="text-right">
                                          <span className="text-[10px] text-violet-300/80 uppercase font-semibold block">
                                            Calibrated P
                                          </span>
                                          <span className="text-sm font-bold text-violet-300 font-mono">
                                            {(Number(probs[chosen]) * 100).toFixed(1)}%
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  )}

                                  {isScoreAns && (
                                    <div className="flex items-center justify-between bg-emerald-950/40 border border-emerald-500/30 rounded-lg p-2.5">
                                      <div>
                                        <span className="text-[10px] text-emerald-300/80 uppercase font-semibold block">
                                          Score / Level
                                        </span>
                                        <span className="text-base font-bold text-emerald-100 font-mono">
                                          {scoreVal}
                                        </span>
                                      </div>
                                      {conf !== null && (
                                        <div className="text-right">
                                          <span className="text-[10px] text-emerald-300/80 uppercase font-semibold block">
                                            Confidence
                                          </span>
                                          <span className="text-xs font-bold text-emerald-300 font-mono">
                                            {(Number(conf) <= 1 ? Number(conf) * 100 : Number(conf)).toFixed(0)}%
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  )}

                                  {isNoulAns && (
                                    <div
                                      className={`flex items-center justify-between p-2.5 rounded-lg border ${
                                        boolVal
                                          ? "bg-emerald-950/40 border-emerald-500/30"
                                          : "bg-rose-950/40 border-rose-500/30"
                                      }`}
                                    >
                                      <div>
                                        <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                                          Binary Judgment
                                        </span>
                                        <span
                                          className={`text-base font-bold font-mono ${
                                            boolVal ? "text-emerald-300" : "text-rose-300"
                                          }`}
                                        >
                                          {boolVal ? "TRUE" : "FALSE"}
                                        </span>
                                      </div>
                                      {ansVal.probability !== undefined && (
                                        <div className="text-right">
                                          <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                                            P(True)
                                          </span>
                                          <span className="text-sm font-bold text-slate-200 font-mono">
                                            {(Number(ansVal.probability) * 100).toFixed(1)}%
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>

                                {/* Probability Distribution Bars */}
                                {Object.keys(probs).length > 0 && (
                                  <div className="space-y-1.5 pt-1">
                                    <span className="text-[10px] font-semibold text-slate-400 block">
                                      Probability Distribution:
                                    </span>
                                    {Object.entries(probs).map(([k, p]) => {
                                      const pNum = Number(p);
                                      const pPercent = Math.min(Math.max(pNum * 100, 0), 100);
                                      const isWinner = k === chosen;

                                      return (
                                        <div key={k} className="space-y-0.5">
                                          <div className="flex items-center justify-between text-[10px] font-mono">
                                            <span
                                              className={
                                                isWinner
                                                  ? "font-bold text-violet-300 truncate mr-2"
                                                  : "text-slate-400 truncate mr-2"
                                              }
                                            >
                                              {k}
                                            </span>
                                            <span
                                              className={
                                                isWinner
                                                  ? "font-bold text-violet-300 shrink-0"
                                                  : "text-slate-400 shrink-0"
                                              }
                                            >
                                              {pPercent.toFixed(1)}%
                                            </span>
                                          </div>
                                          <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                                            <div
                                              className={`h-full rounded-full transition-all duration-500 ${
                                                isWinner
                                                  ? "bg-gradient-to-r from-violet-500 to-indigo-500"
                                                  : "bg-slate-700"
                                              }`}
                                              style={{ width: `${pPercent}%` }}
                                            />
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>

                              {/* Confidence footer */}
                              {conf !== null && !isScoreAns && (
                                <div className="pt-2 border-t border-white/[0.05] flex items-center justify-between text-[10px] text-slate-400">
                                  <span>Confidence</span>
                                  <span className="font-mono text-slate-200 font-semibold">
                                    {(Number(conf) <= 1 ? Number(conf) * 100 : Number(conf)).toFixed(0)}%
                                  </span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => {
                            navigator.clipboard.writeText(JSON.stringify(jevResponse, null, 2));
                            setCopiedJevJson(true);
                            setTimeout(() => setCopiedJevJson(false), 2000);
                          }}
                          className="absolute top-2.5 right-2.5 p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs flex items-center gap-1 z-10"
                        >
                          {copiedJevJson ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                          {copiedJevJson ? "Copied" : "Copy"}
                        </button>
                        <pre className="p-3 bg-slate-950 border border-white/[0.08] rounded-xl text-xs font-mono text-violet-200 overflow-x-auto max-h-[380px]">
                          {JSON.stringify(jevResponse, null, 2)}
                        </pre>
                      </div>
                    )
                  ) : (
                    <div className="p-8 text-center bg-slate-950/40 border border-white/[0.06] rounded-xl text-slate-500 text-xs">
                      Ready to evaluate. Configure State and Questions above, then click <strong className="text-slate-300">Evaluate Decision</strong>.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ===================== CODE EXPORT MODAL ===================== */}
      {showCodeModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full p-4 space-y-3 shadow-2xl">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <Code size={16} className="text-indigo-400" />
                Integration Code Snippet
              </div>
              <button
                onClick={() => setShowCodeModal(false)}
                className="text-slate-400 hover:text-slate-200 p-1 rounded"
              >
                <X size={16} />
              </button>
            </div>

            {/* Language Tabs */}
            <div className="flex gap-2">
              <button
                onClick={() => setCodeTab("python")}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  codeTab === "python" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                Python (OpenAI SDK)
              </button>
              <button
                onClick={() => setCodeTab("curl")}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  codeTab === "curl" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                cURL
              </button>
              <button
                onClick={() => setCodeTab("node")}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  codeTab === "node" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                Node.js / TypeScript
              </button>
            </div>

            {/* Code snippet */}
            <div className="relative group">
              <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 text-xs font-mono overflow-x-auto max-h-[380px] leading-relaxed">
                <code>{getExportCode()}</code>
              </pre>
              <button
                onClick={handleCopyCode}
                className="absolute top-2 right-2 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-xs font-medium flex items-center gap-1.5 transition-colors"
              >
                {copiedCode ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                {copiedCode ? t.common.copied : t.common.copy}
              </button>
            </div>

            <div className="flex justify-end pt-1">
              <button
                onClick={() => setShowCodeModal(false)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition-colors"
              >
                {t.common.close}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
