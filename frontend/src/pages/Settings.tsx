import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Copy, Lock, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ImageUpload } from "@/components/image-upload";
import { LanguageTabs, useLanguageTabs, useTranslatedField } from "@/components/lang-tabs";
import { PageHeader } from "@/components/layout";
import { MarkdownField } from "@/components/markdown-field";
import { SortableList, SortableRow } from "@/components/sortable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  Label,
  Separator,
  Skeleton,
  Switch,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/misc";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { LANGUAGE_LABELS, SUPPORTED_LANGUAGES } from "@/lib/types";
import type { ApplicationStatusOut, Bot, Company, Language } from "@/lib/types";

function BotTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Partial<Bot>>({});
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });
  const bot = useQuery<Bot | null>({
    queryKey: ["bot"],
    queryFn: () => api.bot.get().catch(() => null),
    retry: false,
  });

  const webhook = useQuery({
    queryKey: ["webhook-status"],
    queryFn: api.bot.webhookStatus,
    enabled: Boolean(bot.data),
    retry: false,
  });

  useEffect(() => {
    if (bot.data) setDraft(bot.data);
  }, [bot.data]);

  const baseLanguage = company.data?.default_language ?? "ru";
  const langTabs = useLanguageTabs(company.data?.enabled_languages ?? ["ru"], baseLanguage);
  const field = useTranslatedField(draft, setDraft, langTabs.active, baseLanguage);

  const save = useMutation({
    mutationFn: () =>
      api.bot.update({
        welcome_message: draft.welcome_message ?? null,
        about_text: draft.about_text ?? null,
        after_apply_message: draft.after_apply_message ?? null,
        contacts_text: draft.contacts_text ?? null,
        translations: draft.translations ?? {},
        language: draft.language,
        notify_candidate_on_status: draft.notify_candidate_on_status,
        is_active: draft.is_active,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["bot"] });
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const disconnect = useMutation({
    mutationFn: api.bot.disconnect,
    onSuccess: async () => {
      setConfirmDisconnect(false);
      await qc.invalidateQueries({ queryKey: ["bot"] });
      toast.success(t("toast.deleted"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (bot.isPending) return <Skeleton className="h-72" />;
  if (!bot.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("onboarding.botTitle")}</CardTitle>
          <CardDescription>{t("onboarding.botDesc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <a href="/onboarding">{t("onboarding.connect")}</a>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">@{bot.data.bot_username}</CardTitle>
            <CardDescription>{bot.data.token_hint}</CardDescription>
          </div>
          {webhook.data?.ok && webhook.data.matches_expected ? (
            <Badge variant="success">
              <Check className="mr-1 h-3 w-3" /> {t("settings.webhookOk")}
            </Badge>
          ) : webhook.data ? (
            <Badge variant="warning">
              <AlertTriangle className="mr-1 h-3 w-3" /> {t("settings.webhookMismatch")}
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {webhook.data?.last_error_message && (
            <p className="rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
              {webhook.data.last_error_message}
            </p>
          )}

          <LanguageTabs
            languages={langTabs.ordered}
            active={langTabs.active}
            onChange={langTabs.setActive}
            base={baseLanguage}
            translations={draft.translations ?? {}}
            fields={["welcome_message", "about_text", "after_apply_message", "contacts_text"]}
          />

          <div className="space-y-2">
            <Label htmlFor="welcome">{t("settings.welcomeMessage")}</Label>
            <MarkdownField
              id="welcome"
              rows={3}
              value={field.value("welcome_message")}
              placeholder={field.isBase ? "" : (draft.welcome_message ?? "")}
              onChange={(v) => field.setValue("welcome_message", v)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="about">{t("settings.aboutText")}</Label>
            <MarkdownField
              id="about"
              rows={4}
              value={field.value("about_text")}
              placeholder={field.isBase ? "" : (draft.about_text ?? "")}
              onChange={(v) => field.setValue("about_text", v)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="after">{t("settings.afterApply")}</Label>
            <MarkdownField
              id="after"
              rows={2}
              value={field.value("after_apply_message")}
              placeholder={field.isBase ? "" : (draft.after_apply_message ?? "")}
              onChange={(v) => field.setValue("after_apply_message", v)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="contacts">{t("settings.contactsText")}</Label>
            <MarkdownField
              id="contacts"
              rows={3}
              value={field.value("contacts_text")}
              placeholder={field.isBase ? "" : (draft.contacts_text ?? "")}
              onChange={(v) => field.setValue("contacts_text", v)}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <Label htmlFor="notify">{t("settings.notifyCandidate")}</Label>
            <Switch
              id="notify"
              checked={draft.notify_candidate_on_status ?? true}
              onCheckedChange={(c) => setDraft({ ...draft, notify_candidate_on_status: c })}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <Label htmlFor="botactive">{t("settings.botActive")}</Label>
            <Switch
              id="botactive"
              checked={draft.is_active ?? true}
              onCheckedChange={(c) => setDraft({ ...draft, is_active: c })}
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {t("common.save")}
            </Button>
            <Button variant="outline" onClick={() => webhook.refetch()}>
              <RefreshCw className="h-4 w-4" /> {t("settings.webhookStatus")}
            </Button>
            <Button variant="destructive" onClick={() => setConfirmDisconnect(true)}>
              {t("settings.disconnect")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={confirmDisconnect} onOpenChange={setConfirmDisconnect}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("settings.disconnect")}</DialogTitle>
            <DialogDescription>{t("settings.disconnectDesc")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmDisconnect(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={disconnect.isPending}
              onClick={() => disconnect.mutate()}
            >
              {t("common.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CompanyTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Partial<Company>>({});

  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });

  useEffect(() => {
    if (company.data) setDraft(company.data);
  }, [company.data]);

  const save = useMutation({
    mutationFn: (data: Partial<Company>) => api.company.update(data),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["company"] }),
        qc.invalidateQueries({ queryKey: ["me"] }),
      ]);
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Toggling a language saves immediately: the bot's language picker changes as a result,
  // and leaving that pending behind an unsaved form would be surprising.
  const languages = useMutation({
    mutationFn: (enabled_languages: string[]) => api.company.setLanguages(enabled_languages),
    onSuccess: async (updated) => {
      setDraft((current) => ({ ...current, enabled_languages: updated.enabled_languages }));
      await qc.invalidateQueries({ queryKey: ["company"] });
      toast.success(t("toast.saved"));
    },
    onError: (e: Error, _vars) => {
      // Server rejected it — put the switch back where it was.
      setDraft((current) => ({
        ...current,
        enabled_languages: company.data?.enabled_languages ?? ["ru"],
      }));
      toast.error(e.message);
    },
  });

  if (company.isPending) return <Skeleton className="h-64" />;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("settings.tabCompany")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="cname">{t("settings.companyName")}</Label>
          <Input
            id="cname"
            value={draft.name ?? ""}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
        </div>

        <ImageUpload
          label={t("settings.logoUrl")}
          value={draft.logo_url}
          onChange={(url) => {
            setDraft((current) => ({ ...current, logo_url: url }));
            // Saved straight away: the picker has already uploaded, so leaving the record
            // pointing at the old logo until someone remembers to press Save is worse.
            save.mutate({ logo_url: url });
          }}
        />

        <Separator />

        <div className="space-y-3">
          <div>
            <Label>{t("languages.title")}</Label>
            <p className="mt-1 text-xs text-muted-foreground">{t("languages.desc")}</p>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">{t("languages.enabled")}</Label>
            <div className="flex flex-wrap gap-2">
              {SUPPORTED_LANGUAGES.map((code) => {
                const enabled = (draft.enabled_languages ?? ["ru"]).includes(code);
                const isBase = code === (draft.default_language ?? "ru");
                return (
                  <Button
                    key={code}
                    type="button"
                    size="sm"
                    variant={enabled ? "default" : "outline"}
                    // The base language is the fallback for every untranslated field, so it
                    // cannot be switched off — the API rejects it too.
                    disabled={isBase || languages.isPending}
                    title={isBase ? t("languages.cannotDisableDefault") : undefined}
                    onClick={() => {
                      const current = draft.enabled_languages ?? ["ru"];
                      const next = enabled
                        ? current.filter((l) => l !== code)
                        : [...current, code];
                      setDraft({ ...draft, enabled_languages: next });
                      languages.mutate(next);
                    }}
                  >
                    {LANGUAGE_LABELS[code]}
                    {isBase && (
                      <span className="ml-1 text-[10px] uppercase opacity-70">
                        {t("langTabs.base")}
                      </span>
                    )}
                  </Button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <Label>{t("languages.default")}</Label>
            <p className="text-xs text-muted-foreground">{t("languages.defaultHint")}</p>
            <Select
              value={draft.default_language ?? "ru"}
              onValueChange={(v) => {
                const next = v as Language;
                const enabled = draft.enabled_languages ?? ["ru"];
                setDraft({
                  ...draft,
                  default_language: next,
                  enabled_languages: enabled.includes(next) ? enabled : [...enabled, next],
                });
              }}
            >
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SUPPORTED_LANGUAGES.map((code) => (
                  <SelectItem key={code} value={code}>
                    {LANGUAGE_LABELS[code]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-lg border p-3">
          <div>
            <Label htmlFor="branchmode">{t("settings.branchMode")}</Label>
            <p className="mt-1 text-xs text-muted-foreground">{t("settings.branchModeDesc")}</p>
          </div>
          <Switch
            id="branchmode"
            checked={draft.branches_enabled ?? false}
            onCheckedChange={(checked) => {
              setDraft({ ...draft, branches_enabled: checked });
              // Saved immediately: the API rejects enabling it with no active branch, and
              // the error is only meaningful next to the toggle that caused it.
              save.mutate(
                { branches_enabled: checked },
                {
                  onError: (e) => {
                    setDraft({ ...draft, branches_enabled: !checked });
                    toast.error(e instanceof ApiError ? e.message : String(e));
                  },
                },
              );
            }}
          />
        </div>

        <Button
          onClick={() =>
            save.mutate({
              name: draft.name,
              logo_url: draft.logo_url || null,
              default_language: draft.default_language,
              enabled_languages: draft.enabled_languages,
            })
          }
          disabled={save.isPending}
        >
          {t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}

function TeamTab() {
  const { t } = useTranslation();
  const team = useQuery({ queryKey: ["team"], queryFn: api.company.team });

  if (team.isPending) return <Skeleton className="h-48" />;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("settings.tabTeam")}</CardTitle>
        <CardDescription>{t("settings.inviteSoon")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {(team.data ?? []).map((member) => (
          <div
            key={member.user_id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{member.full_name}</p>
              <p className="truncate text-xs text-muted-foreground">{member.email}</p>
            </div>
            <div className="flex gap-2">
              {member.telegram_linked && <Badge variant="success">Telegram</Badge>}
              <Badge variant="secondary">{member.role}</Badge>
            </div>
          </div>
        ))}
        <Button variant="outline" disabled>
          {t("settings.inviteMember")}
        </Button>
      </CardContent>
    </Card>
  );
}

function NotificationsTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const me = useQuery({ queryKey: ["me"], queryFn: api.auth.me });
  const linked = Boolean(me.data?.user.telegram_user_id);

  const code = useMutation({
    mutationFn: api.notifications.linkCode,
    onError: (e: Error) => toast.error(e.message),
  });

  const unlink = useMutation({
    mutationFn: api.notifications.unlink,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(t("toast.saved"));
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("settings.telegramLink")}</CardTitle>
        <CardDescription>{t("settings.telegramLinkDesc")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {linked ? (
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="success">
              <Check className="mr-1 h-3 w-3" /> {t("settings.linked")}
            </Badge>
            <Button variant="outline" size="sm" onClick={() => unlink.mutate()}>
              {t("settings.unlink")}
            </Button>
          </div>
        ) : (
          <>
            <Button onClick={() => code.mutate()} disabled={code.isPending}>
              {t("settings.getCode")}
            </Button>

            {code.error instanceof ApiError && code.error.status === 503 && (
              <p className="text-sm text-muted-foreground">{t("settings.notConfigured")}</p>
            )}

            {code.data && (
              <div className="space-y-2 rounded-lg border p-4">
                <p className="text-sm">
                  {t("settings.linkInstruction", { bot: `@${code.data.bot_username}` })}
                </p>
                <div className="flex items-center gap-2">
                  <code className="rounded bg-muted px-2 py-1 font-mono text-sm">
                    /link {code.data.code}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      navigator.clipboard.writeText(`/link ${code.data!.code}`);
                      toast.success(t("common.copied"));
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                {code.data.deep_link && (
                  <Button asChild variant="outline" size="sm">
                    <a href={code.data.deep_link} target="_blank" rel="noreferrer">
                      {t("common.open")} @{code.data.bot_username}
                    </a>
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Row content shared by locked (system) and draggable (custom) stages — only the
 *  wrapper and the trailing action buttons differ. */
function StatusRowBody({ row, t }: { row: ApplicationStatusOut; t: (key: string) => string }) {
  return (
    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="truncate font-medium">{row.label}</span>
        {row.is_system && (
          <Badge variant="secondary">
            <Lock className="mr-1 h-3 w-3" /> {t("statuses.system")}
          </Badge>
        )}
        {!row.notify_candidate && <Badge variant="outline">{t("statuses.silent")}</Badge>}
      </div>
      <p className="text-xs text-muted-foreground">
        {t("statuses.applicationsCount")}: {row.application_count}
      </p>
    </div>
  );
}

function StatusesTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [editing, setEditing] = useState<Partial<ApplicationStatusOut> | null>(null);
  const [deleting, setDeleting] = useState<ApplicationStatusOut | null>(null);
  const [moveTarget, setMoveTarget] = useState<string>("");

  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });
  const statuses = useQuery({
    queryKey: ["application-statuses"],
    queryFn: api.applicationStatuses.list,
  });

  const invalidate = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["application-statuses"] }),
      qc.invalidateQueries({ queryKey: ["applications"] }),
      qc.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);

  const save = useMutation({
    mutationFn: (row: Partial<ApplicationStatusOut>) => {
      const payload = {
        label: row.label?.trim() ?? "",
        notify_candidate: row.notify_candidate ?? true,
        translations: row.translations ?? {},
      };
      return row.id
        ? api.applicationStatuses.update(row.id, payload)
        : api.applicationStatuses.create(payload);
    },
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: ({ id, moveTo }: { id: string; moveTo: string }) =>
      api.applicationStatuses.remove(id, moveTo),
    onSuccess: async () => {
      await invalidate();
      setDeleting(null);
      toast.success(t("toast.deleted"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reorder = useMutation({
    mutationFn: api.applicationStatuses.reorder,
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: ["application-statuses"] });
      const previous = qc.getQueryData<ApplicationStatusOut[]>(["application-statuses"]);
      if (previous) {
        // Shape is always [new, ...customs, hired, rejected] — only the middle reorders.
        const system = previous.filter((s) => s.is_system);
        const byId = new Map(previous.map((s) => [s.id, s]));
        const reordered = ids.map((id) => byId.get(id)).filter(Boolean) as ApplicationStatusOut[];
        qc.setQueryData(
          ["application-statuses"],
          [system[0], ...reordered, ...system.slice(1)],
        );
      }
      return { previous };
    },
    onError: (e: Error, _ids, context) => {
      if (context?.previous) qc.setQueryData(["application-statuses"], context.previous);
      toast.error(e.message);
    },
    onSuccess: () => toast.success(t("toast.orderSaved")),
  });

  const list = statuses.data ?? [];
  const systemRows = list.filter((s) => s.is_system);
  const customRows = list.filter((s) => !s.is_system);
  const [newRow, ...terminalRows] = systemRows;

  function openDelete(row: ApplicationStatusOut) {
    setDeleting(row);
    setMoveTarget(list.find((s) => s.id !== row.id)?.id ?? "");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("settings.tabStatuses")}</CardTitle>
        <CardDescription>{t("statuses.tabDesc")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {statuses.isPending ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        ) : (
          <>
            {newRow && (
              <div className="flex items-center gap-3 rounded-lg border bg-card p-3">
                <StatusRowBody row={newRow} t={t} />
              </div>
            )}

            <SortableList items={customRows} onReorder={(ids) => reorder.mutate(ids)}>
              {(row) => (
                <SortableRow key={row.id} id={row.id}>
                  <StatusRowBody row={row} t={t} />
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" size="icon" onClick={() => setEditing(row)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => openDelete(row)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </SortableRow>
              )}
            </SortableList>

            {terminalRows.map((row) => (
              <div key={row.id} className="flex items-center gap-3 rounded-lg border bg-card p-3">
                <StatusRowBody row={row} t={t} />
              </div>
            ))}
          </>
        )}

        <Button
          variant="outline"
          onClick={() => setEditing({ label: "", notify_candidate: true, translations: {} })}
        >
          <Plus className="h-4 w-4" /> {t("statuses.add")}
        </Button>
      </CardContent>

      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DrawerContent>
          <DialogHeader>
            <DialogTitle>{editing?.id ? t("common.edit") : t("statuses.add")}</DialogTitle>
          </DialogHeader>
          {editing && (
            <StatusForm
              editing={editing}
              setEditing={setEditing}
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

      {/* Delete dialog — applications currently in this step must go somewhere. */}
      <Dialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("statuses.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("statuses.deleteDesc")}</DialogDescription>
          </DialogHeader>

          <Select value={moveTarget} onValueChange={setMoveTarget}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {list
                .filter((s) => s.id !== deleting?.id)
                .map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {t("statuses.moveTo")}: {s.label}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleting(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending || !moveTarget}
              onClick={() => deleting && remove.mutate({ id: deleting.id, moveTo: moveTarget })}
            >
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function StatusForm({
  editing,
  setEditing,
  enabledLanguages,
  baseLanguage,
  saving,
  onCancel,
  onSubmit,
  t,
}: {
  editing: Partial<ApplicationStatusOut>;
  setEditing: (s: Partial<ApplicationStatusOut>) => void;
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
      className="flex flex-1 flex-col gap-4"
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
        fields={["label"]}
      />

      <div className="space-y-2">
        <Label htmlFor="slabel">{t("statuses.label")}</Label>
        <Input
          id="slabel"
          value={field.value("label")}
          placeholder={field.isBase ? "" : String(editing.label ?? "")}
          onChange={(e) => field.setValue("label", e.target.value)}
        />
      </div>

      {/* Language-independent. */}
      <div className="flex items-center justify-between rounded-lg border p-3">
        <div>
          <Label htmlFor="notify">{t("statuses.notifyCandidate")}</Label>
          <p className="text-xs text-muted-foreground">{t("statuses.notifyCandidateHint")}</p>
        </div>
        <Switch
          id="notify"
          checked={editing.notify_candidate ?? true}
          onCheckedChange={(checked) => setEditing({ ...editing, notify_candidate: checked })}
        />
      </div>

      <DialogFooter className="mt-auto pt-4">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button type="submit" disabled={!editing.label?.trim() || saving}>
          {t("common.save")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();

  return (
    <>
      <PageHeader title={t("settings.title")} />
      <Tabs defaultValue="bot">
        <TabsList className="flex-wrap">
          <TabsTrigger value="bot">{t("settings.tabBot")}</TabsTrigger>
          <TabsTrigger value="company">{t("settings.tabCompany")}</TabsTrigger>
          <TabsTrigger value="statuses">{t("settings.tabStatuses")}</TabsTrigger>
          <TabsTrigger value="team">{t("settings.tabTeam")}</TabsTrigger>
          <TabsTrigger value="notifications">{t("settings.tabNotifications")}</TabsTrigger>
        </TabsList>

        <TabsContent value="bot">
          <BotTab />
        </TabsContent>
        <TabsContent value="company">
          <CompanyTab />
        </TabsContent>
        <TabsContent value="statuses">
          <StatusesTab />
        </TabsContent>
        <TabsContent value="team">
          <TeamTab />
        </TabsContent>
        <TabsContent value="notifications">
          <NotificationsTab />
        </TabsContent>
      </Tabs>
    </>
  );
}
