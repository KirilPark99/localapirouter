import { Language } from "../types";
import { DocContent } from "./types";
import { en } from "./en";
import { ru } from "./ru";
import { uk } from "./uk";
import { be } from "./be";
import { zh } from "./zh";
import { es } from "./es";
import { fr } from "./fr";
import { de } from "./de";
import { ja } from "./ja";
import { pt } from "./pt";
import { ar } from "./ar";
import { hi } from "./hi";
import { bn } from "./bn";

export * from "./types";

export const docsTranslations: Record<Language, DocContent> = {
  en,
  zh,
  hi,
  es,
  fr,
  ar,
  bn,
  pt,
  ru,
  ja,
  de,
  uk,
  be,
};
