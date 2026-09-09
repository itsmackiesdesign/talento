import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha, useTheme } from "@mui/material/styles";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bot,
  Braces,
  BriefcaseBusiness,
  CalendarClock,
  Check,
  CheckCircle2,
  CircleDot,
  FileUp,
  Globe2,
  GripVertical,
  Hash,
  Languages,
  ListChecks,
  MessageCircle,
  MessagesSquare,
  Pencil,
  Play,
  Send,
  Settings,
  ShieldCheck,
  TextCursorInput,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout";
import { api } from "@/lib/api";
import { markdownToPreviewHtml } from "@/lib/markdown";
import type { Question, QuestionType } from "@/lib/types";

type Scope = "all" | "common" | "vacancy";
type QuestionScope = Exclude<Scope, "all">;

const typeIcons: Record<QuestionType, typeof TextCursorInput> = {
  short_text: TextCursorInput,
  long_text: MessagesSquare,
  single_choice: CircleDot,
  multi_choice: ListChecks,
  number: Hash,
  phone: UserRound,
  file: FileUp,
  datetime: CalendarClock,
};

function SystemStep({
  icon: Icon,
  title,
  description,
  active = false,
  onClick,
}: {
  icon: typeof Bot;
  title: string;
  description: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const theme = useTheme();

  return (
    <Paper
      component={onClick ? "button" : "div"}
      onClick={onClick}
      variant="outlined"
      sx={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        p: 1.5,
        textAlign: "left",
        color: "text.primary",
        cursor: onClick ? "pointer" : "default",
        bgcolor: active ? alpha(theme.palette.primary.main, 0.06) : "background.paper",
        borderColor: active ? alpha(theme.palette.primary.main, 0.5) : "divider",
        boxShadow: "none",
      }}
    >
      <Box sx={{ display: "grid", placeItems: "center", width: 38, height: 38, flexShrink: 0, borderRadius: 1.25, bgcolor: alpha(theme.palette.primary.main, 0.1), color: "primary.main" }}>
        <Icon size={19} />
      </Box>
      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
        <Typography variant="subtitle2">{title}</Typography>
        <Typography variant="caption" color="text.secondary">{description}</Typography>
      </Box>
      <Chip size="small" label="System" variant="outlined" />
    </Paper>
  );
}

function QuestionStep({
  question,
  index,
  total,
  selected,
  disabled,
  onMove,
  onSelect,
}: {
  question: Question;
  index: number;
  total: number;
  selected: boolean;
  disabled: boolean;
  onMove: (direction: -1 | 1) => void;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const Icon = typeIcons[question.type];

  return (
    <Paper
      variant="outlined"
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        p: 1,
        bgcolor: selected ? alpha(theme.palette.primary.main, 0.06) : "background.paper",
        borderColor: selected ? alpha(theme.palette.primary.main, 0.5) : "divider",
        boxShadow: selected ? `0 0 0 1px ${alpha(theme.palette.primary.main, 0.08)}` : "none",
        transition: theme.transitions.create(["border-color", "background-color"]),
      }}
    >
      <Box sx={{ display: { xs: "none", sm: "grid" }, placeItems: "center", width: 28, color: "text.disabled" }}>
        <GripVertical size={18} />
      </Box>
      <Box
        component="button"
        onClick={onSelect}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          minWidth: 0,
          flexGrow: 1,
          p: 0.75,
          border: 0,
          color: "inherit",
          textAlign: "left",
          bgcolor: "transparent",
          cursor: "pointer",
        }}
      >
        <Box sx={{ display: "grid", placeItems: "center", width: 38, height: 38, flexShrink: 0, borderRadius: 1.25, bgcolor: alpha(theme.palette.info.main, 0.1), color: "info.main" }}>
          <Icon size={19} />
        </Box>
        <Box sx={{ minWidth: 0, flexGrow: 1 }}>
          <Typography
            component="div"
            variant="subtitle2"
            noWrap
            dangerouslySetInnerHTML={{ __html: markdownToPreviewHtml(question.text) }}
          />
          <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 0.25 }}>
            <Typography variant="caption" color="text.secondary">
              {t(`questions.types.${question.type}`)}
            </Typography>
            {question.is_required && <Chip size="small" label={t("common.required")} sx={{ height: 20, fontSize: 10 }} />}
            {question.is_filterable && <Chip size="small" color="info" label={t("questions.filterEnabled")} sx={{ height: 20, fontSize: 10 }} />}
          </Stack>
        </Box>
      </Box>

      <Stack direction="row" spacing={0.25}>
        <Tooltip title={t("botBuilder.moveUp", { defaultValue: "Выше" })}>
          <span>
            <IconButton size="small" disabled={disabled || index === 0} onClick={() => onMove(-1)} aria-label={t("botBuilder.moveUp", { defaultValue: "Переместить выше" })}>
              <ArrowUp size={17} />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title={t("botBuilder.moveDown", { defaultValue: "Ниже" })}>
          <span>
            <IconButton size="small" disabled={disabled || index === total - 1} onClick={() => onMove(1)} aria-label={t("botBuilder.moveDown", { defaultValue: "Переместить ниже" })}>
              <ArrowDown size={17} />
            </IconButton>
          </span>
        </Tooltip>
      </Stack>
    </Paper>
  );
}

function FlowSection({
  title,
  caption,
  questions,
  scope,
  visible,
  pending,
  selectedId,
  onSelect,
  onMove,
}: {
  title: string;
  caption: string;
  questions: Question[];
  scope: QuestionScope;
  visible: boolean;
  pending: boolean;
  selectedId: string | null;
  onSelect: (question: Question) => void;
  onMove: (scope: QuestionScope, questions: Question[], index: number, direction: -1 | 1) => void;
}) {
  const { t } = useTranslation();
  if (!visible) return null;

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-end" spacing={2} sx={{ mb: 1.25 }}>
        <Box>
          <Typography variant="overline" color="text.secondary">{title}</Typography>
          <Typography variant="caption" color="text.disabled" display="block">{caption}</Typography>
        </Box>
        <Chip size="small" label={questions.length} />
      </Stack>
      {pending ? (
        <Stack alignItems="center" sx={{ py: 4 }}><CircularProgress size={26} /></Stack>
      ) : questions.length ? (
        <Stack spacing={1}>
          {questions.map((question, index) => (
            <QuestionStep
              key={question.id}
              question={question}
              index={index}
              total={questions.length}
              selected={selectedId === question.id}
              disabled={pending}
              onSelect={() => onSelect(question)}
              onMove={(direction) => onMove(scope, questions, index, direction)}
            />
          ))}
        </Stack>
      ) : (
        <Paper variant="outlined" sx={{ p: 2.5, textAlign: "center", boxShadow: "none", borderStyle: "dashed" }}>
          <Typography variant="body2" color="text.secondary">{t("questions.empty")}</Typography>
        </Paper>
      )}
    </Box>
  );
}

function TelegramPreview({
  username,
  welcome,
  question,
  step,
  total,
  onPrevious,
  onNext,
}: {
  username?: string;
  welcome?: string | null;
  question?: Question;
  step: number;
  total: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const answerHint: Record<QuestionType, string> = {
    short_text: t("botBuilder.answerText", { defaultValue: "Введите ответ…" }),
    long_text: t("botBuilder.answerText", { defaultValue: "Введите ответ…" }),
    single_choice: t("botBuilder.chooseOption", { defaultValue: "Выберите вариант" }),
    multi_choice: t("botBuilder.chooseOptions", { defaultValue: "Выберите варианты" }),
    number: "0",
    phone: "+998 90 123 45 67",
    file: t("botBuilder.uploadFile", { defaultValue: "Прикрепить файл" }),
    datetime: "25.12.2026 10:00",
  };

  return (
    <Box sx={{ position: { xl: "sticky" }, top: { xl: 96 } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Box>
          <Typography variant="overline" color="text.secondary">{t("botBuilder.preview", { defaultValue: "Telegram preview" })}</Typography>
          <Typography variant="caption" color="text.disabled" display="block">{t("botBuilder.previewHint", { defaultValue: "Тот же порядок, который увидит кандидат" })}</Typography>
        </Box>
        <Chip size="small" icon={<Play size={14} />} label={`${step + 1}/${total + 1}`} />
      </Stack>

      <Box
        sx={{
          mx: "auto",
          maxWidth: 380,
          overflow: "hidden",
          border: `8px solid ${theme.palette.mode === "dark" ? "#25252B" : "#111116"}`,
          borderRadius: 4,
          bgcolor: theme.palette.mode === "dark" ? "#0E1621" : "#DDE7EF",
          boxShadow: theme.shadows[16],
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1.25} sx={{ p: 1.5, color: "common.white", bgcolor: "#517DA2" }}>
          <Box sx={{ display: "grid", placeItems: "center", width: 38, height: 38, borderRadius: "50%", bgcolor: "primary.main" }}><Bot size={20} /></Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="subtitle2" noWrap>{username ? `@${username}` : "talento bot"}</Typography>
            <Typography variant="caption" sx={{ opacity: 0.72 }}>{t("botBuilder.botStatus", { defaultValue: "бот" })}</Typography>
          </Box>
        </Stack>

        <Stack spacing={1.25} sx={{ minHeight: 430, p: 1.5, justifyContent: "flex-end" }}>
          <Box sx={{ alignSelf: "center", px: 1, py: 0.4, borderRadius: 1, color: "common.white", bgcolor: alpha("#1F2C38", 0.45) }}>
            <Typography variant="caption">{t("botBuilder.today", { defaultValue: "Сегодня" })}</Typography>
          </Box>
          <Box sx={{ alignSelf: "flex-start", maxWidth: "88%", p: 1.25, borderRadius: "12px 12px 12px 3px", bgcolor: theme.palette.mode === "dark" ? "#182533" : "#FFFFFF", color: theme.palette.mode === "dark" ? "#FFFFFF" : "#17212B", boxShadow: `0 1px 2px ${alpha("#000000", 0.15)}` }}>
            <Typography
              component="div"
              variant="body2"
              sx={{ "& p": { m: 0 } }}
              dangerouslySetInnerHTML={{
                __html: markdownToPreviewHtml(step === 0
                  ? (welcome || t("botBuilder.defaultWelcome", { defaultValue: "Здравствуйте! Давайте найдём подходящую вакансию." }))
                  : (question?.text ?? "")),
              }}
            />
            <Typography variant="caption" sx={{ display: "block", mt: 0.5, textAlign: "right", color: theme.palette.mode === "dark" ? "#7F91A4" : "#8D9CA8" }}>10:08</Typography>
          </Box>

          {step > 0 && question && (
            question.options?.length ? (
              <Stack spacing={0.65}>
                {question.options.slice(0, 4).map((option) => (
                  <Paper
                    key={option}
                    sx={{
                      display: "grid",
                      minHeight: 38,
                      placeItems: "center",
                      px: 1.5,
                      py: 0.75,
                      color: "common.white",
                      bgcolor: "#4B95D0",
                      borderRadius: 1,
                      boxShadow: "none",
                    }}
                  >
                    <Typography variant="body2" fontWeight={700}>{option}</Typography>
                  </Paper>
                ))}
              </Stack>
            ) : (
              <Paper sx={{ display: "flex", alignItems: "center", gap: 1, p: 0.75, pl: 1.25, bgcolor: theme.palette.mode === "dark" ? "#17212B" : "#FFFFFF", boxShadow: "none" }}>
                <Typography variant="body2" color="text.disabled" noWrap sx={{ flexGrow: 1 }}>{answerHint[question.type]}</Typography>
                <IconButton size="small" aria-label={t("botBuilder.send", { defaultValue: "Отправить" })} sx={{ color: "#4B95D0" }}><Send size={18} /></IconButton>
              </Paper>
            )
          )}
        </Stack>
      </Box>

      <Stack direction="row" spacing={1} justifyContent="center" sx={{ mt: 2 }}>
        <Button variant="outlined" disabled={step === 0} onClick={onPrevious} startIcon={<ArrowLeft size={17} />}>
          {t("common.back")}
        </Button>
        <Button variant="contained" disabled={step === total} onClick={onNext} endIcon={<ArrowRight size={17} />}>
          {t("common.next")}
        </Button>
      </Stack>
    </Box>
  );
}

export default function BotBuilderPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<Scope>("all");
  const [vacancyId, setVacancyId] = useState("");
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null);
  const [previewStep, setPreviewStep] = useState(0);

  const bot = useQuery({ queryKey: ["bot"], queryFn: api.bot.get, retry: false });
  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });
  const vacancies = useQuery({ queryKey: ["vacancies"], queryFn: () => api.vacancies.list() });
  const commonQuestions = useQuery({ queryKey: ["questions", "null"], queryFn: () => api.questions.list("null") });
  const vacancyQuestions = useQuery({
    queryKey: ["questions", vacancyId],
    queryFn: () => api.questions.list(vacancyId),
    enabled: Boolean(vacancyId),
  });

  useEffect(() => {
    if (!vacancyId && vacancies.data?.length) {
      setVacancyId((vacancies.data.find((vacancy) => vacancy.status === "active") ?? vacancies.data[0]).id);
    }
  }, [vacancyId, vacancies.data]);

  const common = commonQuestions.data ?? [];
  const specific = vacancyQuestions.data ?? [];
  const previewQuestions = useMemo(() => [...common, ...specific], [common, specific]);
  const selectedVacancy = vacancies.data?.find((vacancy) => vacancy.id === vacancyId);

  useEffect(() => {
    setPreviewStep((current) => Math.min(current, previewQuestions.length));
  }, [previewQuestions.length]);

  const reorder = useMutation({
    mutationFn: ({ ids }: { scope: QuestionScope; ids: string[] }) => api.questions.reorder(ids),
    onSuccess: async (_value, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["questions", variables.scope === "common" ? "null" : vacancyId] });
      toast.success(t("toast.orderSaved"));
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const moveQuestion = (questionScope: QuestionScope, questions: Question[], index: number, direction: -1 | 1) => {
    const destination = index + direction;
    if (destination < 0 || destination >= questions.length) return;
    const ids = questions.map((question) => question.id);
    [ids[index], ids[destination]] = [ids[destination], ids[index]];
    reorder.mutate({ scope: questionScope, ids });
  };

  const selectQuestion = (question: Question) => {
    setSelectedQuestionId(question.id);
    const index = previewQuestions.findIndex((item) => item.id === question.id);
    if (index >= 0) setPreviewStep(index + 1);
  };

  const botConnected = Boolean(bot.data);
  const isLoading = vacancies.isPending || commonQuestions.isPending || company.isPending;
  const validationItems = [
    { ok: botConnected, label: botConnected ? t("botBuilder.botConnected", { defaultValue: "Telegram-бот подключён" }) : t("botBuilder.botMissing", { defaultValue: "Подключите Telegram-бота" }) },
    { ok: Boolean(bot.data?.welcome_message), label: bot.data?.welcome_message ? t("botBuilder.welcomeReady", { defaultValue: "Приветствие настроено" }) : t("botBuilder.welcomeMissing", { defaultValue: "Добавьте приветствие" }) },
    { ok: previewQuestions.length > 0, label: previewQuestions.length ? t("botBuilder.questionsReady", { defaultValue: "{{count}} вопросов в сценарии", count: previewQuestions.length }) : t("botBuilder.questionsMissing", { defaultValue: "Добавьте вопросы" }) },
  ];
  const health = validationItems.filter((item) => item.ok).length;

  return (
    <>
      <PageHeader
        title={t("botBuilder.title", { defaultValue: "Bot Studio" })}
        description={t("botBuilder.subtitle", { defaultValue: "Визуально настройте путь кандидата — от первого сообщения до отправленной заявки." })}
        action={(
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <Button component={Link} to="/settings" variant="outlined" startIcon={<Settings size={18} />}>
              {t("botBuilder.botSettings", { defaultValue: "Настройки бота" })}
            </Button>
            {selectedVacancy && (
              <Button component={Link} to={`/vacancies/${selectedVacancy.id}/questions`} variant="contained" startIcon={<Pencil size={18} />}>
                {t("botBuilder.editQuestions", { defaultValue: "Редактировать вопросы" })}
              </Button>
            )}
          </Stack>
        )}
      />

      {!botConnected && !bot.isPending && (
        <Alert severity="warning" action={<Button component={Link} to="/settings" color="inherit">{t("common.open")}</Button>} sx={{ mb: 3 }}>
          {t("botBuilder.noBotAlert", { defaultValue: "Сценарий можно подготовить сейчас, но для теста и публикации нужно подключить Telegram-бота." })}
        </Alert>
      )}

      <Card sx={{ mb: 3, boxShadow: "none", border: `1px solid ${theme.palette.divider}` }}>
        <CardContent>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(260px, 1fr) auto auto" }, gap: 2, alignItems: "center" }}>
            <TextField
              select
              label={t("botBuilder.vacancy", { defaultValue: "Сценарий вакансии" })}
              value={vacancyId}
              onChange={(event) => { setVacancyId(event.target.value); setSelectedQuestionId(null); setPreviewStep(0); }}
              fullWidth
              disabled={vacancies.isPending || !vacancies.data?.length}
            >
              {(vacancies.data ?? []).map((vacancy) => (
                <MenuItem key={vacancy.id} value={vacancy.id}>{vacancy.title}</MenuItem>
              ))}
            </TextField>
            <Stack direction="row" spacing={1} alignItems="center">
              <Box sx={{ display: "grid", placeItems: "center", width: 42, height: 42, borderRadius: 1.25, color: health === validationItems.length ? "success.main" : "warning.main", bgcolor: alpha(health === validationItems.length ? theme.palette.success.main : theme.palette.warning.main, 0.1) }}>
                <ShieldCheck size={21} />
              </Box>
              <Box>
                <Typography variant="subtitle2">{health}/{validationItems.length} {t("botBuilder.checks", { defaultValue: "проверки" })}</Typography>
                <Typography variant="caption" color="text.secondary">{t("botBuilder.scenarioHealth", { defaultValue: "Готовность сценария" })}</Typography>
              </Box>
            </Stack>
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
              <Chip size="small" icon={<Languages size={15} />} label={(company.data?.enabled_languages ?? []).map((language) => language.toUpperCase()).join(" · ") || "RU"} />
              <Chip size="small" color={selectedVacancy?.status === "active" ? "success" : "default"} label={selectedVacancy?.status === "active" ? t("vacancies.statusActive") : t("vacancies.statusDraft")} />
            </Stack>
          </Box>
        </CardContent>
      </Card>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(0, 1fr)", lg: "230px minmax(0, 1fr)", xl: "220px minmax(420px, 1fr) 390px" }, gap: 3, alignItems: "start" }}>
        <Stack spacing={2.5}>
          <Card>
            <CardContent>
              <Typography variant="overline" color="text.secondary">{t("botBuilder.structure", { defaultValue: "Структура" })}</Typography>
              <Stack spacing={0.75} sx={{ mt: 1.5 }}>
                {[
                  { id: "all" as const, icon: Braces, label: t("botBuilder.wholeJourney", { defaultValue: "Весь путь" }), count: common.length + specific.length + 4 },
                  { id: "common" as const, icon: UserRound, label: t("questions.common"), count: common.length },
                  { id: "vacancy" as const, icon: BriefcaseBusiness, label: t("questions.specific"), count: specific.length },
                ].map(({ id, icon: Icon, label, count }) => (
                  <Button
                    key={id}
                    variant={scope === id ? "contained" : "text"}
                    color={scope === id ? "primary" : "inherit"}
                    onClick={() => setScope(id)}
                    startIcon={<Icon size={17} />}
                    sx={{ justifyContent: "flex-start" }}
                  >
                    <Box component="span" sx={{ minWidth: 0, flexGrow: 1, overflow: "hidden", textOverflow: "ellipsis", textAlign: "left" }}>{label}</Box>
                    <Box component="span" sx={{ ml: 1, opacity: 0.68 }}>{count}</Box>
                  </Button>
                ))}
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                <ShieldCheck size={18} color={theme.palette.primary.main} />
                <Typography variant="subtitle2">{t("botBuilder.validation", { defaultValue: "Проверка" })}</Typography>
              </Stack>
              <Stack spacing={1.25}>
                {validationItems.map((item) => (
                  <Stack key={item.label} direction="row" spacing={1} alignItems="flex-start">
                    {item.ok ? <CheckCircle2 size={17} color={theme.palette.success.main} /> : <CircleDot size={17} color={theme.palette.warning.main} />}
                    <Typography variant="caption" color={item.ok ? "text.secondary" : "text.primary"}>{item.label}</Typography>
                  </Stack>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Stack>

        <Card sx={{ minWidth: 0 }}>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2} sx={{ mb: 2.5 }}>
              <Box>
                <Typography variant="h6">{t("botBuilder.scenario", { defaultValue: "Сценарий кандидата" })}</Typography>
                <Typography variant="body2" color="text.secondary">{t("botBuilder.scenarioHint", { defaultValue: "Меняйте порядок стрелками; изменения сразу сохраняются." })}</Typography>
              </Box>
              {reorder.isPending && <CircularProgress size={22} />}
            </Stack>

            {isLoading ? (
              <Stack alignItems="center" sx={{ py: 8 }}><CircularProgress /></Stack>
            ) : (
              <Stack spacing={2.5}>
                {scope === "all" && (
                  <>
                    <SystemStep icon={MessageCircle} title={t("botBuilder.start", { defaultValue: "Старт и приветствие" })} description={t("botBuilder.startHint", { defaultValue: "Первое сообщение после /start" })} active={previewStep === 0} onClick={() => setPreviewStep(0)} />
                    <Box sx={{ height: 18, width: 2, bgcolor: "divider", mx: "auto !important" }} />
                    <SystemStep icon={Globe2} title={t("botBuilder.language", { defaultValue: "Выбор языка" })} description={(company.data?.enabled_languages ?? ["ru"]).map((language) => language.toUpperCase()).join(" · ")} />
                  </>
                )}

                <FlowSection
                  title={t("questions.common")}
                  caption={t("botBuilder.profileCaption", { defaultValue: "Профиль кандидата для всех вакансий" })}
                  questions={common}
                  scope="common"
                  visible={scope === "all" || scope === "common"}
                  pending={commonQuestions.isPending || reorder.isPending}
                  selectedId={selectedQuestionId}
                  onSelect={selectQuestion}
                  onMove={moveQuestion}
                />

                {scope === "all" && (
                  <SystemStep icon={BriefcaseBusiness} title={t("botBuilder.vacancySelection", { defaultValue: "Выбор вакансии" })} description={selectedVacancy?.title ?? t("botBuilder.noVacancy", { defaultValue: "Вакансия не выбрана" })} />
                )}

                <FlowSection
                  title={t("questions.specific")}
                  caption={selectedVacancy?.title ?? t("botBuilder.vacancyCaption", { defaultValue: "Отдельный сценарий вакансии" })}
                  questions={specific}
                  scope="vacancy"
                  visible={scope === "all" || scope === "vacancy"}
                  pending={vacancyQuestions.isPending || reorder.isPending}
                  selectedId={selectedQuestionId}
                  onSelect={selectQuestion}
                  onMove={moveQuestion}
                />

                {scope === "all" && (
                  <SystemStep icon={Check} title={t("botBuilder.complete", { defaultValue: "Подтверждение заявки" })} description={t("botBuilder.completeHint", { defaultValue: "Создание заявки и финальное сообщение" })} />
                )}
              </Stack>
            )}
          </CardContent>
          <Divider />
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1.5} sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary" sx={{ alignSelf: { sm: "center" } }}>
              {t("botBuilder.builderFoundation", { defaultValue: "Основа Flow Studio работает на текущих вопросах; ветвления и версии добавляются следующим этапом." })}
            </Typography>
            {selectedVacancy && (
              <Button component={Link} to={`/vacancies/${selectedVacancy.id}/questions`} size="small" endIcon={<ArrowRight size={16} />}>
                {t("botBuilder.openEditor", { defaultValue: "Открыть редактор" })}
              </Button>
            )}
          </Stack>
        </Card>

        <Box sx={{ display: { xs: "block", xl: "block" }, gridColumn: { lg: "1 / -1", xl: "auto" } }}>
          <TelegramPreview
            username={bot.data?.bot_username}
            welcome={bot.data?.welcome_message}
            question={previewStep > 0 ? previewQuestions[previewStep - 1] : undefined}
            step={previewStep}
            total={previewQuestions.length}
            onPrevious={() => setPreviewStep((current) => Math.max(0, current - 1))}
            onNext={() => setPreviewStep((current) => Math.min(previewQuestions.length, current + 1))}
          />
        </Box>
      </Box>
    </>
  );
}
