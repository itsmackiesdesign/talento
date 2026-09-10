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
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import InputAdornment from "@mui/material/InputAdornment";
import MenuItem from "@mui/material/MenuItem";
import Pagination from "@mui/material/Pagination";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import MuiButton from "@mui/material/Button";
import { alpha, useTheme } from "@mui/material/styles";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Download,
  ExternalLink,
  FileText,
  FilterX,
  Inbox,
  KanbanSquare,
  Search,
  Table2,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
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
import { Textarea } from "@/components/ui/input";
import { EmptyState, Label, Separator, Skeleton } from "@/components/ui/misc";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, downloadExport } from "@/lib/api";
import type {
  Answer,
  ApplicationListItem,
  ApplicationPage,
  ApplicationStatusOut,
  InterviewKind,
} from "@/lib/types";
import { cn, formatDate, formatDateTime } from "@/lib/utils";

const ALL = "__all__";
const PAGE_SIZE = 25;

function parseAnswerFilters(value: string | null): Record<string, string> {
  if (!value) return {};
  try {
    const parsed: unknown = JSON.parse(value);
    if (
      parsed &&
      typeof parsed === "object" &&
      !Array.isArray(parsed) &&
      Object.entries(parsed).every(
        ([key, answer]) => key.length > 0 && typeof answer === "string",
      )
    ) {
      return parsed as Record<string, string>;
    }
  } catch {
    // Invalid shared URLs degrade to an unfiltered list instead of breaking the page.
  }
  return {};
}

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

function ApplicationStatusChip({ status }: { status?: ApplicationStatusOut }) {
  if (!status) return <Typography color="text.secondary">—</Typography>;
  return (
    <Chip
      size="small"
      label={status.label}
      sx={{
        color: status.color,
        bgcolor: alpha(status.color, 0.1),
        border: `1px solid ${alpha(status.color, 0.22)}`,
        "&::before": {
          content: '""',
          width: 7,
          height: 7,
          borderRadius: "50%",
          bgcolor: status.color,
          ml: 1,
        },
      }}
    />
  );
}

function AnswerValue({ answer }: { answer: Answer }) {
  const { t } = useTranslation();
  if (answer.skipped || answer.answer === null) {
    return <span className="text-muted-foreground">{t("applications.skipped")}</span>;
  }

  const value = Array.isArray(answer.answer) ? answer.answer.join(", ") : answer.answer;
  const fileUrl = answer.file_url || (answer.type === "file" && /^https?:\/\//.test(value) ? value : null);
  if (answer.type === "file" && fileUrl) {
    return (
      <MuiButton
        component="a"
        href={fileUrl}
        target="_blank"
        rel="noreferrer"
        variant="outlined"
        size="small"
        startIcon={<FileText size={16} />}
      >
        {t("applications.openFile")}
      </MuiButton>
    );
  }

  return <>{value}</>;
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
        "flex w-full shrink-0 flex-col gap-2 rounded-xl border border-t-2 bg-muted/40 p-2 transition-colors sm:w-64",
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
  const theme = useTheme();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { id: routeId } = useParams<{ id: string }>();

  const querySearch = searchParams.get("q") ?? "";
  const [search, setSearch] = useState(querySearch);
  const view = searchParams.get("view") === "kanban" ? "kanban" : "table";
  const vacancyFilter = searchParams.get("vacancy") ?? ALL;
  const branchFilter = searchParams.get("branch") ?? ALL;
  const statusFilter = searchParams.get("status") ?? ALL;
  const dateFrom = searchParams.get("from") ?? "";
  const dateTo = searchParams.get("to") ?? "";
  const rawPage = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const page = Number.isFinite(rawPage) && rawPage > 0 ? rawPage : 1;
  const answerFiltersParam = searchParams.get("answers");
  const answerFilters = useMemo(
    () => parseAnswerFilters(answerFiltersParam),
    [answerFiltersParam],
  );
  const [comment, setComment] = useState("");
  const [transitionReason, setTransitionReason] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDueAt, setTaskDueAt] = useState("");
  const [interviewKind, setInterviewKind] = useState<InterviewKind>("video");
  const [interviewAt, setInterviewAt] = useState("");
  const [interviewDuration, setInterviewDuration] = useState("45");
  const [interviewLocation, setInterviewLocation] = useState("");
  const [interviewNotes, setInterviewNotes] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkStatus, setBulkStatus] = useState(ALL);

  const updateParams = useCallback(
    (updates: Record<string, string | undefined>, resetPage = true) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [key, value] of Object.entries(updates)) {
            if (!value || value === ALL) next.delete(key);
            else next.set(key, value);
          }
          if (resetPage) next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  useEffect(() => setSearch(querySearch), [querySearch]);

  useEffect(() => setTransitionReason(""), [routeId]);

  useEffect(() => {
    const nextSearch = search.trim();
    if (nextSearch === querySearch) return;

    // Debounce the URL write itself, not a second piece of state. That way clearing
    // every filter cannot be undone by a stale debounced value from the previous query.
    const timeout = window.setTimeout(
      () => updateParams({ q: nextSearch || undefined }),
      350,
    );
    return () => window.clearTimeout(timeout);
  }, [querySearch, search, updateParams]);

  const selectVacancy = (value: string) => {
    updateParams({ vacancy: value, answers: undefined });
  };

  const setAnswerFilter = (questionId: string, value: string) => {
    const next = { ...answerFilters };
    if (value === ALL) delete next[questionId];
    else next[questionId] = value;
    updateParams({ answers: Object.keys(next).length ? JSON.stringify(next) : undefined });
  };

  const clearFilters = () => {
    const next = new URLSearchParams();
    if (view === "kanban") next.set("view", "kanban");
    setSearchParams(next, { replace: true });
    setSearch("");
  };

  const filters = useMemo(
    () => ({
      status: statusFilter === ALL ? undefined : statusFilter,
      vacancy_id: vacancyFilter === ALL ? undefined : vacancyFilter,
      branch_id: branchFilter === ALL ? undefined : branchFilter,
      search: querySearch || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      answers: Object.keys(answerFilters).length ? JSON.stringify(answerFilters) : undefined,
    }),
    [answerFilters, branchFilter, dateFrom, dateTo, querySearch, statusFilter, vacancyFilter],
  );
  const pageSize = view === "kanban" ? 200 : PAGE_SIZE;
  const applicationsQueryKey = ["applications", filters, page, pageSize] as const;
  const activeFilterCount = [
    querySearch,
    vacancyFilter !== ALL ? vacancyFilter : "",
    branchFilter !== ALL ? branchFilter : "",
    statusFilter !== ALL ? statusFilter : "",
    dateFrom,
    dateTo,
    ...Object.values(answerFilters),
  ].filter(Boolean).length;

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
    queryKey: applicationsQueryKey,
    queryFn: () => api.applications.list({ ...filters, page, page_size: pageSize }),
    placeholderData: (previous) => previous,
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
    mutationFn: ({ id, statusId, reason }: { id: string; statusId: string; reason?: string }) =>
      api.applications.setStatus(id, statusId, reason),
    onMutate: async ({ id, statusId }) => {
      await qc.cancelQueries({ queryKey: applicationsQueryKey });
      const previous = qc.getQueryData<ApplicationPage>(applicationsQueryKey);
      qc.setQueryData<ApplicationPage>(applicationsQueryKey, (old) =>
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
      if (context?.previous) qc.setQueryData(applicationsQueryKey, context.previous);
      toast.error(e.message);
    },
    onSuccess: async () => {
      setTransitionReason("");
      await invalidate();
      toast.success(t("toast.statusChanged"));
    },
  });

  const bulkSetStatus = useMutation({
    mutationFn: ({ ids, statusId }: { ids: string[]; statusId: string }) =>
      api.applications.bulkSetStatus(ids, statusId),
    onSuccess: async (result) => {
      setSelectedIds([]);
      setBulkStatus(ALL);
      await invalidate();
      toast.success(t("applications.bulkMoved", { count: result.updated }));
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const addComment = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => api.applications.comment(id, text),
    onSuccess: async () => {
      setComment("");
      await qc.invalidateQueries({ queryKey: ["application", routeId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const addTask = useMutation({
    mutationFn: ({ id, title, dueAt }: { id: string; title: string; dueAt: string }) =>
      api.applications.createTask(id, {
        title,
        due_at: dueAt ? new Date(dueAt).toISOString() : null,
      }),
    onSuccess: async () => {
      setTaskTitle("");
      setTaskDueAt("");
      await qc.invalidateQueries({ queryKey: ["application", routeId] });
      toast.success(t("applications.addTask"));
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const updateTask = useMutation({
    mutationFn: ({ applicationId, taskId, completed }: { applicationId: string; taskId: string; completed: boolean }) =>
      api.applications.updateTask(applicationId, taskId, completed),
    onSuccess: async (_result, variables) => {
      await qc.invalidateQueries({ queryKey: ["application", variables.applicationId] });
      if (variables.completed) toast.success(t("applications.taskCompleted"));
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const addInterview = useMutation({
    mutationFn: ({ id }: { id: string }) => api.applications.createInterview(id, {
      kind: interviewKind,
      scheduled_at: new Date(interviewAt).toISOString(),
      duration_minutes: Number(interviewDuration),
      location: interviewLocation.trim() || null,
      notes: interviewNotes.trim() || null,
    }),
    onSuccess: async () => {
      setInterviewAt("");
      setInterviewLocation("");
      setInterviewNotes("");
      await qc.invalidateQueries({ queryKey: ["application", routeId] });
      toast.success(t("applications.scheduleInterview"));
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const updateInterview = useMutation({
    mutationFn: ({ applicationId, interviewId, status }: {
      applicationId: string;
      interviewId: string;
      status: "completed" | "cancelled";
    }) => api.applications.updateInterview(applicationId, interviewId, { status }),
    onSuccess: async (_result, variables) => {
      await qc.invalidateQueries({ queryKey: ["application", variables.applicationId] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: api.applications.remove,
    onSuccess: async () => {
      setConfirmDelete(false);
      navigate(`/applications${location.search}`);
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
  const total = applications.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const statusList = statuses.data ?? [];
  const statusById = new Map(statusList.map((s) => [s.id, s]));
  const selectedSet = new Set(selectedIds);
  const allPageSelected = items.length > 0 && items.every((item) => selectedSet.has(item.id));
  const somePageSelected = items.some((item) => selectedSet.has(item.id));

  const openApplication = (id: string) => navigate(`/applications/${id}${location.search}`);
  const closeApplication = () => navigate(`/applications${location.search}`);
  const changePage = (_event: React.ChangeEvent<unknown>, nextPage: number) => {
    updateParams({ page: nextPage > 1 ? String(nextPage) : undefined }, false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const toggleSelection = (id: string) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((selected) => selected !== id) : [...current, id],
    );
  };
  const togglePageSelection = () => {
    setSelectedIds((current) => {
      if (allPageSelected) return current.filter((id) => !items.some((item) => item.id === id));
      return Array.from(new Set([...current, ...items.map((item) => item.id)]));
    });
  };

  useEffect(() => {
    setSelectedIds([]);
    setBulkStatus(ALL);
  }, [filters, page, view]);

  useEffect(() => {
    if (view === "table" && applications.data && page > pageCount) {
      updateParams({ page: pageCount > 1 ? String(pageCount) : undefined }, false);
    }
  }, [applications.data, page, pageCount, updateParams, view]);

  return (
    <>
      <PageHeader
        title={t("applications.title")}
        description={t("applications.subtitle")}
        action={
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <MuiButton
              variant="outlined"
              startIcon={<Download size={18} />}
              onClick={() =>
                downloadExport(filters as Record<string, string | undefined>)
                  .then(() => toast.success(t("toast.exported")))
                  .catch((e: Error) => toast.error(e.message))
              }
            >
              {t("applications.export")}
            </MuiButton>
            <ToggleButtonGroup
              exclusive
              value={view}
              size="small"
              aria-label={t("applications.view")}
              onChange={(_event, nextView: "table" | "kanban" | null) => {
                if (nextView) updateParams({ view: nextView === "kanban" ? nextView : undefined });
              }}
              sx={{ "& .MuiToggleButton-root": { minWidth: 44, minHeight: 44, px: 1.25 } }}
            >
              <ToggleButton value="table" aria-label={t("applications.table")}>
                <Table2 size={18} />
              </ToggleButton>
              <ToggleButton value="kanban" aria-label={t("applications.kanban")}>
                <KanbanSquare size={18} />
              </ToggleButton>
            </ToggleButtonGroup>
          </Stack>
        }
      />

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(2, minmax(0, 1fr))",
                lg: "minmax(240px, 1.45fr) repeat(3, minmax(160px, 1fr))",
              },
              gap: 2,
            }}
          >
            <TextField
              label={t("common.search")}
              placeholder={t("applications.searchPlaceholder")}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search size={18} />
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              select
              label={t("applications.vacancy")}
              value={vacancyFilter}
              onChange={(event) => selectVacancy(event.target.value)}
            >
              <MenuItem value={ALL}>{t("common.all")}</MenuItem>
              {(options.data?.vacancies ?? []).map((vacancy) => (
                <MenuItem key={vacancy.id} value={vacancy.id}>{vacancy.title}</MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label={t("applications.branch")}
              value={branchFilter}
              onChange={(event) => updateParams({ branch: event.target.value })}
            >
              <MenuItem value={ALL}>{t("common.all")}</MenuItem>
              <MenuItem value="null">{t("common.none")}</MenuItem>
              {(options.data?.branches ?? []).map((branch) => (
                <MenuItem key={branch.id} value={branch.id}>{branch.name}</MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label={t("applications.status")}
              value={statusFilter}
              onChange={(event) => updateParams({ status: event.target.value })}
            >
              <MenuItem value={ALL}>{t("common.all")}</MenuItem>
              {statusList.map((status) => (
                <MenuItem key={status.id} value={status.id}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: status.color }} />
                    <span>{status.label}</span>
                  </Stack>
                </MenuItem>
              ))}
            </TextField>
            <TextField
              type="date"
              label={t("applications.dateFrom")}
              value={dateFrom}
              onChange={(event) => updateParams({ from: event.target.value })}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              type="date"
              label={t("applications.dateTo")}
              value={dateTo}
              onChange={(event) => updateParams({ to: event.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Box>

          {vacancyFilter !== ALL && (questionFilters.data?.length ?? 0) > 0 && (
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" },
                gap: 2,
                mt: 2,
                pt: 2,
                borderTop: `1px dashed ${theme.palette.divider}`,
              }}
            >
              {questionFilters.data!.map((question) => (
                <TextField
                  select
                  key={question.id}
                  label={questionTextToPlainText(question.text)}
                  value={answerFilters[question.id] ?? ALL}
                  onChange={(event) => setAnswerFilter(question.id, event.target.value)}
                >
                  <MenuItem value={ALL}>{t("common.all")}</MenuItem>
                  {(question.options ?? []).map((option) => (
                    <MenuItem key={option} value={option}>{option}</MenuItem>
                  ))}
                </TextField>
              ))}
            </Box>
          )}

          <Stack
            direction={{ xs: "column", sm: "row" }}
            alignItems={{ xs: "stretch", sm: "center" }}
            justifyContent="space-between"
            spacing={1.5}
            sx={{ mt: 2.5 }}
          >
            <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
              <Typography variant="body2" color="text.secondary">
                {t("applications.resultCount", { count: total })}
              </Typography>
              {activeFilterCount > 0 && (
                <Chip
                  size="small"
                  color="primary"
                  variant="outlined"
                  label={t("applications.activeFilters", { count: activeFilterCount })}
                />
              )}
              {applications.isFetching && !applications.isPending && <CircularProgress size={18} />}
            </Stack>
            {activeFilterCount > 0 && (
              <MuiButton variant="text" startIcon={<FilterX size={17} />} onClick={clearFilters}>
                {t("applications.clearFilters")}
              </MuiButton>
            )}
          </Stack>
        </CardContent>
      </Card>

      {view === "table" && selectedIds.length > 0 && (
        <Paper
          role="region"
          aria-label={t("applications.bulkActions")}
          sx={{ mb: 2, p: 1.5, border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`, bgcolor: alpha(theme.palette.primary.main, 0.06) }}
        >
          <Stack direction={{ xs: "column", sm: "row" }} alignItems={{ xs: "stretch", sm: "center" }} spacing={1.5}>
            <Typography variant="subtitle2" sx={{ minWidth: 150 }}>
              {t("applications.selected", { count: selectedIds.length })}
            </Typography>
            <TextField
              select
              size="small"
              label={t("applications.moveToStatus")}
              value={bulkStatus}
              onChange={(event) => setBulkStatus(event.target.value)}
              sx={{ minWidth: { sm: 240 } }}
            >
              <MenuItem value={ALL}>{t("applications.chooseStatus")}</MenuItem>
              {statusList.map((status) => (
                <MenuItem key={status.id} value={status.id}>{status.label}</MenuItem>
              ))}
            </TextField>
            <MuiButton
              variant="contained"
              disabled={bulkStatus === ALL || bulkSetStatus.isPending}
              onClick={() => bulkSetStatus.mutate({ ids: selectedIds, statusId: bulkStatus })}
            >
              {bulkSetStatus.isPending ? t("common.loading") : t("applications.apply")}
            </MuiButton>
            <MuiButton variant="text" color="inherit" onClick={() => setSelectedIds([])}>
              {t("common.cancel")}
            </MuiButton>
          </Stack>
        </Paper>
      )}

      {applications.isPending || statuses.isPending ? (
        <Skeleton className="h-96" />
      ) : applications.isError ? (
        <EmptyState
          icon={Inbox}
          title={t("common.error")}
          description={(applications.error as Error).message}
          action={<Button onClick={() => applications.refetch()}>{t("common.retry")}</Button>}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={activeFilterCount ? t("applications.noResults") : t("applications.empty")}
          description={activeFilterCount ? t("applications.noResultsDesc") : t("applications.emptyDesc")}
          action={activeFilterCount ? <Button onClick={clearFilters}>{t("applications.clearFilters")}</Button> : undefined}
        />
      ) : view === "kanban" ? (
        <DndContext sensors={sensors} collisionDetection={pointerWithin} onDragEnd={handleDragEnd}>
          <Box sx={{ display: { xs: "grid", sm: "flex" }, gap: 2, overflowX: { sm: "auto" }, pb: 2 }}>
              {statusList.map((status) => (
                <KanbanColumn
                  key={status.id}
                  status={status}
                  items={items.filter((a) => a.status_id === status.id)}
                  onOpen={openApplication}
                />
              ))}
          </Box>
        </DndContext>
      ) : (
        <>
          <TableContainer component={Card} sx={{ display: { xs: "none", md: "block" } }}>
            <Table aria-label={t("applications.table")}>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={allPageSelected}
                      indeterminate={!allPageSelected && somePageSelected}
                      onChange={togglePageSelection}
                      inputProps={{ "aria-label": t("applications.selectPage") }}
                    />
                  </TableCell>
                  <TableCell>{t("applications.candidate")}</TableCell>
                  <TableCell>{t("applications.vacancy")}</TableCell>
                  <TableCell>{t("applications.branch")}</TableCell>
                  <TableCell>{t("applications.phone")}</TableCell>
                  <TableCell>{t("applications.date")}</TableCell>
                  <TableCell>{t("applications.status")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((application) => (
                  <TableRow
                    hover
                    selected={selectedSet.has(application.id)}
                    key={application.id}
                    role="link"
                    tabIndex={0}
                    aria-label={`${application.candidate_name} — ${application.vacancy_title}`}
                    onClick={() => openApplication(application.id)}
                    onKeyDown={(event) => {
                      if (event.target !== event.currentTarget) return;
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openApplication(application.id);
                      }
                    }}
                    sx={{ cursor: "pointer", "&:focus-visible": { outline: `2px solid ${theme.palette.primary.main}`, outlineOffset: -2 } }}
                  >
                    <TableCell padding="checkbox" onClick={(event) => event.stopPropagation()}>
                      <Checkbox
                        checked={selectedSet.has(application.id)}
                        onChange={() => toggleSelection(application.id)}
                        inputProps={{ "aria-label": t("applications.selectCandidate", { name: application.candidate_name }) }}
                      />
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" alignItems="center" spacing={1.25}>
                        <CandidateAvatar name={application.candidate_name} photoUrl={application.candidate_photo_url} className="h-9 w-9" />
                        <Typography variant="subtitle2" noWrap>{application.candidate_name}</Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>{application.vacancy_title}</TableCell>
                    <TableCell sx={{ color: "text.secondary" }}>{application.branch_name ?? "—"}</TableCell>
                    <TableCell sx={{ color: "text.secondary", whiteSpace: "nowrap" }}>{application.candidate_phone ?? "—"}</TableCell>
                    <TableCell sx={{ color: "text.secondary", whiteSpace: "nowrap" }}>{formatDate(application.created_at)}</TableCell>
                    <TableCell><ApplicationStatusChip status={statusById.get(application.status_id)} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ display: { xs: "grid", md: "none" }, gap: 1.5 }}>
            {items.map((application) => (
              <Card
                key={application.id}
                sx={{
                  border: `1px solid ${selectedSet.has(application.id) ? alpha(theme.palette.primary.main, 0.5) : theme.palette.divider}`,
                  boxShadow: selectedSet.has(application.id) ? `0 0 0 2px ${alpha(theme.palette.primary.main, 0.12)}` : undefined,
                }}
              >
                <CardContent sx={{ p: 2, "&:last-child": { pb: 2 } }}>
                  <Stack direction="row" alignItems="flex-start" spacing={1}>
                    <Checkbox
                      checked={selectedSet.has(application.id)}
                      onChange={() => toggleSelection(application.id)}
                      inputProps={{ "aria-label": t("applications.selectCandidate", { name: application.candidate_name }) }}
                      sx={{ ml: -1, mt: -0.75 }}
                    />
                    <Box
                      component="button"
                      type="button"
                      onClick={() => openApplication(application.id)}
                      sx={{
                        all: "unset",
                        display: "block",
                        minWidth: 0,
                        flexGrow: 1,
                        cursor: "pointer",
                        borderRadius: 1,
                        "&:focus-visible": { outline: `2px solid ${theme.palette.primary.main}`, outlineOffset: 3 },
                      }}
                    >
                      <Stack direction="row" alignItems="center" spacing={1.25}>
                        <CandidateAvatar name={application.candidate_name} photoUrl={application.candidate_photo_url} />
                        <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                          <Typography variant="subtitle2" noWrap>{application.candidate_name}</Typography>
                          <Typography variant="body2" color="text.secondary" noWrap>{application.vacancy_title}</Typography>
                        </Box>
                      </Stack>
                      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1} sx={{ mt: 1.5 }}>
                        <ApplicationStatusChip status={statusById.get(application.status_id)} />
                        <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>{formatDate(application.created_at)}</Typography>
                      </Stack>
                      {application.branch_name && (
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                          {application.branch_name}
                        </Typography>
                      )}
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Box>

          {pageCount > 1 && (
            <Stack alignItems="center" spacing={1} sx={{ mt: 3 }}>
              <Pagination
                count={pageCount}
                page={page}
                onChange={changePage}
                color="primary"
                siblingCount={0}
                boundaryCount={1}
                showFirstButton
                showLastButton
              />
              <Typography variant="caption" color="text.secondary">
                {t("applications.pageSummary", { from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, total), total })}
              </Typography>
            </Stack>
          )}
        </>
      )}

      {/* Detail drawer, opened by route so a card is linkable and shareable. */}
      <Dialog
        open={Boolean(routeId)}
        onOpenChange={(open) => !open && closeApplication()}
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
                    setStatus.mutate({
                      id: detail.data!.id,
                      statusId: v,
                      reason: transitionReason.trim() || undefined,
                    })
                  }
                >
                  <SelectTrigger className="w-44" aria-label={t("applications.status")}>
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
                  aria-label={t("applications.deleteTitle")}
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>

              <TextField
                fullWidth
                size="small"
                multiline
                minRows={2}
                value={transitionReason}
                label={t("applications.transitionReason")}
                placeholder={t("applications.transitionReasonPlaceholder")}
                helperText={t("applications.transitionReasonHint")}
                inputProps={{ maxLength: 1000 }}
                onChange={(event) => setTransitionReason(event.target.value)}
              />

              <section className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold">{t("applications.interviews")}</h3>
                  <Badge variant="outline">
                    {detail.data.interviews.filter((interview) => interview.status === "scheduled").length}
                  </Badge>
                </div>

                {detail.data.interviews.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("applications.noInterviews")}</p>
                ) : (
                  <Stack spacing={1}>
                    {detail.data.interviews.map((interview) => (
                      <Paper key={interview.id} variant="outlined" sx={{ p: 1.25, borderRadius: 1.5 }}>
                        <Stack spacing={0.75}>
                          <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
                            <Typography variant="body2" fontWeight={700}>
                              {interview.kind === "video"
                                ? t("applications.interviewVideo")
                                : interview.kind === "in_person"
                                  ? t("applications.interviewInPerson")
                                  : t("applications.interviewPhone")}
                            </Typography>
                            <Chip
                              size="small"
                              label={interview.status === "scheduled"
                                ? t("applications.interviewScheduled")
                                : interview.status === "completed"
                                  ? t("applications.interviewCompleted")
                                  : t("applications.interviewCancelled")}
                              color={interview.status === "completed" ? "success" : interview.status === "cancelled" ? "default" : "primary"}
                              variant="outlined"
                            />
                          </Stack>
                          <Typography variant="body2">
                            {formatDateTime(interview.scheduled_at)} · {t("applications.interviewMinutes", { count: interview.duration_minutes })}
                          </Typography>
                          {interview.location && <Typography variant="body2" color="text.secondary">{interview.location}</Typography>}
                          {interview.notes && <Typography variant="body2" color="text.secondary">{interview.notes}</Typography>}
                          {interview.status === "scheduled" && (
                            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                              <MuiButton
                                size="small"
                                variant="outlined"
                                disabled={updateInterview.isPending}
                                sx={{ minHeight: 44 }}
                                onClick={() => updateInterview.mutate({ applicationId: detail.data!.id, interviewId: interview.id, status: "completed" })}
                              >
                                {t("applications.markInterviewCompleted")}
                              </MuiButton>
                              <MuiButton
                                size="small"
                                color="inherit"
                                disabled={updateInterview.isPending}
                                sx={{ minHeight: 44 }}
                                onClick={() => updateInterview.mutate({ applicationId: detail.data!.id, interviewId: interview.id, status: "cancelled" })}
                              >
                                {t("applications.cancelInterview")}
                              </MuiButton>
                            </Stack>
                          )}
                        </Stack>
                      </Paper>
                    ))}
                  </Stack>
                )}

                <Stack
                  component="form"
                  spacing={1}
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (interviewAt && Number(interviewDuration) >= 15 && Number(interviewDuration) <= 480 && !addInterview.isPending) {
                      addInterview.mutate({ id: detail.data!.id });
                    }
                  }}
                >
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                    <TextField
                      select
                      size="small"
                      label={t("applications.interviewKind")}
                      value={interviewKind}
                      onChange={(event) => setInterviewKind(event.target.value as InterviewKind)}
                      sx={{ minWidth: { sm: 150 } }}
                    >
                      <MenuItem value="video">{t("applications.interviewVideo")}</MenuItem>
                      <MenuItem value="in_person">{t("applications.interviewInPerson")}</MenuItem>
                      <MenuItem value="phone">{t("applications.interviewPhone")}</MenuItem>
                    </TextField>
                    <TextField
                      required
                      size="small"
                      label={t("applications.interviewAt")}
                      type="datetime-local"
                      value={interviewAt}
                      onChange={(event) => setInterviewAt(event.target.value)}
                      InputLabelProps={{ shrink: true }}
                      fullWidth
                    />
                    <TextField
                      required
                      size="small"
                      label={t("applications.interviewDuration")}
                      type="number"
                      value={interviewDuration}
                      onChange={(event) => setInterviewDuration(event.target.value)}
                      inputProps={{ min: 15, max: 480 }}
                      sx={{ minWidth: { sm: 130 } }}
                    />
                  </Stack>
                  <TextField
                    size="small"
                    label={t("applications.interviewLocation")}
                    value={interviewLocation}
                    onChange={(event) => setInterviewLocation(event.target.value)}
                    inputProps={{ maxLength: 500 }}
                    fullWidth
                  />
                  <TextField
                    size="small"
                    multiline
                    minRows={2}
                    label={t("applications.interviewNotes")}
                    value={interviewNotes}
                    onChange={(event) => setInterviewNotes(event.target.value)}
                    inputProps={{ maxLength: 2000 }}
                    fullWidth
                  />
                  <MuiButton
                    type="submit"
                    variant="contained"
                    disabled={!interviewAt || Number(interviewDuration) < 15 || Number(interviewDuration) > 480 || addInterview.isPending}
                    sx={{ alignSelf: "flex-start", minHeight: 44 }}
                  >
                    {t("applications.scheduleInterview")}
                  </MuiButton>
                </Stack>
              </section>

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
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold">{t("applications.tasks")}</h3>
                  <Badge variant="outline">{detail.data.tasks.filter((task) => !task.completed_at).length}</Badge>
                </div>

                {detail.data.tasks.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("applications.noTasks")}</p>
                ) : (
                  <Stack spacing={1}>
                    {detail.data.tasks.map((task) => (
                      <Paper
                        key={task.id}
                        variant="outlined"
                        sx={{ display: "flex", alignItems: "flex-start", gap: 0.75, p: 0.75, borderRadius: 1.5 }}
                      >
                        <Checkbox
                          size="small"
                          checked={Boolean(task.completed_at)}
                          disabled={updateTask.isPending}
                          onChange={(event) => updateTask.mutate({
                            applicationId: detail.data!.id,
                            taskId: task.id,
                            completed: event.target.checked,
                          })}
                          inputProps={{ "aria-label": task.title }}
                          sx={{ mt: -0.65, ml: -0.65 }}
                        />
                        <Box sx={{ minWidth: 0, py: 0.25 }}>
                          <Typography
                            variant="body2"
                            sx={{ textDecoration: task.completed_at ? "line-through" : "none", color: task.completed_at ? "text.secondary" : "text.primary" }}
                          >
                            {task.title}
                          </Typography>
                          {task.due_at && (
                            <Typography variant="caption" color="text.secondary">
                              {formatDateTime(task.due_at)}
                            </Typography>
                          )}
                        </Box>
                      </Paper>
                    ))}
                  </Stack>
                )}

                <Stack
                  component="form"
                  direction={{ xs: "column", sm: "row" }}
                  spacing={1}
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (taskTitle.trim() && !addTask.isPending) {
                      addTask.mutate({ id: detail.data!.id, title: taskTitle.trim(), dueAt: taskDueAt });
                    }
                  }}
                >
                  <TextField
                    size="small"
                    label={t("applications.taskTitle")}
                    value={taskTitle}
                    onChange={(event) => setTaskTitle(event.target.value)}
                    fullWidth
                  />
                  <TextField
                    size="small"
                    label={t("applications.taskDue")}
                    type="datetime-local"
                    value={taskDueAt}
                    onChange={(event) => setTaskDueAt(event.target.value)}
                    InputLabelProps={{ shrink: true }}
                    sx={{ minWidth: { sm: 190 } }}
                  />
                  <MuiButton
                    type="submit"
                    variant="contained"
                    disabled={!taskTitle.trim() || addTask.isPending}
                    sx={{ whiteSpace: "nowrap" }}
                  >
                    {t("applications.addTask")}
                  </MuiButton>
                </Stack>
              </section>

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
                        <dd className="text-sm"><AnswerValue answer={answer} /></dd>
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
                      {h.reason && (
                        <Typography component="p" variant="caption" color="text.primary" sx={{ mt: 0.5 }}>
                          {h.reason}
                        </Typography>
                      )}
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
