import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase,
  Copy,
  CopyPlus,
  ListChecks,
  MoreHorizontal,
  Pencil,
  Plus,
  QrCode,
  Trash2,
} from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState, Label, Skeleton, Switch } from "@/components/ui/misc";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Bot, RecruitmentCampaign, Vacancy, VacancyStatus } from "@/lib/types";
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
  const [campaignVacancy, setCampaignVacancy] = useState<Vacancy | null>(null);
  const [campaignName, setCampaignName] = useState("");
  const [campaignSource, setCampaignSource] = useState("");

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
  const campaigns = useQuery({
    queryKey: ["campaigns", campaignVacancy?.id],
    queryFn: () => api.campaigns.list(campaignVacancy!.id),
    enabled: Boolean(campaignVacancy),
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

  const createCampaign = useMutation({
    mutationFn: () => api.campaigns.create({
      vacancy_id: campaignVacancy!.id,
      name: campaignName.trim(),
      source: campaignSource.trim() || null,
    }),
    onSuccess: async () => {
      setCampaignName("");
      setCampaignSource("");
      await qc.invalidateQueries({ queryKey: ["campaigns", campaignVacancy?.id] });
      toast.success(t("campaigns.created"));
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const updateCampaign = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      api.campaigns.update(id, { is_active: isActive }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["campaigns", campaignVacancy?.id] });
    },
    onError: (error: Error) => toast.error(error.message),
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
            <SelectTrigger aria-label={t("vacancies.filterByBranch")}>
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

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label={t("common.actions")}>
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {bot.data && vacancy.deep_link && (
                    <DropdownMenuItem
                      onSelect={() => {
                        navigator.clipboard.writeText(vacancy.deep_link!);
                        toast.success(t("toast.linkCopied"));
                      }}
                    >
                      <Copy /> {t("vacancies.deepLink")}
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem
                    disabled={!bot.data || vacancy.status !== "active"}
                    onSelect={() => setCampaignVacancy(vacancy)}
                  >
                    <QrCode /> {t("campaigns.manage")}
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to={`/vacancies/${vacancy.id}/questions`}>
                      <ListChecks /> {t("vacancies.questions")}
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() => {
                      setDuplicating(vacancy);
                      setDuplicateTarget(NO_BRANCH);
                    }}
                  >
                    <CopyPlus /> {t("vacancies.duplicate")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => setEditing(vacancy)}>
                    <Pencil /> {t("common.edit")}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onSelect={() => setDeleting(vacancy)}
                  >
                    <Trash2 /> {t("common.delete")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
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
            <SelectTrigger aria-label={t("vacancies.branch")}>
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

      <Dialog
        open={Boolean(campaignVacancy)}
        onOpenChange={(open) => {
          if (!open) {
            setCampaignVacancy(null);
            setCampaignName("");
            setCampaignSource("");
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("campaigns.title")}</DialogTitle>
            <DialogDescription>{campaignVacancy?.title}</DialogDescription>
          </DialogHeader>

          <form
            className="grid gap-3 rounded-lg border p-3 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (campaignName.trim() && !createCampaign.isPending) createCampaign.mutate();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="campaign-name">{t("campaigns.name")}</Label>
              <Input id="campaign-name" value={campaignName} onChange={(event) => setCampaignName(event.target.value)} maxLength={160} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="campaign-source">{t("campaigns.source")}</Label>
              <Input id="campaign-source" value={campaignSource} onChange={(event) => setCampaignSource(event.target.value)} maxLength={100} />
            </div>
            <Button type="submit" disabled={!campaignName.trim() || createCampaign.isPending} className="sm:col-span-2 sm:w-fit">
              <Plus className="h-4 w-4" /> {t("campaigns.create")}
            </Button>
          </form>

          {campaigns.isPending ? (
            <Skeleton className="h-32" />
          ) : campaigns.data?.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("campaigns.empty")}</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {(campaigns.data ?? []).map((campaign) => (
                <CampaignCard
                  key={campaign.id}
                  campaign={campaign}
                  t={t}
                  pending={updateCampaign.isPending}
                  onToggle={() => updateCampaign.mutate({ id: campaign.id, isActive: !campaign.is_active })}
                />
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function CampaignCard({
  campaign,
  t,
  pending,
  onToggle,
}: {
  campaign: RecruitmentCampaign;
  t: (key: string, options?: Record<string, unknown>) => string;
  pending: boolean;
  onToggle: () => void;
}) {
  const [qrSrc, setQrSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!campaign.deep_link) return;
    let alive = true;
    QRCode.toDataURL(campaign.deep_link, { width: 240, margin: 1, color: { dark: "#050507", light: "#FFFFFF" } })
      .then((value) => alive && setQrSrc(value))
      .catch(() => alive && setQrSrc(null));
    return () => { alive = false; };
  }, [campaign.deep_link]);

  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium">{campaign.name}</p>
          {campaign.source && <p className="truncate text-xs text-muted-foreground">{campaign.source}</p>}
        </div>
        <Badge variant={campaign.is_active ? "success" : "outline"}>{campaign.is_active ? t("campaigns.active") : t("campaigns.paused")}</Badge>
      </div>
      <div className="mt-3 flex gap-3">
        {qrSrc && <img src={qrSrc} alt={t("campaigns.qrAlt", { name: campaign.name })} className="h-24 w-24 rounded bg-white p-1" />}
        <div className="min-w-0 flex-1 text-sm">
          <p>{t("campaigns.applications", { count: campaign.applications_count })}</p>
          <p className="mt-1 break-all text-xs text-muted-foreground">{campaign.deep_link ?? t("campaigns.botMissing")}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={!campaign.deep_link} onClick={() => campaign.deep_link && navigator.clipboard.writeText(campaign.deep_link).then(() => toast.success(t("toast.linkCopied")))}>
          <Copy className="h-4 w-4" /> {t("campaigns.copy")}
        </Button>
        <Button size="sm" variant="ghost" disabled={pending} onClick={onToggle}>
          {campaign.is_active ? t("campaigns.pause") : t("campaigns.resume")}
        </Button>
      </div>
    </div>
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
            <SelectTrigger aria-label={t("vacancies.branch")}>
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
            <SelectTrigger aria-label={t("vacancies.status")}>
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
