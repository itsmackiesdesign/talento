import { useQuery } from "@tanstack/react-query";
import { Briefcase, Inbox, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";

// Cycled by column index — statuses are HR-defined now, so there's no fixed key to key a
// color off of. Same palette family as Applications.tsx's kanban accents.
const COLOR_PALETTE = [
  "#3b82f6", "#8b5cf6", "#f59e0b", "#06b6d4", "#10b981", "#ef4444", "#ec4899", "#84cc16",
];

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: typeof Inbox;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="rounded-lg bg-primary/10 p-2.5 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const { data, isPending } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.dashboard.stats(30),
  });
  const statuses = useQuery({
    queryKey: ["application-statuses"],
    queryFn: api.applicationStatuses.list,
  });

  if (isPending || statuses.isPending) {
    return (
      <>
        <PageHeader title={t("dashboard.title")} />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="mt-4 h-72" />
      </>
    );
  }

  if (!data) return null;

  const dailyChart = data.daily.map((point) => ({
    ...point,
    label: new Date(point.date).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" }),
  }));
  const hasDaily = data.daily.some((d) => d.count > 0);
  // Ordered by the fetched status list (same order the kanban columns use), not by
  // whatever order the by_status dict's keys happen to iterate in.
  const statusData = (statuses.data ?? [])
    .map((s, index) => ({
      id: s.id,
      label: s.label,
      count: data.by_status[s.id] ?? 0,
      color: COLOR_PALETTE[index % COLOR_PALETTE.length],
    }))
    .filter((d) => d.count > 0);

  return (
    <>
      <PageHeader title={t("dashboard.title")} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label={t("dashboard.total")} value={data.applications_total} icon={Inbox} />
        <StatCard label={t("dashboard.last7")} value={data.applications_7d} icon={TrendingUp} />
        <StatCard label={t("dashboard.last30")} value={data.applications_30d} icon={TrendingUp} />
        <StatCard
          label={t("dashboard.activeVacancies")}
          value={data.active_vacancies}
          icon={Briefcase}
        />
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">{t("dashboard.byDay")}</CardTitle>
        </CardHeader>
        <CardContent>
          {hasDaily ? (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyChart} margin={{ left: -20, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    interval="preserveStartEnd"
                    minTickGap={24}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: "hsl(var(--accent))" }}
                    contentStyle={{
                      background: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState title={t("dashboard.noData")} />
          )}
        </CardContent>
      </Card>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("dashboard.byStatus")}</CardTitle>
          </CardHeader>
          <CardContent>
            {statusData.length ? (
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={statusData} layout="vertical" margin={{ left: 24, right: 16 }}>
                    <XAxis type="number" hide allowDecimals={false} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={92}
                      tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "hsl(var(--accent))" }}
                      contentStyle={{
                        background: "hsl(var(--popover))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {statusData.map((entry) => (
                        <Cell key={entry.id} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState title={t("dashboard.noData")} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("dashboard.byVacancy")}</CardTitle>
          </CardHeader>
          <CardContent>
            {data.by_vacancy.length ? (
              <ul className="space-y-2.5">
                {data.by_vacancy.map((row) => (
                  <li key={row.vacancy_id} className="flex items-center justify-between gap-4 text-sm">
                    <span className="truncate">{row.title}</span>
                    <span className="shrink-0 font-medium tabular-nums">{row.count}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title={t("dashboard.noData")} />
            )}
          </CardContent>
        </Card>
      </div>

      {data.by_branch.length > 1 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-base">{t("dashboard.byBranch")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5">
              {data.by_branch.map((row) => (
                <li
                  key={row.branch_id ?? "none"}
                  className="flex items-center justify-between gap-4 text-sm"
                >
                  <span className="truncate">{row.name}</span>
                  <span className="shrink-0 font-medium tabular-nums">{row.count}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}
