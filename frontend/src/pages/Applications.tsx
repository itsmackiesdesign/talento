import {
  DndContext,
  PointerSensor,
  pointerWithin,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ExternalLink, Inbox, KanbanSquare, Table2, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout";
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
import { EmptyState, Label, Separator, Skeleton } from "@/components/ui/misc";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, downloadExport } from "@/lib/api";
import type { ApplicationListItem, ApplicationStatusOut } from "@/lib/types";
import { cn, formatDate, formatDateTime } from "@/lib/utils";

const ALL = "__all__";

function questionTextToPlainText(value: string): string {
  const withoutMarkdown = value
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/\*\*|__|~~|```|`|_/g, "");
  const parsed = new DOMParser().parseFromString(withoutMarkdown, "text/html");
  return (parsed.body.textContent ?? "").replace(/\s+/g, " ").trim();
}

function QuestionLabel({ text }: { text: string }) {
  const plainText = questionTextToPlainText(text);
  return (
    <dt className="truncate text-xs text-muted-foreground" title={plainText}>
      {plainText}
    </dt>
  );
}

function CandidateAvatar({
  name,
  photoUrl,
  className = "h-10 w-10",
}: {
  name: string;
  photoUrl: string | null;
  className?: string;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  useEffect(() => setImageFailed(false), [photoUrl]);
  const initials = (name === "—" ? "" : name)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "?";

  if (photoUrl && !imageFailed) {
    return (
      <img
        src={photoUrl}
        alt=""
        className={cn("shrink-0 rounded-full border object-cover", className)}
        onError={() => setImageFailed(true)}
      />
    );
  }

  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary",
        className,
      )}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}

function CandidateCard({
  application,
  onOpen,
}: {
  application: ApplicationListItem;
  onOpen: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: application.id,
  });
  const pressOrigin = useRef<{ x: number; y: number } | null>(null);

  // A plain `onClick` never fires here: dnd-kit's pointer handlers call preventDefault to
  // stop text selection mid-drag, which suppresses the synthetic click. So we measure the
  // pointer travel ourselves and treat a near-stationary press as a tap.
  const handlePointerDown = (event: React.PointerEvent) => {
    pressOrigin.current = { x: event.clientX, y: event.clientY };
    listeners?.onPointerDown?.(event);
  };

  const handlePointerUp = (event: React.PointerEvent) => {
    const origin = pressOrigin.current;
    pressOrigin.current = null;
    if (origin && Math.hypot(event.clientX - origin.x, event.clientY - origin.y) < 8) {
      onOpen();
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      className={cn(
        "cursor-grab rounded-lg border bg-card p-3 text-sm active:cursor-grabbing",
        isDragging && "z-50 opacity-90 shadow-xl",
      )}
      {...attributes}
      {...listeners}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onOpen();
      }}
    >
      <div className="flex min-w-0 items-center gap-3">
        <CandidateAvatar
          name={application.candidate_name}
          photoUrl={application.candidate_photo_url}
        />
        <div className="min-w-0">
          <p className="truncate font-medium">{application.candidate_name}</p>
          <p className="truncate text-xs text-muted-foreground">{application.vacancy_title}</p>
        </div>
      </div>
      {application.branch_name && (
        <Badge variant="outline" className="mt-1.5">
          {application.branch_name}
        </Badge>
      )}
      <p className="mt-1.5 text-xs text-muted-foreground">{formatDate(application.created_at)}</p>
    </div>
  );
}

function KanbanColumn({
  status,
  items,
  onOpen,
}: {
  status: ApplicationStatusOut;
  items: ApplicationListItem[];
  onOpen: (id: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status.id });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-64 shrink-0 flex-col gap-2 rounded-xl border border-t-2 bg-muted/40 p-2 transition-colors",
        isOver && "bg-accent",
      )}
      style={{ borderTopColor: status.color }}
    >
      <div className="flex items-center justify-between px-1 py-1">
        <span className="text-sm font-medium">{status.label}</span>
        <span className="text-xs text-muted-foreground tabular-nums">{items.length}</span>
      </div>
      <div className="flex flex-col gap-2">
        {items.map((application) => (
          <CandidateCard
            key={application.id}
            application={application}
            onOpen={() => onOpen(application.id)}
          />
        ))}
      </div>
    </div>
  );
}

export default function ApplicationsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { id: routeId } = useParams<{ id: string }>();

  const [view, setView] = useState<"kanban" | "table">("kanban");
  const [vacancyFilter, setVacancyFilter] = useState(ALL);
  const [branchFilter, setBranchFilter] = useState(ALL);
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [comment, setComment] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  // question_id -> chosen option, e.g. "is a student?" -> "Да". Only meaningful once a
  // single vacancy is picked, since that's what determines which questions even exist.
  const [answerFilters, setAnswerFilters] = useState<Record<string, string>>({});

  function selectVacancy(v: string) {
    setVacancyFilter(v);
    setAnswerFilters({});
  }

  const filters = {
    vacancy_id: vacancyFilter === ALL ? undefined : vacancyFilter,
    branch_id: branchFilter === ALL ? undefined : branchFilter,
    search: search.trim() || undefined,
    date_from: dateFrom || undefined,
    answers: Object.keys(answerFilters).length ? JSON.stringify(answerFilters) : undefined,
  };

  const options = useQuery({ queryKey: ["app-filters"], queryFn: api.applications.filters });
  const statuses = useQuery({
    queryKey: ["application-statuses"],
    queryFn: api.applicationStatuses.list,
  });
  // Company-wide questions are asked on every vacancy alongside its own — see
  // collect_questions in app/bot/forms.py — so both sets are offered as filters. Only
  // single/multi-choice questions have a fixed option set a dropdown can filter by.
  const questionFilters = useQuery({
    queryKey: ["question-filters", vacancyFilter],
    queryFn: async () => {
      const [common, specific] = await Promise.all([
        api.questions.list("null"),
        api.questions.list(vacancyFilter),
      ]);
      return [...common, ...specific].filter(
        (q) =>
          q.is_filterable && (q.type === "single_choice" || q.type === "multi_choice"),
      );
    },
    enabled: vacancyFilter !== ALL,
  });

  const applications = useQuery({
    queryKey: ["applications", filters],
    queryFn: () => api.applications.list({ ...filters, page_size: 200 }),
  });

  const detail = useQuery({
    queryKey: ["application", routeId],
    queryFn: () => api.applications.get(routeId!),
    enabled: Boolean(routeId),
  });

  const invalidate = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["applications"] }),
      qc.invalidateQueries({ queryKey: ["application", routeId] }),
      qc.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);

  const setStatus = useMutation({
    mutationFn: ({ id, statusId }: { id: string; statusId: string }) =>
      api.applications.setStatus(id, statusId),
    onMutate: async ({ id, statusId }) => {
      await qc.cancelQueries({ queryKey: ["applications", filters] });
      const previous = qc.getQueryData(["applications", filters]);
      qc.setQueryData(["applications", filters], (old: typeof applications.data) =>
        old
          ? {
              ...old,
              items: old.items.map((a) => (a.id === id ? { ...a, status_id: statusId } : a)),
            }
          : old,
      );
      return { previous };
    },
    onError: (e: Error, _vars, context) => {
      if (context?.previous) qc.setQueryData(["applications", filters], context.previous);
      toast.error(e.message);
    },
    onSuccess: async () => {
      await invalidate();
      toast.success(t("toast.statusChanged"));
    },
  });

  const addComment = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => api.applications.comment(id, text),
    onSuccess: async () => {
      setComment("");
      await qc.invalidateQueries({ queryKey: ["application", routeId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: api.applications.remove,
    onSuccess: async () => {
      setConfirmDelete(false);
      navigate("/applications");
      await invalidate();
      toast.success(t("toast.deleted"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const statusId = String(over.id);
    const current = applications.data?.items.find((a) => a.id === active.id);
    if (!current || current.status_id === statusId) return;
    setStatus.mutate({ id: String(active.id), statusId });
  }

  const items = applications.data?.items ?? [];
  const statusList = statuses.data ?? [];
  const statusById = new Map(statusList.map((s) => [s.id, s]));

  return (
    <>
      <PageHeader
        title={t("applications.title")}
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() =>
                downloadExport(filters as Record<string, string | undefined>)
                  .then(() => toast.success(t("toast.exported")))
                  .catch((e: Error) => toast.error(e.message))
              }
            >
              <Download className="h-4 w-4" /> {t("applications.export")}
            </Button>
            <Button
              variant={view === "kanban" ? "default" : "outline"}
              size="icon"
              aria-label={t("applications.kanban")}
              onClick={() => setView("kanban")}
            >
              <KanbanSquare className="h-4 w-4" />
            </Button>
            <Button
              variant={view === "table" ? "default" : "outline"}
              size="icon"
              aria-label={t("applications.table")}
              onClick={() => setView("table")}
            >
              <Table2 className="h-4 w-4" />
            </Button>
          </div>
        }
      />

      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          placeholder={t("applications.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={vacancyFilter} onValueChange={selectVacancy}>
          <SelectTrigger>
            <SelectValue placeholder={t("applications.vacancy")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("applications.vacancy")}: {t("common.all")}</SelectItem>
            {(options.data?.vacancies ?? []).map((v) => (
              <SelectItem key={v.id} value={v.id}>
                {v.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={branchFilter} onValueChange={setBranchFilter}>
          <SelectTrigger>
            <SelectValue placeholder={t("applications.branch")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("applications.branch")}: {t("common.all")}</SelectItem>
            <SelectItem value="null">{t("common.none")}</SelectItem>
            {(options.data?.branches ?? []).map((b) => (
              <SelectItem key={b.id} value={b.id}>
                {b.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
      </div>

      {/* Only shown once a single vacancy is picked — that's what fixes which questions
          (and thus which answer options) are even in play. */}
      {vacancyFilter !== ALL && (questionFilters.data?.length ?? 0) > 0 && (
        <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {questionFilters.data!.map((q) => (
            <Select
              key={q.id}
              value={answerFilters[q.id] ?? ALL}
              onValueChange={(v) =>
                setAnswerFilters((prev) => {
                  const next = { ...prev };
                  if (v === ALL) delete next[q.id];
                  else next[q.id] = v;
                  return next;
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder={q.text} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>
                  {q.text}: {t("common.all")}
                </SelectItem>
                {(q.options ?? []).map((opt) => (
                  <SelectItem key={opt} value={opt}>
                    {opt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}
        </div>
      )}

      {applications.isPending || statuses.isPending ? (
        <Skeleton className="h-96" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={t("applications.empty")}
          description={t("applications.emptyDesc")}
        />
      ) : view === "kanban" ? (
        <DndContext sensors={sensors} collisionDetection={pointerWithin} onDragEnd={handleDragEnd}>
          <div className="table-scroll pb-4">
            <div className="flex gap-3">
              {statusList.map((status) => (
                <KanbanColumn
                  key={status.id}
                  status={status}
                  items={items.filter((a) => a.status_id === status.id)}
                  onOpen={(id) => navigate(`/applications/${id}`)}
                />
              ))}
            </div>
          </div>
        </DndContext>
      ) : (
        <div className="table-scroll rounded-xl border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left">
              <tr>
                <th className="p-3 font-medium">{t("applications.candidate")}</th>
                <th className="p-3 font-medium">{t("applications.vacancy")}</th>
                <th className="p-3 font-medium">{t("applications.branch")}</th>
                <th className="p-3 font-medium">{t("applications.phone")}</th>
                <th className="p-3 font-medium">{t("applications.date")}</th>
                <th className="p-3 font-medium">{t("applications.status")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr
                  key={a.id}
                  className="cursor-pointer border-b last:border-0 hover:bg-accent/50"
                  onClick={() => navigate(`/applications/${a.id}`)}
                >
                  <td className="p-3 font-medium">
                    <div className="flex items-center gap-2">
                      <CandidateAvatar
                        name={a.candidate_name}
                        photoUrl={a.candidate_photo_url}
                        className="h-8 w-8"
                      />
                      <span className="truncate">{a.candidate_name}</span>
                    </div>
                  </td>
                  <td className="p-3">{a.vacancy_title}</td>
                  <td className="p-3 text-muted-foreground">{a.branch_name ?? "—"}</td>
                  <td className="p-3 text-muted-foreground">{a.candidate_phone ?? "—"}</td>
                  <td className="p-3 whitespace-nowrap text-muted-foreground">
                    {formatDate(a.created_at)}
                  </td>
                  <td className="p-3">
                    {statusById.get(a.status_id) ? (
                      <Badge variant="outline" className="gap-1.5">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: statusById.get(a.status_id)?.color }}
                        />
                        {statusById.get(a.status_id)?.label}
                      </Badge>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail drawer, opened by route so a card is linkable and shareable. */}
      <Dialog
        open={Boolean(routeId)}
        onOpenChange={(open) => !open && navigate("/applications")}
      >
        <DrawerContent>
          {detail.isPending ? (
            <div className="space-y-3">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-40" />
            </div>
          ) : detail.data ? (
            <>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  <CandidateAvatar
                    name={detail.data.candidate_name}
                    photoUrl={detail.data.candidate_photo_url}
                    className="h-12 w-12"
                  />
                  <div className="min-w-0">
                    <DialogTitle>{detail.data.candidate_name}</DialogTitle>
                    <DialogDescription>
                      {detail.data.vacancy_title}
                      {detail.data.branch_name && ` · ${detail.data.branch_name}`}
                    </DialogDescription>
                  </div>
                </div>
              </DialogHeader>

              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={detail.data.status_id}
                  onValueChange={(v) =>
                    setStatus.mutate({ id: detail.data!.id, statusId: v })
                  }
                >
                  <SelectTrigger className="w-44">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {statusList.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        <span className="flex items-center gap-2">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: s.color }}
                          />
                          {s.label}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {detail.data.candidate_username && (
                  <Button asChild variant="outline" size="sm">
                    <a
                      href={`https://t.me/${detail.data.candidate_username}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink className="h-4 w-4" /> {t("applications.writeTelegram")}
                    </a>
                  </Button>
                )}

                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-auto"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>

              {detail.data.candidate_phone && (
                <p className="text-sm">
                  <span className="text-muted-foreground">{t("applications.phone")}: </span>
                  <a href={`tel:${detail.data.candidate_phone}`} className="hover:underline">
                    {detail.data.candidate_phone}
                  </a>
                </p>
              )}

              <Separator />

              <section className="space-y-3">
                <h3 className="text-sm font-semibold">{t("applications.answers")}</h3>
                {detail.data.answers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">—</p>
                ) : (
                  <dl className="space-y-3">
                    {detail.data.answers.map((answer) => (
                      <div key={answer.question_id}>
                        <QuestionLabel text={answer.question_text} />
                        <dd className="text-sm">
                          {answer.skipped || answer.answer === null ? (
                            <span className="text-muted-foreground">
                              {t("applications.skipped")}
                            </span>
                          ) : Array.isArray(answer.answer) ? (
                            answer.answer.join(", ")
                          ) : (
                            answer.answer
                          )}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </section>

              <Separator />

              <section className="space-y-3">
                <h3 className="text-sm font-semibold">{t("applications.comments")}</h3>
                {detail.data.comments.map((c) => (
                  <div key={c.id} className="rounded-lg bg-muted/60 p-3 text-sm">
                    <p>{c.text}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {c.author_name} · {formatDateTime(c.created_at)}
                    </p>
                  </div>
                ))}
                <div className="space-y-2">
                  <Label htmlFor="comment">{t("applications.addComment")}</Label>
                  <Textarea
                    id="comment"
                    rows={2}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                  />
                  <Button
                    size="sm"
                    disabled={!comment.trim() || addComment.isPending}
                    onClick={() => addComment.mutate({ id: detail.data!.id, text: comment })}
                  >
                    {t("common.save")}
                  </Button>
                </div>
              </section>

              <Separator />

              <section className="space-y-2 pb-4">
                <h3 className="text-sm font-semibold">{t("applications.history")}</h3>
                <ol className="space-y-1.5 text-xs text-muted-foreground">
                  {detail.data.history.map((h, index) => (
                    <li key={index}>
                      {formatDateTime(h.created_at)} ·{" "}
                      {h.from_status_label ? `${h.from_status_label} → ` : ""}
                      {h.to_status_label}
                      {h.changed_by_name && ` · ${h.changed_by_name}`}
                    </li>
                  ))}
                </ol>
              </section>
            </>
          ) : null}
        </DrawerContent>
      </Dialog>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("applications.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("applications.deleteDesc")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => routeId && remove.mutate(routeId)}
            >
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
