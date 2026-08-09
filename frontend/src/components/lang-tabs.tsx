/** Language tabs for translatable forms.
 *
 *  The base-language tab edits the record's own columns; every other tab edits an entry in
 *  `translations`. A dot on a tab means that language has at least one field filled in, so
 *  a half-translated vacancy is obvious at a glance instead of needing a click per tab.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Translations } from "@/lib/types";
import { LANGUAGE_LABELS } from "@/lib/types";
import { cn } from "@/lib/utils";

export function useLanguageTabs(enabled: string[], base: string) {
  // Ordered with the base language first — it is the fallback, so it is what you fill first.
  const ordered = [base, ...enabled.filter((l) => l !== base)];
  const [active, setActive] = useState(base);
  return { ordered, active: ordered.includes(active) ? active : base, setActive };
}

export function LanguageTabs({
  languages,
  active,
  onChange,
  base,
  translations,
  fields,
}: {
  languages: string[];
  active: string;
  onChange: (lang: string) => void;
  base: string;
  translations: Translations;
  fields: string[];
}) {
  const { t } = useTranslation();
  if (languages.length < 2) return null;

  const hasContent = (lang: string) =>
    lang === base || fields.some((f) => String(translations?.[lang]?.[f] ?? "").trim());

  return (
    <div className="flex flex-wrap items-center gap-1 rounded-lg bg-muted p-1">
      {languages.map((lang) => (
        <button
          key={lang}
          type="button"
          onClick={() => onChange(lang)}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-sm font-medium transition-colors",
            active === lang
              ? "bg-background text-foreground shadow"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {LANGUAGE_LABELS[lang] ?? lang}
          {lang === base ? (
            <span className="text-[10px] uppercase text-muted-foreground">
              {t("langTabs.base")}
            </span>
          ) : (
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                hasContent(lang) ? "bg-emerald-500" : "bg-muted-foreground/40",
              )}
              title={hasContent(lang) ? t("langTabs.filled") : t("langTabs.empty")}
            />
          )}
        </button>
      ))}
    </div>
  );
}

/** Read/write a single field for the active language.
 *
 *  On the base tab the value lives on the record itself; on any other tab it lives under
 *  `translations[lang]`. Callers get one `value`/`onChange` pair and never branch on it.
 */
export function useTranslatedField<T extends { translations?: Translations | null }>(
  draft: T,
  setDraft: (next: T) => void,
  activeLang: string,
  baseLang: string,
) {
  const isBase = activeLang === baseLang;

  const value = (field: string): string => {
    if (isBase) return String((draft as Record<string, unknown>)[field] ?? "");
    return String(draft.translations?.[activeLang]?.[field] ?? "");
  };

  const setValue = (field: string, next: string) => {
    if (isBase) {
      setDraft({ ...draft, [field]: next });
      return;
    }
    const translations: Translations = { ...(draft.translations ?? {}) };
    translations[activeLang] = { ...(translations[activeLang] ?? {}), [field]: next };
    setDraft({ ...draft, translations });
  };

  return { isBase, value, setValue };
}
