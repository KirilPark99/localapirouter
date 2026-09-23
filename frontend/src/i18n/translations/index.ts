import { Language, TranslationSchema } from "../types";
import { en } from "./en";
import { zh } from "./zh";
import { hi } from "./hi";
import { es } from "./es";
import { fr } from "./fr";
import { ar } from "./ar";
import { bn } from "./bn";
import { pt } from "./pt";
import { ru } from "./ru";
import { ja } from "./ja";
import { de } from "./de";
import { uk } from "./uk";
import { be } from "./be";

export const translations: Record<Language, TranslationSchema> = {
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
