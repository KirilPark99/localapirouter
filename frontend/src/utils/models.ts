import { DiscoveredModel, Provider } from "../types";

export const HIDDEN_MODELS_STORAGE_KEY = "myairouter_hidden_model_ids";

export function getHiddenModelIds(): Set<number> {
  try {
    const raw = localStorage.getItem(HIDDEN_MODELS_STORAGE_KEY);
    return raw ? new Set<number>(JSON.parse(raw)) : new Set<number>();
  } catch {
    return new Set<number>();
  }
}

export function saveHiddenModelIds(ids: Set<number>): void {
  try {
    localStorage.setItem(HIDDEN_MODELS_STORAGE_KEY, JSON.stringify(Array.from(ids)));
  } catch (e) {
    console.error("Failed to save hidden model IDs:", e);
  }
}

export function isModelVisible(model: DiscoveredModel, hiddenIds?: Set<number>): boolean {
  if (hiddenIds && hiddenIds.size > 0 && hiddenIds.has(model.id)) {
    return false;
  }
  return model.is_visible === true && model.available && model.enabled !== false;
}

export function getVisibleModels(
  models: DiscoveredModel[],
  hiddenIds?: Set<number>
): DiscoveredModel[] {
  return models.filter((m) => isModelVisible(m, hiddenIds));
}

export interface ProviderModelGroup {
  provider: Provider;
  models: DiscoveredModel[];
}

export function groupModelsByProvider(
  models: DiscoveredModel[],
  providers: Provider[],
  onlyVisible: boolean = false,
  hiddenIds?: Set<number>
): ProviderModelGroup[] {
  const groupMap = new Map<number, Map<string, DiscoveredModel>>();

  models.forEach((m) => {
    if (onlyVisible && !isModelVisible(m, hiddenIds)) {
      return;
    }

    if (!groupMap.has(m.provider_id)) {
      groupMap.set(m.provider_id, new Map());
    }
    const pModels = groupMap.get(m.provider_id)!;
    // Deduplicate by provider_model_id so multiple credentials do not cause duplicates
    if (!pModels.has(m.provider_model_id)) {
      pModels.set(m.provider_model_id, m);
    }
  });

  const sortedProviders = [...providers].sort((a, b) => a.name.localeCompare(b.name));
  const groups: ProviderModelGroup[] = [];

  sortedProviders.forEach((p) => {
    const pModelsMap = groupMap.get(p.id);
    const pModels = pModelsMap ? Array.from(pModelsMap.values()) : [];
    if (pModels.length > 0 || !onlyVisible) {
      groups.push({
        provider: p,
        models: pModels.sort((a, b) => a.canonical_slug.localeCompare(b.canonical_slug)),
      });
    }
  });

  return groups;
}
