import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, Copy, CopyPlus, ListChecks, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { ImageUpload } from "@/components/image-upload";
import { LanguageTabs, useLanguageTabs, useTranslatedField } from "@/components/lang-tabs";
import { PageHeader } from "@/components/layout";
import { MarkdownField } from "@/components/markdown-field";
import { SortableList, SortableRow } from "@/components/sortable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DrawerContent,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { EmptyState, Label, Skeleton, Switch } from "@/components/ui/misc";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Bot, Vacancy, VacancyStatus } from "@/lib/types";
import { salaryLabel } from "@/lib/utils";

const NO_BRANCH = "__none__";
const ALL = "__all__";

const EMPTY: Partial<Vacancy> = {
  title: "",
  description: "",
  city: "",
  employment_type: "",
  currency: "UZS",
  status: "draft",
  branch_id: null,
  is_hot: false,
  photo_url: "",
};

const STATUS_VARIANT: Record<VacancyStatus, "success" | "secondary" | "outline"> = {
  active: "success",
  draft: "secondary",
  archived: "outline",
};

export default function VacanciesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [branchFilter, setBranchFilter] = useState<string>(ALL);
  const [editing, setEditing] = useState<Partial<Vacancy> | null>(null);
  const [duplicating, setDuplicating] = useState<Vacancy | null>(null);
  const [duplicateTarget, setDuplicateTarget] = useState<string>(NO_BRANCH);
  const [deleting, setDeleting] = useState<Vacancy | null>(null);

  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });
  const branches = useQuery({ queryKey: ["branches"], queryFn: api.branches.list });
  const bot = useQuery<Bot | null>({
    queryKey: ["bot"],
    queryFn: () => api.bot.get().catch(() => null),
    retry: false,
  });

  const vacancyParams =
    branchFilter === ALL
      ? {}
      : { branch_id: branchFilter === NO_BRANCH ? "null" : branchFilter };

  const vacancies = useQuery({
    queryKey: ["vacancies", branchFilter],
    queryFn: () => api.vacancies.list(vacancyParams),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["vacancies"] });

  const save = useMutation({
    mutationFn: (v: Partial<Vacancy>) => {
      const payload = {
        title: v.title?.trim(),
        description: v.description ?? "",
        city: v.city?.trim() || null,
        employment_type: v.employment_type?.trim() || null,
        salary_from: v.salary_from ?? null,
        salary_to: v.salary_to ?? null,
        currency: v.currency || "UZS",
        status: v.status,
        branch_id: v.branch_id ?? null,
        is_hot: v.is_hot ?? false,
        photo_url: v.photo_url?.trim() || null,
        translations: v.translations ?? {},
      };
      // `clear_branch` tells the API that a null branch_id means "detach", not "unchanged".
      return v.id
        ? api.vacancies.update(v.id, { ...payload, clear_branch: payload.branch_id === null })
        : api.vacancies.create(payload);
    },
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const duplicate = useMutation({
    mutationFn: ({ id, branchId }: { id: string; branchId: string }) =>
      api.vacancies.duplicate(id, { branch_id: branchId === NO_BRANCH ? null : branchId }),
    onSuccess: async () => {
      await invalidate();
      setDuplicating(null);
      toast.success(t("toast.created"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: api.vacancies.remove,
    onSuccess: async () => {
      await invalidate();
      setDeleting(null);
      toast.success(t("toast.deleted"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reorder = useMutation({
    mutationFn: api.vacancies.reorder,
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: ["vacancies", branchFilter] });
      const previous = qc.getQueryData<Vacancy[]>(["vacancies", branchFilter]);
      if (previous) {
        const byId = new Map(previous.map((v) => [v.id, v]));
        qc.setQueryData(
          ["vacancies", branchFilter],
          ids.map((id) => byId.get(id)).filter(Boolean) as Vacancy[],
        );
      }
      return { previous };
    },
    onError: (e: Error, _ids, context) => {
      if (context?.previous) qc.setQueryData(["vacancies", branchFilter], context.previous);
      toast.error(e.message);
    },
    onSuccess: () => toast.success(t("toast.orderSaved")),
  });

  const list = vacancies.data ?? [];
  const branchList = branches.data ?? [];

  return (
    <>
      <PageHeader
        title={t("vacancies.title")}
        action={
          <Button onClick={() => setEditing({ ...EMPTY })}>
            <Plus className="h-4 w-4" /> {t("vacancies.add")}
          </Button>
        }
      />

      {branchList.length > 0 && (
        <div className="mb-4 max-w-xs">
          <Select value={branchFilter} onValueChange={setBranchFilter}>
            <SelectTrigger>
              <SelectValue placeholder={t("vacancies.filterByBranch")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{t("common.all")}</SelectItem>
              <SelectItem value={NO_BRANCH}>{t("common.none")}</SelectItem>
              {branchList.map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {vacancies.isPending ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={t("vacancies.empty")}
          description={t("vacancies.emptyDesc")}
          action={
            <Button onClick={() => setEditing({ ...EMPTY })}>
              <Plus className="h-4 w-4" /> {t("vacancies.add")}
            </Button>
          }
        />
      ) : (
        <SortableList items={list} onReorder={(ids) => reorder.mutate(ids)}>
          {(vacancy) => (
            <SortableRow key={vacancy.id} id={vacancy.id}>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{vacancy.title}</span>
                  <Badge variant={STATUS_VARIANT[vacancy.status]}>
                    {t(
                      `vacancies.status${vacancy.status.charAt(0).toUpperCase()}${vacancy.status.slice(1)}`,
                    )}
                  </Badge>
                  {vacancy.is_hot && <Badge variant="warning">{t("vacancies.isHot")}</Badge>}
                  {vacancy.branch_name && <Badge variant="outline">{vacancy.branch_name}</Badge>}
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {[
                    vacancy.city,
                    salaryLabel(vacancy.salary_from, vacancy.salary_to, vacancy.currency),
                    `${t("vacancies.applications")}: ${vacancy.application_count}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>

              <div className="flex shrink-0 gap-1">
                {bot.data && vacancy.deep_link && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title={t("vacancies.deepLink")}
                    onClick={() => {
                      navigator.clipboard.writeText(vacancy.deep_link!);
                      toast.success(t("toast.linkCopied"));
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                )}
                <Button asChild variant="ghost" size="icon" title={t("vacancies.questions")}>
                  <Link to={`/vacancies/${vacancy.id}/questions`}>
                    <ListChecks className="h-4 w-4" />
                  </Link>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  title={t("vacancies.duplicate")}
                  onClick={() => {
                    setDuplicating(vacancy);
                    setDuplicateTarget(NO_BRANCH);
                  }}
                >
                  <CopyPlus className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setEditing(vacancy)}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setDeleting(vacancy)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </SortableRow>
          )}
        </SortableList>
      )}

      {/* Create / edit drawer */}
      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DrawerContent>
          <DialogHeader>
            <DialogTitle>{editing?.id ? t("common.edit") : t("vacancies.add")}</DialogTitle>
          </DialogHeader>

          {editing && (
            <VacancyForm
              editing={editing}
              setEditing={setEditing}
              branchList={branchList}
              enabledLanguages={company.data?.enabled_languages ?? ["ru"]}
              baseLanguage={company.data?.default_language ?? "ru"}
              saving={save.isPending}
              onCancel={() => setEditing(null)}
              onSubmit={() => save.mutate(editing)}
              t={t}
            />
          )}
        </DrawerContent>
      </Dialog>


      {/* Duplicate dialog */}
      <Dialog open={Boolean(duplicating)} onOpenChange={(open) => !open && setDuplicating(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("vacancies.duplicateTitle")}</DialogTitle>
            <DialogDescription>{t("vacancies.duplicateDesc")}</DialogDescription>
          </DialogHeader>

          <Select value={duplicateTarget} onValueChange={setDuplicateTarget}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_BRANCH}>{t("common.none")}</SelectItem>
              {branchList.map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setDuplicating(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={duplicate.isPending}
              onClick={() =>
                duplicating &&
                duplicate.mutate({ id: duplicating.id, branchId: duplicateTarget })
              }
            >
              {t("common.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("common.delete")}</DialogTitle>
            <DialogDescription>{deleting?.title}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleting(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => deleting && remove.mutate(deleting.id)}
            >
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Vacancy editor with one tab per published language.
 *
 *  Only the translatable fields switch per tab — salary, status and branch are language-
 *  independent, so they stay visible on every tab rather than being duplicated per language.
 */
function VacancyForm({
  editing,
  setEditing,
  branchList,
  enabledLanguages,
  baseLanguage,
  saving,
  onCancel,
  onSubmit,
  t,
}: {
  editing: Partial<Vacancy>;
  setEditing: (v: Partial<Vacancy>) => void;
  branchList: { id: string; name: string }[];
  enabledLanguages: string[];
  baseLanguage: string;
  saving: boolean;
  onCancel: () => void;
  onSubmit: () => void;
  t: (key: string) => string;
}) {
  const { ordered, active, setActive } = useLanguageTabs(enabledLanguages, baseLanguage);
  const field = useTranslatedField(editing, setEditing, active, baseLanguage);

  return (
    <form
      className="flex flex-1 flex-col gap-4 overflow-y-auto"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <LanguageTabs
        languages={ordered}
        active={active}
        onChange={setActive}
        base={baseLanguage}
        translations={editing.translations ?? {}}
        fields={["title", "description", "city", "employment_type"]}
      />

      <div className="space-y-2">
        <Label htmlFor="title">{t("vacancies.name")}</Label>
        <Input
          id="title"
          value={field.value("title")}
          placeholder={field.isBase ? "" : String(editing.title ?? "")}
          onChange={(e) => field.setValue("title", e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">{t("vacancies.description")}</Label>
        <MarkdownField
          id="description"
          rows={5}
          value={field.value("description")}
          placeholder={field.isBase ? "" : String(editing.description ?? "")}
          onChange={(v) => field.setValue("description", v)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="city">{t("vacancies.city")}</Label>
          <Input
            id="city"
            value={field.value("city")}
            placeholder={field.isBase ? "" : String(editing.city ?? "")}
            onChange={(e) => field.setValue("city", e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="employment">{t("vacancies.employment")}</Label>
          <Input
            id="employment"
            placeholder={field.isBase ? "full_time" : String(editing.employment_type ?? "")}
            value={field.value("employment_type")}
            onChange={(e) => field.setValue("employment_type", e.target.value)}
          />
        </div>
      </div>

      {/* Language-independent fields. */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>{t("vacancies.branch")}</Label>
          <Select
            value={editing.branch_id ?? NO_BRANCH}
            onValueChange={(v) =>
              setEditing({ ...editing, branch_id: v === NO_BRANCH ? null : v })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_BRANCH}>{t("common.none")}</SelectItem>
              {branchList.map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>{t("vacancies.status")}</Label>
          <Select
            value={editing.status ?? "draft"}
            onValueChange={(v) => setEditing({ ...editing, status: v as VacancyStatus })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">{t("vacancies.statusDraft")}</SelectItem>
              <SelectItem value="active">{t("vacancies.statusActive")}</SelectItem>
              <SelectItem value="archived">{t("vacancies.statusArchived")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="from">{t("vacancies.salaryFrom")}</Label>
          <Input
            id="from"
            type="number"
            min={0}
            value={editing.salary_from ?? ""}
            onChange={(e) =>
              setEditing({
                ...editing,
                salary_from: e.target.value ? Number(e.target.value) : null,
              })
            }
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="to">{t("vacancies.salaryTo")}</Label>
          <Input
            id="to"
            type="number"
            min={0}
            value={editing.salary_to ?? ""}
            onChange={(e) =>
              setEditing({
                ...editing,
                salary_to: e.target.value ? Number(e.target.value) : null,
              })
            }
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="currency">{t("vacancies.currency")}</Label>
          <Input
            id="currency"
            value={editing.currency ?? "UZS"}
            onChange={(e) => setEditing({ ...editing, currency: e.target.value })}
          />
        </div>
      </div>

      <ImageUpload
        label={t("vacancies.photoUrl")}
        value={editing.photo_url}
        onChange={(url) => setEditing({ ...editing, photo_url: url })}
      />

      <div className="flex items-center justify-between rounded-lg border p-3">
        <div>
          <Label htmlFor="ishot">{t("vacancies.isHot")}</Label>
          <p className="mt-1 text-xs text-muted-foreground">{t("vacancies.isHotHint")}</p>
        </div>
        <Switch
          id="ishot"
          checked={editing.is_hot ?? false}
          onCheckedChange={(checked) => setEditing({ ...editing, is_hot: checked })}
        />
      </div>

      <DialogFooter className="mt-auto pt-4">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button type="submit" disabled={!editing.title?.trim() || saving}>
          {t("common.save")}
        </Button>
      </DialogFooter>
    </form>
  );
}
