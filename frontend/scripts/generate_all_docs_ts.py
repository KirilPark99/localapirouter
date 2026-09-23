import json
import os
import sys

# Ensure local dir is on sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from sections_data_part1 import SECTIONS_PART1
from sections_data_part2 import SECTIONS_PART2

LANGUAGES = ["en", "ru", "uk", "be", "zh", "es", "fr", "de", "ja", "pt", "ar", "hi", "bn"]

UI_STRINGS = {
    "en": {
        "searchPlaceholder": "Search docs (e.g. Ollama, Fallback, Fusion, API key)...",
        "noSectionsFound": "No matching documentation sections found.",
        "prevSection": "Previous Section",
        "nextSection": "Next Section",
        "copied": "Copied!",
        "copy": "Copy Code",
        "endpoints": "Endpoints",
        "tocTitle": "Documentation Index"
    },
    "ru": {
        "searchPlaceholder": "Поиск по документации (например, Ollama, Fallback, Fusion)...",
        "noSectionsFound": "Разделы документации не найдены.",
        "prevSection": "Предыдущий раздел",
        "nextSection": "Следующий раздел",
        "copied": "Скопировано!",
        "copy": "Скопировать код",
        "endpoints": "Эндпоинты",
        "tocTitle": "Содержание"
    },
    "uk": {
        "searchPlaceholder": "Пошук по документації (наприклад, Ollama, Fallback, Fusion)...",
        "noSectionsFound": "Розділи документації не знайдені.",
        "prevSection": "Попередній розділ",
        "nextSection": "Наступний розділ",
        "copied": "Скопійовано!",
        "copy": "Скопіювати код",
        "endpoints": "Ендпоінти",
        "tocTitle": "Зміст"
    },
    "be": {
        "searchPlaceholder": "Пошук па дакументацыі (напрыклад, Ollama, Fallback, Fusion)...",
        "noSectionsFound": "Раздзелы дакументацыі не знойдзены.",
        "prevSection": "Папярэдні раздзел",
        "nextSection": "Наступны раздзел",
        "copied": "Скапіявана!",
        "copy": "Скапіяваць код",
        "endpoints": "Эндпоінты",
        "tocTitle": "Змест"
    },
    "zh": {
        "searchPlaceholder": "搜索文档（例如 Ollama、Fallback、Fusion、API 密钥）...",
        "noSectionsFound": "未找到匹配的文档小节。",
        "prevSection": "上一小节",
        "nextSection": "下一小节",
        "copied": "已复制！",
        "copy": "复制代码",
        "endpoints": "接口列表",
        "tocTitle": "文档目录"
    },
    "es": {
        "searchPlaceholder": "Buscar en la documentación (ej. Ollama, Fallback, Fusion)...",
        "noSectionsFound": "No se encontraron secciones coincidentes.",
        "prevSection": "Sección anterior",
        "nextSection": "Sección siguiente",
        "copied": "¡Copiado!",
        "copy": "Copiar código",
        "endpoints": "Endpoints",
        "tocTitle": "Índice de documentación"
    },
    "fr": {
        "searchPlaceholder": "Rechercher dans la documentation (ex. Ollama, Fallback, Fusion)...",
        "noSectionsFound": "Aucune section correspondante trouvée.",
        "prevSection": "Section précédente",
        "nextSection": "Section suivante",
        "copied": "Copié !",
        "copy": "Copier le code",
        "endpoints": "Points de terminaison",
        "tocTitle": "Sommaire"
    },
    "de": {
        "searchPlaceholder": "Dokumentation durchsuchen (z. B. Ollama, Fallback, Fusion)...",
        "noSectionsFound": "Keine passenden Abschnitte gefunden.",
        "prevSection": "Vorheriger Abschnitt",
        "nextSection": "Nächster Abschnitt",
        "copied": "Kopiert!",
        "copy": "Code kopieren",
        "endpoints": "Endpunkte",
        "tocTitle": "Inhaltsverzeichnis"
    },
    "ja": {
        "searchPlaceholder": "ドキュメントを検索（例: Ollama、Fallback、Fusion、APIキー）...",
        "noSectionsFound": "一致するセクションが見つかりません。",
        "prevSection": "前のセクション",
        "nextSection": "次のセクション",
        "copied": "コピー完了！",
        "copy": "コードをコピー",
        "endpoints": "エンドポイント",
        "tocTitle": "目次"
    },
    "pt": {
        "searchPlaceholder": "Pesquisar documentação (ex: Ollama, Fallback, Fusion)...",
        "noSectionsFound": "Nenhuma seção correspondente encontrada.",
        "prevSection": "Seção anterior",
        "nextSection": "Próxima seção",
        "copied": "Copiado!",
        "copy": "Copiar código",
        "endpoints": "Endpoints",
        "tocTitle": "Índice da Documentação"
    },
    "ar": {
        "searchPlaceholder": "بحث في التوثيق (مثل Ollama, Fallback, Fusion, مفاتيح API)...",
        "noSectionsFound": "لم يتم العثور على أقسام مطابقة.",
        "prevSection": "القسم السابق",
        "nextSection": "القسم التالي",
        "copied": "تم النسخ!",
        "copy": "نسخ الكود",
        "endpoints": "نقاط النهاية",
        "tocTitle": "فهرس التوثيق"
    },
    "hi": {
        "searchPlaceholder": "दस्तावेज़ खोजें (उदा. Ollama, Fallback, Fusion, API key)...",
        "noSectionsFound": "कोई मेल खाता अनुभाग नहीं मिला।",
        "prevSection": "पिछला अनुभाग",
        "nextSection": "अगला अनुभाग",
        "copied": "कॉपी किया गया!",
        "copy": "कोड कॉपी करें",
        "endpoints": "एंडपॉइंट्स",
        "tocTitle": "दस्तावेज़ सूची"
    },
    "bn": {
        "searchPlaceholder": "ডকুমেন্টেশন অনুসন্ধান করুন (যেমন Ollama, Fallback, Fusion)...",
        "noSectionsFound": "কোনো বিভাগ পাওয়া যায়নি।",
        "prevSection": "পূর্ববর্তী বিভাগ",
        "nextSection": "পরবর্তী বিভাগ",
        "copied": "কপি করা হয়েছে!",
        "copy": "কোড কপি করুন",
        "endpoints": "এন্ডপয়েন্ট",
        "tocTitle": "সূচিপত্র"
    }
}

ALL_RAW_SECTIONS = SECTIONS_PART1 + SECTIONS_PART2

def build_section_for_lang(sec, lang):
    title = sec["titles"].get(lang) or sec["titles"].get("en", sec["id"])
    description = sec["descriptions"].get(lang) or sec["descriptions"].get("en", "")
    badge = sec.get("badge")
    group = sec.get("group", "general")
    
    highlights_dict = sec.get("highlights", {})
    highlights = highlights_dict.get(lang) or highlights_dict.get("en", [])

    subsections = []
    for sub in sec.get("subsections", []):
        sub_title = sub["titles"].get(lang) or sub["titles"].get("en", "")
        sub_desc = ""
        if "descriptions" in sub:
            sub_desc = sub["descriptions"].get(lang) or sub["descriptions"].get("en", "")
        
        sub_item = {"title": sub_title}
        if sub_desc:
            sub_item["description"] = sub_desc
            
        if "code" in sub:
            sub_item["code"] = sub["code"]
            
        if "table" in sub:
            t = sub["table"]
            headers = t.get("headers", [])
            if isinstance(headers, dict):
                headers = headers.get(lang) or headers.get("en", [])
            rows = t.get("rows", [])
            if isinstance(rows, dict):
                rows = rows.get(lang) or rows.get("en", [])
            sub_item["table"] = {"headers": headers, "rows": rows}
            
        if "bullets" in sub:
            b = sub["bullets"]
            if isinstance(b, dict):
                b = b.get(lang) or b.get("en", [])
            sub_item["bullets"] = b
            
        if "callout" in sub:
            c = sub["callout"]
            c_type = c.get("type", "info")
            c_title = ""
            if "titles" in c:
                c_title = c["titles"].get(lang) or c["titles"].get("en", "")
            c_text = ""
            if "texts" in c:
                c_text = c["texts"].get(lang) or c["texts"].get("en", "")
            elif "text" in c:
                c_text = c["text"]
            sub_item["callout"] = {"type": c_type, "title": c_title, "text": c_text}
            
        subsections.append(sub_item)

    out = {
        "id": sec["id"],
        "title": title,
        "group": group,
        "description": description,
        "subsections": subsections
    }
    if badge:
        out["badge"] = badge
    if highlights:
        out["highlights"] = highlights
    return out

out_dir = os.path.join(script_dir, "..", "src", "i18n", "docs")
os.makedirs(out_dir, exist_ok=True)

print(f"Total sections defined: {len(ALL_RAW_SECTIONS)}")

for lang in LANGUAGES:
    content = {
        "ui": UI_STRINGS[lang],
        "sections": [build_section_for_lang(sec, lang) for sec in ALL_RAW_SECTIONS]
    }
    
    file_content = f"""import {{ DocContent }} from "./types";

export const {lang}: DocContent = {json.dumps(content, ensure_ascii=False, indent=2)};
"""
    file_path = os.path.join(out_dir, f"{lang}.ts")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(file_content)
    print(f"Written: {file_path} ({len(content['sections'])} sections)")

index_content = f"""import {{ Language }} from "../types";
import {{ DocContent }} from "./types";
import {{ en }} from "./en";
import {{ ru }} from "./ru";
import {{ uk }} from "./uk";
import {{ be }} from "./be";
import {{ zh }} from "./zh";
import {{ es }} from "./es";
import {{ fr }} from "./fr";
import {{ de }} from "./de";
import {{ ja }} from "./ja";
import {{ pt }} from "./pt";
import {{ ar }} from "./ar";
import {{ hi }} from "./hi";
import {{ bn }} from "./bn";

export * from "./types";

export const docsTranslations: Record<Language, DocContent> = {{
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
}};
"""
with open(os.path.join(out_dir, "index.ts"), "w", encoding="utf-8") as f:
    f.write(index_content)
print("Written: index.ts")
