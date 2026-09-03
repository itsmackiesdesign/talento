import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CopyPlus, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { LanguageTabs, useLanguageTabs } from "@/components/lang-tabs";
import { PageHeader } from "@/components/layout";
import { MarkdownField } from "@/components/markdown-field";
import { SortableList, SortableRow } from "@/components/sortable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DrawerContent,
} from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label, Skeleton, Switch, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { markdownToPreviewHtml } from "@/lib/markdown";
import {
  QUESTION_TYPES,
  type DatetimeMask,
  type Question,
  type QuestionType,
  type Translations,
} from "@/lib/types";

type Draft = Partial<Question> & { optionsText?: string };

const needsOptions = (type?: QuestionType) =>
  type === "single_choice" || type === "multi_choice";

const compatibleProfileField = (
  type: QuestionType | undefined,
  current: Question["profile_field"] | undefined,
): Question["profile_field"] => {
  if (type === "short_text" && current === "candidate_name") return current;
  if (type === "file" && current === "candidate_photo") return current;
  return null;
};

export default function QuestionsPage() {
  const { t } = useTranslation();
  const { id: vacancyId } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const [scope, setScope] = useState<"vacancy" | "common">("vacancy");
  const [editing, setEditing] = useState<Draft | null>(null);

  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });
  const vacancy = useQuery({
    queryKey: ["vacancy", vacancyId],
    queryFn: () => api.vacancies.get(vacancyId!),
    enabled: Boolean(vacancyId),
  });

  const scopeParam = scope === "vacancy" ? vacancyId! : "null";
  const questions = useQuery({
    queryKey: ["questions", scopeParam],
    queryFn: () => api.questions.list(scopeParam),
    enabled: Boolean(vacancyId),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["questions"] });

  const save = useMutation({
    mutationFn: (draft: Draft) => {
      const options = needsOptions(draft.type)
        ? (draft.optionsText ?? "")
            .split("\n")
            .map((o) => o.trim())
            .filter(Boolean)
        : null;
      const validation =
        draft.type === "number"
          ? {
              ...(draft.validation?.min != null ? { min: draft.validation.min } : {}),
              ...(draft.validation?.max != null ? { max: draft.validation.max } : {}),
            }
          : draft.type === "datetime"
            ? { mask: draft.validation?.mask ?? "date" }
            : null;

      // Translated option lists must line up 1:1 with the base list — the API rejects a
      // mismatch, and the form shows one input per base option to make that hard to get
      // wrong in the first place.
      const translations: Translations = {};
      for (const [lang, fields] of Object.entries(draft.translations ?? {})) {
        const entry: Record<string, string | string[]> = {};
        const text = String(fields.text ?? "").trim();
        if (text) entry.text = text;
        if (needsOptions(draft.type)) {
          const translated = (fields.options as string[] | undefined) ?? [];
          // Blank boxes fall back to the base wording rather than shipping an empty option.
          if (translated.some((o) => o?.trim())) {
            entry.options = (options ?? []).map((base, i) => translated[i]?.trim() || base);
          }
        }
        if (Object.keys(entry).length) translations[lang] = entry;
      }

      const payload = {
        text: draft.text?.trim(),
        type: draft.type,
        options,
        is_required: draft.is_required ?? true,
        is_filterable: needsOptions(draft.type) ? (draft.is_filterable ?? false) : false,
        profile_field: compatibleProfileField(draft.type, draft.profile_field),
        validation: validation && Object.keys(validation).length ? validation : null,
        translations,
      };

      return draft.id
        ? api.questions.update(draft.id, payload)
        : api.questions.create({
            ...payload,
            vacancy_id: scope === "vacancy" ? vacancyId : null,
          });
    },
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: api.questions.remove,
    onSuccess: async () => {
      await invalidate();
      toast.success(t("toast.deleted"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // A copy is independent from the moment it's created — editing either side afterwards
  // never touches the other, same as vacancy duplication.
  const copy = useMutation({
    mutationFn: (question: Question) =>
      api.questions.copy(question.id, scope === "vacancy" ? null : vacancyId!),
    onSuccess: async () => {
      await invalidate();
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reorder = useMutation({
    mutationFn: api.questions.reorder,
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: ["questions", scopeParam] });
      const previous = qc.getQueryData<Question[]>(["questions", scopeParam]);
      if (previous) {
        const byId = new Map(previous.map((q) => [q.id, q]));
        qc.setQueryData(
          ["questions", scopeParam],
          ids.map((id) => byId.get(id)).filter(Boolean) as Question[],
        );
      }
      return { previous };
    },
    onError: (e: Error, _ids, context) => {
      if (context?.previous) qc.setQueryData(["questions", scopeParam], context.previous);
      toast.error(e.message);
    },
    onSuccess: () => toast.success(t("toast.orderSaved")),
  });

  const list = questions.data ?? [];

  const baseLanguage = company.data?.default_language ?? "ru";
  const langTabs = useLanguageTabs(company.data?.enabled_languages ?? ["ru"], baseLanguage);
  const isBaseTab = langTabs.active === baseLanguage;

  // The base option list drives everything: translations are edited one box per base
  // option, so the two lists can never drift out of alignment.
  const baseOptions = (editing?.optionsText ?? "")
    .split("\n")
    .map((o) => o.trim())
    .filter(Boolean);

  const setTranslatedText = (next: string) => {
    if (!editing) return;
    if (isBaseTab) {
      setEditing({ ...editing, text: next });
      return;
    }
    const translations = { ...(editing.translations ?? {}) };
    translations[langTabs.active] = { ...(translations[langTabs.active] ?? {}), text: next };
    setEditing({ ...editing, translations });
  };

  const translatedOption = (index: number): string => {
    const options = editing?.translations?.[langTabs.active]?.options;
    return Array.isArray(options) ? (options[index] ?? "") : "";
  };

  const setTranslatedOption = (index: number, next: string) => {
    if (!editing) return;
    const translations = { ...(editing.translations ?? {}) };
    const entry = { ...(translations[langTabs.active] ?? {}) };
    const options = Array.isArray(entry.options) ? [...entry.options] : [];
    while (options.length < baseOptions.length) options.push("");
    options[index] = next;
    entry.options = options.slice(0, baseOptions.length);
    translations[langTabs.active] = entry;
    setEditing({ ...editing, translations });
  };

  const openEditor = (question?: Question) =>
    setEditing(
      question
        ? { ...question, optionsText: (question.options ?? []).join("\n") }
        : {
            text: "",
            type: "short_text",
            is_required: true,
            is_filterable: false,
            profile_field: null,
            optionsText: "",
            translations: {},
          },
    );

  return (
    <>
      <PageHeader
        title={t("questions.title")}
        description={vacancy.data?.title ?? t("questions.subtitle")}
        action={
          <div className="flex gap-2">
            <Button asChild variant="ghost">
              <Link to="/vacancies">
                <ArrowLeft className="h-4 w-4" /> {t("common.back")}
              </Link>
            </Button>
            <Button onClick={() => openEditor()}>
              <Plus className="h-4 w-4" /> {t("questions.add")}
            </Button>
          </div>
        }
      />

      <Tabs value={scope} onValueChange={(v) => setScope(v as "vacancy" | "common")}>
        <TabsList>
          <TabsTrigger value="vacancy">{t("questions.specific")}</TabsTrigger>
          <TabsTrigger value="common">{t("questions.common")}</TabsTrigger>
        </TabsList>

        <TabsContent value={scope}>
          {scope === "common" && (
            <p className="mb-3 text-sm text-muted-foreground">{t("questions.commonDesc")}</p>
          )}

          {questions.isPending ? (
            <div className="space-y-2">
              {[0, 1].map((i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : list.length === 0 ? (
            <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              {t("questions.empty")}
            </p>
          ) : (
            <SortableList items={list} onReorder={(ids) => reorder.mutate(ids)}>
              {(question) => (
                <SortableRow key={question.id} id={question.id}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className="truncate font-medium"
                        dangerouslySetInnerHTML={{ __html: markdownToPreviewHtml(question.text) }}
                      />
                      <Badge variant="outline">{t(`questions.types.${question.type}`)}</Badge>
                      {!question.is_required && (
                        <Badge variant="secondary">{t("common.optional")}</Badge>
                      )}
                      {question.is_filterable && (
                        <Badge variant="secondary">{t("questions.filterEnabled")}</Badge>
                      )}
                      {question.profile_field && (
                        <Badge variant="secondary">
                          {t(`questions.profileFields.${question.profile_field}`)}
                        </Badge>
                      )}
                    </div>
                    {question.options && (
                      <p className="truncate text-xs text-muted-foreground">
                        {question.options.join(" · ")}
                      </p>
                    )}
                    {question.validation && (
                      <p className="text-xs text-muted-foreground">
                        {question.validation.min != null && `min ${question.validation.min}`}
                        {question.validation.min != null && question.validation.max != null && " · "}
                        {question.validation.max != null && `max ${question.validation.max}`}
                        {question.validation.mask &&
                          t(`questions.datetimeMask${question.validation.mask.charAt(0).toUpperCase()}${question.validation.mask.slice(1)}`)}
                      </p>
                    )}
                  </div>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={t("common.actions")}>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        disabled={copy.isPending}
                        onSelect={() => copy.mutate(question)}
                      >
                        <CopyPlus />
                        {scope === "vacancy"
                          ? t("questions.copyToCommon")
                          : t("questions.copyToVacancy")}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onSelect={() => openEditor(question)}>
                        <Pencil /> {t("common.edit")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onSelect={() => remove.mutate(question.id)}
                      >
                        <Trash2 /> {t("common.delete")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </SortableRow>
              )}
            </SortableList>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DrawerContent>
          <DialogHeader>
            <DialogTitle>{editing?.id ? t("common.edit") : t("questions.add")}</DialogTitle>
          </DialogHeader>

          {editing && (
            <form
              className="flex flex-1 flex-col gap-4 overflow-y-auto"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate(editing);
              }}
            >
              <LanguageTabs
                languages={langTabs.ordered}
                active={langTabs.active}
                onChange={langTabs.setActive}
                base={baseLanguage}
                translations={editing.translations ?? {}}
                fields={["text", "options"]}
              />

              <div className="space-y-2">
                <Label htmlFor="qtext">{t("questions.text")}</Label>
                <MarkdownField
                  id="qtext"
                  value={
                    isBaseTab
                      ? (editing.text ?? "")
                      : String(editing.translations?.[langTabs.active]?.text ?? "")
                  }
                  placeholder={isBaseTab ? "" : (editing.text ?? "")}
                  onChange={setTranslatedText}
                />
              </div>

              {/* Answer type is language-independent, so it lives outside the tabs. */}
              <div className="space-y-2">
                <Label>{t("questions.type")}</Label>
                <Select
                  value={editing.type ?? "short_text"}
                  onValueChange={(v) => {
                    const type = v as QuestionType;
                    setEditing({
                      ...editing,
                      type,
                      is_filterable: needsOptions(type) ? (editing.is_filterable ?? false) : false,
                      profile_field: compatibleProfileField(type, editing.profile_field),
                    });
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {QUESTION_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>
                        {t(`questions.types.${type}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {needsOptions(editing.type) &&
                (isBaseTab ? (
                  <div className="space-y-2">
                    <Label htmlFor="options">{t("questions.options")}</Label>
                    <Textarea
                      id="options"
                      rows={5}
                      placeholder={"Утро\nВечер\nНочь"}
                      value={editing.optionsText ?? ""}
                      onChange={(e) => setEditing({ ...editing, optionsText: e.target.value })}
                    />
                    <p className="text-xs text-muted-foreground">2–10</p>
                  </div>
                ) : (
                  // One box per base option instead of a free textarea: the API requires the
                  // lists to be the same length, and this makes that structurally impossible
                  // to get wrong.
                  <div className="space-y-2">
                    <Label>{t("questions.options")}</Label>
                    {baseOptions.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        {t("questions.optionsBaseFirst")}
                      </p>
                    ) : (
                      baseOptions.map((base, index) => (
                        <Input
                          key={index}
                          value={translatedOption(index)}
                          placeholder={base}
                          onChange={(e) => setTranslatedOption(index, e.target.value)}
                        />
                      ))
                    )}
                  </div>
                ))}

              {editing.type === "number" && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="min">{t("questions.min")}</Label>
                    <Input
                      id="min"
                      type="number"
                      value={editing.validation?.min ?? ""}
                      onChange={(e) =>
                        setEditing({
                          ...editing,
                          validation: {
                            ...editing.validation,
                            min: e.target.value ? Number(e.target.value) : undefined,
                          },
                        })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max">{t("questions.max")}</Label>
                    <Input
                      id="max"
                      type="number"
                      value={editing.validation?.max ?? ""}
                      onChange={(e) =>
                        setEditing({
                          ...editing,
                          validation: {
                            ...editing.validation,
                            max: e.target.value ? Number(e.target.value) : undefined,
                          },
                        })
                      }
                    />
                  </div>
                </div>
              )}

              {editing.type === "datetime" && (
                <div className="space-y-2">
                  <Label>{t("questions.datetimeMask")}</Label>
                  <Select
                    value={editing.validation?.mask ?? "date"}
                    onValueChange={(v) =>
                      setEditing({
                        ...editing,
                        validation: { ...editing.validation, mask: v as DatetimeMask },
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="date">{t("questions.datetimeMaskDate")}</SelectItem>
                      <SelectItem value="datetime">
                        {t("questions.datetimeMaskDatetime")}
                      </SelectItem>
                      <SelectItem value="time">{t("questions.datetimeMaskTime")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {needsOptions(editing.type) && (
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label htmlFor="filterable">{t("questions.filterByThisQuestion")}</Label>
                    <p className="text-xs text-muted-foreground">
                      {t("questions.filterByThisQuestionHint")}
                    </p>
                  </div>
                  <Switch
                    id="filterable"
                    checked={editing.is_filterable ?? false}
                    onCheckedChange={(checked) =>
                      setEditing({ ...editing, is_filterable: checked })
                    }
                  />
                </div>
              )}

              {editing.type === "short_text" && (
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label htmlFor="candidate-name">
                      {t("questions.useAsCandidateName")}
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      {t("questions.useAsCandidateNameHint")}
                    </p>
                  </div>
                  <Switch
                    id="candidate-name"
                    checked={editing.profile_field === "candidate_name"}
                    onCheckedChange={(checked) =>
                      setEditing({
                        ...editing,
                        profile_field: checked ? "candidate_name" : null,
                      })
                    }
                  />
                </div>
              )}

              {editing.type === "file" && (
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label htmlFor="candidate-photo">
                      {t("questions.useAsCandidatePhoto")}
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      {t("questions.useAsCandidatePhotoHint")}
                    </p>
                  </div>
                  <Switch
                    id="candidate-photo"
                    checked={editing.profile_field === "candidate_photo"}
                    onCheckedChange={(checked) =>
                      setEditing({
                        ...editing,
                        profile_field: checked ? "candidate_photo" : null,
                      })
                    }
                  />
                </div>
              )}

              <div className="flex items-center justify-between rounded-lg border p-3">
                <Label htmlFor="required">{t("questions.isRequired")}</Label>
                <Switch
                  id="required"
                  checked={editing.is_required ?? true}
                  onCheckedChange={(checked) => setEditing({ ...editing, is_required: checked })}
                />
              </div>

              <DialogFooter className="mt-auto pt-4">
                <Button type="button" variant="ghost" onClick={() => setEditing(null)}>
                  {t("common.cancel")}
                </Button>
                <Button type="submit" disabled={!editing.text?.trim() || save.isPending}>
                  {t("common.save")}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DrawerContent>
      </Dialog>
    </>
  );
}
