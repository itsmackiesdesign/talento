import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase,
  Copy,
  CopyPlus,
  ListChecks,
  MoreHorizontal,
  Pencil,
  Plus,
  Send,
  Trash2,
  Users,
} from "lucide-react";
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
import { Input, Textarea } from "@/components/ui/input";
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
import type {
  ApplicationStatusOut,
  Bot,
  CampaignCandidate,
  CampaignAudience,
  Vacancy,
  VacancyCampaignTarget,
  VacancyStatus,
} from "@/lib/types";
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
  branch_ids: [],
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
        branch_ids: v.branch_ids ?? (v.branch_id ? [v.branch_id] : []),
        is_hot: v.is_hot ?? false,
        photo_url: v.photo_url?.trim() || null,
        translations: v.translations ?? {},
      };
      return v.id
        ? api.vacancies.update(v.id, payload)
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
                  {vacancy.branch_names.map((name) => (
                    <Badge key={name} variant="outline">{name}</Badge>
                  ))}
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
                  {bot.data && vacancy.status === "active" && (
                    <DropdownMenuItem onSelect={() => setCampaignVacancy(vacancy)}>
                      <Send /> {t("campaign.sendNotification")}
                    </DropdownMenuItem>
                  )}
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

      <Dialog
        open={Boolean(campaignVacancy)}
        onOpenChange={(open) => !open && setCampaignVacancy(null)}
      >
        <DrawerContent>
          {campaignVacancy && (
            <CampaignWizard
              vacancy={campaignVacancy}
              vacancies={list}
              branches={branchList}
              enabledLanguages={company.data?.enabled_languages ?? ["ru"]}
              onClose={() => setCampaignVacancy(null)}
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

const EMPTY_TARGET: VacancyCampaignTarget = {
  audience_type: "everyone",
  source_vacancy_ids: [],
  source_status_ids: [],
  branch_ids: [],
  languages: [],
  excluded_candidate_ids: [],
  exclude_applied: false,
  exclude_rejected: false,
};

function toggleId(values: string[], id: string) {
  return values.includes(id) ? values.filter((value) => value !== id) : [...values, id];
}

function CampaignWizard({
  vacancy,
  vacancies,
  branches,
  enabledLanguages,
  onClose,
}: {
  vacancy: Vacancy;
  vacancies: Vacancy[];
  branches: { id: string; name: string }[];
  enabledLanguages: string[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const [intro, setIntro] = useState("");
  const [target, setTarget] = useState<VacancyCampaignTarget>(EMPTY_TARGET);
  const [schedule, setSchedule] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [candidateSearch, setCandidateSearch] = useState("");
  const statuses = useQuery<ApplicationStatusOut[]>({
    queryKey: ["application-statuses"],
    queryFn: api.applicationStatuses.list,
  });
  const candidates = useQuery<CampaignCandidate[]>({
    queryKey: ["campaign-candidates", candidateSearch],
    queryFn: () => api.vacancyCampaigns.candidates(candidateSearch.trim() || undefined),
    enabled: step === 2,
  });
  const targetIsValid =
    target.audience_type === "everyone" ||
    (target.audience_type === "selected_vacancies" && target.source_vacancy_ids.length > 0) ||
    (target.audience_type === "selected_statuses" && target.source_status_ids.length > 0);
  const estimate = useQuery({
    queryKey: ["campaign-estimate", vacancy.id, target],
    queryFn: () => api.vacancies.estimateCampaign(vacancy.id, target),
    enabled: step >= 2 && targetIsValid,
  });
  const create = useMutation({
    mutationFn: () =>
      api.vacancies.createCampaign(vacancy.id, {
        ...target,
        intro_text: intro.trim(),
        scheduled_at: schedule && scheduledAt ? new Date(scheduledAt).toISOString() : null,
      }),
    onSuccess: () => {
      toast.success(schedule ? t("campaign.scheduled") : t("campaign.queued"));
      onClose();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const setAudience = (audience_type: CampaignAudience) =>
    setTarget({
      ...target,
      audience_type,
      source_vacancy_ids: audience_type === "selected_vacancies" ? target.source_vacancy_ids : [],
      source_status_ids: audience_type === "selected_statuses" ? target.source_status_ids : [],
    });

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <DialogHeader>
        <DialogTitle>{t("campaign.title")}</DialogTitle>
        <DialogDescription>{vacancy.title}</DialogDescription>
      </DialogHeader>

      <div className="my-4 flex gap-2 text-xs">
        {[1, 2, 3].map((number) => (
          <div
            key={number}
            className={`h-1 flex-1 rounded-full ${number <= step ? "bg-primary" : "bg-muted"}`}
          />
        ))}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto pr-1">
        {step === 1 && (
          <>
            <div className="space-y-2">
              <Label htmlFor="campaign-intro">{t("campaign.intro")}</Label>
              <Textarea
                id="campaign-intro"
                rows={4}
                maxLength={1000}
                value={intro}
                placeholder={t("campaign.introPlaceholder")}
                onChange={(event) => setIntro(event.target.value)}
              />
            </div>
            <div className="overflow-hidden rounded-2xl border bg-muted/30">
              {vacancy.photo_url && (
                <img src={vacancy.photo_url} alt="" className="h-40 w-full object-cover" />
              )}
              <div className="space-y-2 p-4">
                <p className="text-xs font-medium uppercase text-muted-foreground">
                  {t("campaign.preview")}
                </p>
                {intro && <p className="whitespace-pre-wrap text-sm">{intro}</p>}
                <p className="font-semibold">💼 {vacancy.title}</p>
                {vacancy.branch_name && <p className="text-sm">🏢 {vacancy.branch_name}</p>}
                {vacancy.city && <p className="text-sm">📍 {vacancy.city}</p>}
                <Button type="button" size="sm" className="w-full" disabled>
                  {t("campaign.openVacancy")}
                </Button>
              </div>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className="space-y-2">
              <Label>{t("campaign.audience")}</Label>
              {(
                ["everyone", "selected_vacancies", "selected_statuses"] as CampaignAudience[]
              ).map((type) => (
                <button
                  type="button"
                  key={type}
                  onClick={() => setAudience(type)}
                  className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left ${
                    target.audience_type === type ? "border-primary bg-primary/5" : ""
                  }`}
                >
                  <span
                    className={`mt-0.5 h-4 w-4 rounded-full border ${
                      target.audience_type === type ? "border-4 border-primary" : ""
                    }`}
                  />
                  <span>
                    <span className="block text-sm font-medium">{t(`campaign.${type}`)}</span>
                    <span className="block text-xs text-muted-foreground">
                      {t(`campaign.${type}Hint`)}
                    </span>
                  </span>
                </button>
              ))}
            </div>

            {target.audience_type === "selected_vacancies" && (
              <PillPicker
                label={t("campaign.chooseVacancies")}
                values={target.source_vacancy_ids}
                items={vacancies.map((item) => ({ id: item.id, label: item.title }))}
                onToggle={(id) =>
                  setTarget({
                    ...target,
                    source_vacancy_ids: toggleId(target.source_vacancy_ids, id),
                  })
                }
              />
            )}
            {target.audience_type === "selected_statuses" && (
              <PillPicker
                label={t("campaign.chooseStatuses")}
                values={target.source_status_ids}
                items={(statuses.data ?? []).map((item) => ({ id: item.id, label: item.label }))}
                onToggle={(id) =>
                  setTarget({
                    ...target,
                    source_status_ids: toggleId(target.source_status_ids, id),
                  })
                }
              />
            )}

            <div className="space-y-3 rounded-xl border p-3">
              <Label>{t("campaign.exclusions")}</Label>
              <SwitchRow
                label={t("campaign.excludeApplied")}
                checked={target.exclude_applied}
                onChange={(value) => setTarget({ ...target, exclude_applied: value })}
              />
              <SwitchRow
                label={t("campaign.excludeRejected")}
                checked={target.exclude_rejected}
                onChange={(value) => setTarget({ ...target, exclude_rejected: value })}
              />
            </div>

            {branches.length > 0 && (
              <PillPicker
                label={t("campaign.filterBranches")}
                values={target.branch_ids}
                items={branches.map((item) => ({ id: item.id, label: item.name }))}
                onToggle={(id) =>
                  setTarget({ ...target, branch_ids: toggleId(target.branch_ids, id) })
                }
              />
            )}
            <PillPicker
              label={t("campaign.filterLanguages")}
              values={target.languages}
              items={enabledLanguages.map((language) => ({
                id: language,
                label: language.toUpperCase(),
              }))}
              onToggle={(id) =>
                setTarget({
                  ...target,
                  languages: toggleId(target.languages, id) as ("ru" | "uz" | "en")[],
                })
              }
            />

            <div className="space-y-2">
              <Label>{t("campaign.excludeSpecific")}</Label>
              <Input
                value={candidateSearch}
                placeholder={t("campaign.searchCandidate")}
                onChange={(event) => setCandidateSearch(event.target.value)}
              />
              {target.excluded_candidate_ids.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {t("campaign.excludedCount", {
                    count: target.excluded_candidate_ids.length,
                  })}
                </p>
              )}
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border p-2">
                {(candidates.data ?? []).map((candidate) => {
                  const selected = target.excluded_candidate_ids.includes(candidate.id);
                  return (
                    <button
                      key={candidate.id}
                      type="button"
                      className={`flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm ${
                        selected ? "bg-destructive/10 text-destructive" : "hover:bg-muted"
                      }`}
                      onClick={() =>
                        setTarget({
                          ...target,
                          excluded_candidate_ids: toggleId(
                            target.excluded_candidate_ids,
                            candidate.id,
                          ),
                        })
                      }
                    >
                      <span className="truncate">{candidate.first_name || t("campaign.unnamed")}</span>
                      <span className="ml-2 shrink-0 text-xs text-muted-foreground">
                        {candidate.telegram_username ? `@${candidate.telegram_username}` : ""}
                      </span>
                    </button>
                  );
                })}
                {!candidates.isFetching && (candidates.data?.length ?? 0) === 0 && (
                  <p className="p-2 text-center text-xs text-muted-foreground">
                    {t("campaign.noCandidates")}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3 rounded-xl bg-primary/5 p-4">
              <Users className="h-5 w-5 text-primary" />
              <div>
                <p className="text-xs text-muted-foreground">{t("campaign.estimated")}</p>
                <p className="text-lg font-semibold">
                  {estimate.isFetching ? "…" : (estimate.data?.count ?? 0)}
                </p>
              </div>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className="rounded-xl border p-4">
              <p className="text-sm text-muted-foreground">{t("campaign.willReceive")}</p>
              <p className="mt-1 text-3xl font-semibold">{estimate.data?.count ?? 0}</p>
            </div>
            <div className="space-y-3 rounded-xl border p-3">
              <SwitchRow label={t("campaign.schedule") } checked={schedule} onChange={setSchedule} />
              {schedule && (
                <Input
                  type="datetime-local"
                  value={scheduledAt}
                  min={new Date().toISOString().slice(0, 16)}
                  onChange={(event) => setScheduledAt(event.target.value)}
                />
              )}
            </div>
            <p className="text-xs text-muted-foreground">{t("campaign.consentNote")}</p>
          </>
        )}
      </div>

      <DialogFooter className="mt-4 pt-4">
        <Button type="button" variant="ghost" onClick={step === 1 ? onClose : () => setStep(step - 1)}>
          {step === 1 ? t("common.cancel") : t("common.back")}
        </Button>
        {step < 3 ? (
          <Button type="button" disabled={step === 2 && !targetIsValid} onClick={() => setStep(step + 1)}>
            {t("common.next")}
          </Button>
        ) : (
          <Button
            type="button"
            disabled={create.isPending || (schedule && !scheduledAt)}
            onClick={() => create.mutate()}
          >
            <Send className="h-4 w-4" />
            {schedule ? t("campaign.scheduleButton") : t("campaign.sendNow")}
          </Button>
        )}
      </DialogFooter>
    </div>
  );
}

function PillPicker({
  label,
  values,
  items,
  onToggle,
}: {
  label: string;
  values: string[];
  items: { id: string; label: string }[];
  onToggle: (id: string) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <Button
            key={item.id}
            type="button"
            size="sm"
            variant={values.includes(item.id) ? "default" : "outline"}
            onClick={() => onToggle(item.id)}
          >
            {item.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

function SwitchRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm">{label}</span>
      <Switch checked={checked} onCheckedChange={onChange} />
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
          <PillPicker
            label={t("vacancies.branches")}
            values={editing.branch_ids ?? (editing.branch_id ? [editing.branch_id] : [])}
            items={branchList.map((branch) => ({ id: branch.id, label: branch.name }))}
            onToggle={(id) =>
              setEditing({
                ...editing,
                branch_ids: toggleId(
                  editing.branch_ids ?? (editing.branch_id ? [editing.branch_id] : []),
                  id,
                ),
              })
            }
          />
          <p className="text-xs text-muted-foreground">{t("vacancies.branchesHint")}</p>
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
