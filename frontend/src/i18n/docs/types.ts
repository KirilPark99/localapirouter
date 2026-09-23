export interface DocCodeSnippet {
  title?: string;
  lang?: string;
  content: string;
}

export interface DocTable {
  headers: string[];
  rows: string[][];
}

export interface DocSubsection {
  title: string;
  description?: string;
  code?: DocCodeSnippet;
  table?: DocTable;
  bullets?: string[];
  callout?: {
    type: "info" | "warning" | "success";
    title?: string;
    text: string;
  };
}

export interface DocSectionContent {
  id: string;
  title: string;
  group: string;
  description: string;
  badge?: string;
  highlights?: string[];
  subsections: DocSubsection[];
}

export interface DocUiStrings {
  searchPlaceholder: string;
  noSectionsFound: string;
  prevSection: string;
  nextSection: string;
  copied: string;
  copy: string;
  endpoints: string;
  tocTitle: string;
}

export interface DocContent {
  ui: DocUiStrings;
  sections: DocSectionContent[];
}
