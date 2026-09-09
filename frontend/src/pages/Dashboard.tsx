import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import LinearProgress from "@mui/material/LinearProgress";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { alpha, useTheme } from "@mui/material/styles";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, BriefcaseBusiness, CalendarRange, Inbox, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/layout";
import { api } from "@/lib/api";

const metricColors = ["primary", "success", "info", "warning"] as const;

function MetricCard({
  label,
  value,
  icon: Icon,
  color,
  note,
}: {
  label: string;
  value: number;
  icon: typeof Inbox;
  color: (typeof metricColors)[number];
  note: string;
}) {
  const theme = useTheme();
  const tone = theme.palette[color].main;

  return (
    <Card sx={{ overflow: "hidden", boxShadow: "none", border: `1px solid ${theme.palette.divider}` }}>
      <CardContent>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={2}>
          <Box>
            <Typography variant="body2" color="text.secondary">{label}</Typography>
            <Typography variant="h3" sx={{ mt: 1, fontVariantNumeric: "tabular-nums" }}>{value}</Typography>
            <Typography variant="caption" color="text.disabled">{note}</Typography>
          </Box>
          <Box
            sx={{
              display: "grid",
              placeItems: "center",
              width: 48,
              height: 48,
              flexShrink: 0,
              borderRadius: 2,
              color: tone,
              bgcolor: alpha(tone, 0.12),
            }}
          >
            <Icon size={23} />
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <PageHeader title="Дашборд" />
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", xl: "repeat(4, 1fr)" }, gap: 2.5 }}>
        {[0, 1, 2, 3].map((item) => <Skeleton key={item} variant="rounded" height={140} />)}
      </Box>
      <Skeleton variant="rounded" height={360} sx={{ mt: 3 }} />
    </>
  );
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { data, isPending } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.dashboard.stats(30),
  });
  const statuses = useQuery({
    queryKey: ["application-statuses"],
    queryFn: api.applicationStatuses.list,
  });

  if (isPending || statuses.isPending) return <DashboardSkeleton />;
  if (!data) return null;

  const dailyChart = data.daily.map((point) => ({
    ...point,
    label: new Date(point.date).toLocaleDateString(undefined, { day: "2-digit", month: "short" }),
  }));
  const hasDaily = data.daily.some((point) => point.count > 0);
  const maxStatus = Math.max(1, ...Object.values(data.by_status));
  const statusData = (statuses.data ?? [])
    .map((status) => ({ ...status, count: data.by_status[status.id] ?? 0 }))
    .filter((status) => status.count > 0);
  const weeklyShare = data.applications_30d
    ? Math.round((data.applications_7d / data.applications_30d) * 100)
    : 0;

  const actions = [
    {
      title: data.active_vacancies
        ? t("dashboard.reviewApplications", { defaultValue: "Разобрать новые заявки" })
        : t("dashboard.launchVacancy", { defaultValue: "Запустить первую вакансию" }),
      description: data.active_vacancies
        ? t("dashboard.reviewApplicationsHint", { defaultValue: "Проверьте кандидатов и обновите этапы воронки." })
        : t("dashboard.launchVacancyHint", { defaultValue: "Опубликуйте вакансию, чтобы начать получать кандидатов." }),
      to: data.active_vacancies ? "/applications" : "/vacancies",
      icon: data.active_vacancies ? Inbox : BriefcaseBusiness,
      color: theme.palette.primary.main,
    },
    {
      title: t("dashboard.configureJourney", { defaultValue: "Настроить путь кандидата" }),
      description: t("dashboard.configureJourneyHint", { defaultValue: "Проверьте вопросы и сценарий Telegram-бота." }),
      to: "/bot-builder",
      icon: Bot,
      color: theme.palette.info.main,
    },
  ];

  return (
    <>
      <PageHeader
        title={t("dashboard.title")}
        description={t("dashboard.subtitle", {
          defaultValue: "Ключевые показатели найма и действия, которые требуют внимания сегодня.",
        })}
        action={(
          <Button component={Link} to="/applications" variant="contained" endIcon={<ArrowRight size={18} />}>
            {t("nav.applications")}
          </Button>
        )}
      />

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", xl: "repeat(4, 1fr)" }, gap: 2.5 }}>
        <MetricCard
          label={t("dashboard.total")}
          value={data.applications_total}
          icon={Inbox}
          color="primary"
          note={t("dashboard.allTime", { defaultValue: "за всё время" })}
        />
        <MetricCard
          label={t("dashboard.last7")}
          value={data.applications_7d}
          icon={TrendingUp}
          color="success"
          note={t("dashboard.monthShare", { defaultValue: "{{share}}% от объёма за 30 дней", share: weeklyShare })}
        />
        <MetricCard
          label={t("dashboard.last30")}
          value={data.applications_30d}
          icon={CalendarRange}
          color="info"
          note={t("dashboard.currentPeriod", { defaultValue: "текущий период" })}
        />
        <MetricCard
          label={t("dashboard.activeVacancies")}
          value={data.active_vacancies}
          icon={BriefcaseBusiness}
          color="warning"
          note={t("dashboard.acceptingCandidates", { defaultValue: "принимают кандидатов" })}
        />
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.65fr) minmax(310px, 0.75fr)" }, gap: 3, mt: 3 }}>
        <Card>
          <CardContent>
            <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={2} sx={{ mb: 3 }}>
              <Box>
                <Typography variant="h6">{t("dashboard.byDay")}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {t("dashboard.last30Caption", { defaultValue: "Динамика входящих заявок за последние 30 дней" })}
                </Typography>
              </Box>
              <Chip size="small" label={t("dashboard.liveData", { defaultValue: "Live data" })} color="primary" variant="outlined" />
            </Stack>

            {hasDaily ? (
              <Box sx={{ width: "100%", height: 310 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyChart} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                    <defs>
                      <linearGradient id="talentoBars" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={theme.palette.primary.main} stopOpacity={1} />
                        <stop offset="100%" stopColor={theme.palette.primary.light} stopOpacity={0.58} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 4" stroke={theme.palette.divider} vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 11, fill: theme.palette.text.disabled }}
                      interval="preserveStartEnd"
                      minTickGap={28}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: theme.palette.text.disabled }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <ChartTooltip
                      cursor={{ fill: alpha(theme.palette.primary.main, 0.06) }}
                      contentStyle={{
                        background: theme.palette.background.paper,
                        border: `1px solid ${theme.palette.divider}`,
                        borderRadius: 10,
                        color: theme.palette.text.primary,
                        boxShadow: theme.shadows[8],
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" fill="url(#talentoBars)" radius={[6, 6, 2, 2]} maxBarSize={34} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Stack alignItems="center" justifyContent="center" spacing={1} sx={{ minHeight: 310, textAlign: "center" }}>
                <Box sx={{ display: "grid", placeItems: "center", width: 56, height: 56, borderRadius: 2, bgcolor: alpha(theme.palette.primary.main, 0.1), color: "primary.main" }}>
                  <TrendingUp size={26} />
                </Box>
                <Typography variant="subtitle1">{t("dashboard.noData")}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 360 }}>
                  {t("dashboard.noDataHint", { defaultValue: "График появится, когда бот получит первые заявки." })}
                </Typography>
              </Stack>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6">{t("dashboard.actionCenter", { defaultValue: "Центр действий" })}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2.5 }}>
              {t("dashboard.actionCenterHint", { defaultValue: "Следующие шаги для стабильного потока кандидатов" })}
            </Typography>
            <Stack spacing={1.5}>
              {actions.map(({ title, description, to, icon: Icon, color }) => (
                <Box
                  key={to}
                  component={Link}
                  to={to}
                  sx={{
                    display: "flex",
                    gap: 1.5,
                    p: 1.75,
                    color: "text.primary",
                    textDecoration: "none",
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 1.5,
                    transition: theme.transitions.create(["transform", "border-color", "background-color"]),
                    "&:hover": { transform: "translateY(-2px)", borderColor: alpha(color, 0.5), bgcolor: alpha(color, 0.04) },
                    "@media (prefers-reduced-motion: reduce)": { transition: "none", "&:hover": { transform: "none" } },
                  }}
                >
                  <Box sx={{ display: "grid", placeItems: "center", width: 40, height: 40, flexShrink: 0, borderRadius: 1.25, color, bgcolor: alpha(color, 0.1) }}>
                    <Icon size={20} />
                  </Box>
                  <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                    <Typography variant="subtitle2">{title}</Typography>
                    <Typography variant="caption" color="text.secondary">{description}</Typography>
                  </Box>
                  <ArrowRight size={18} color={theme.palette.text.disabled} />
                </Box>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "repeat(2, minmax(0, 1fr))" }, gap: 3, mt: 3 }}>
        <Card>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
              <Box>
                <Typography variant="h6">{t("dashboard.byStatus")}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {t("dashboard.pipelineCaption", { defaultValue: "Распределение текущей базы по этапам" })}
                </Typography>
              </Box>
              <Button component={Link} to="/applications" size="small" endIcon={<ArrowRight size={16} />}>
                {t("common.open")}
              </Button>
            </Stack>
            {statusData.length ? (
              <Stack spacing={2.25}>
                {statusData.map((status) => (
                  <Box key={status.id}>
                    <Stack direction="row" justifyContent="space-between" spacing={2} sx={{ mb: 0.75 }}>
                      <Typography variant="body2" fontWeight={600}>{status.label}</Typography>
                      <Typography variant="body2" fontWeight={700} sx={{ fontVariantNumeric: "tabular-nums" }}>{status.count}</Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={(status.count / maxStatus) * 100}
                      sx={{ height: 7, borderRadius: 4, bgcolor: alpha(status.color, 0.12), "& .MuiLinearProgress-bar": { bgcolor: status.color, borderRadius: 4 } }}
                    />
                  </Box>
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">{t("dashboard.noData")}</Typography>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Box>
                <Typography variant="h6">{t("dashboard.byVacancy")}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {t("dashboard.vacancyCaption", { defaultValue: "Где формируется основной поток" })}
                </Typography>
              </Box>
              <Button component={Link} to="/vacancies" size="small" endIcon={<ArrowRight size={16} />}>
                {t("common.open")}
              </Button>
            </Stack>
            {data.by_vacancy.length ? (
              <Stack divider={<Box sx={{ borderTop: `1px dashed ${theme.palette.divider}` }} />}>
                {data.by_vacancy.slice(0, 7).map((row, index) => (
                  <Stack key={row.vacancy_id} direction="row" alignItems="center" spacing={1.5} sx={{ py: 1.4 }}>
                    <Box sx={{ display: "grid", placeItems: "center", width: 34, height: 34, borderRadius: 1, bgcolor: alpha(theme.palette.primary.main, 0.08), color: "primary.main" }}>
                      <Typography variant="caption" fontWeight={800}>{String(index + 1).padStart(2, "0")}</Typography>
                    </Box>
                    <Typography variant="body2" fontWeight={600} noWrap sx={{ flexGrow: 1 }}>{row.title}</Typography>
                    <Chip size="small" label={row.count} />
                  </Stack>
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">{t("dashboard.noData")}</Typography>
            )}
          </CardContent>
        </Card>
      </Box>
    </>
  );
}
