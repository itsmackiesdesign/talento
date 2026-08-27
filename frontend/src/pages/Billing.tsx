import { useQuery } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, Infinity, WalletCards } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const money = new Intl.NumberFormat("uz-UZ");

export default function BillingPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const summary = useQuery({ queryKey: ["billing", "summary"], queryFn: api.billing.summary });
  const transactions = useQuery({
    queryKey: ["billing", "transactions", page],
    queryFn: () => api.billing.transactions(page),
  });
  const totalPages = Math.max(1, Math.ceil((transactions.data?.total ?? 0) / 25));

  return (
    <div>
      <PageHeader title={t("billing.title")} description={t("billing.subtitle")} />

      {summary.isPending ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-32" />
          ))}
        </div>
      ) : summary.isError ? (
        <p className="text-sm text-destructive">{summary.error.message}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <p className="text-sm text-muted-foreground">{t("billing.mode")}</p>
                <p className="mt-2 text-xl font-semibold">
                  {summary.data?.billing_mode === "unlimited"
                    ? t("billing.unlimited")
                    : t("billing.payPerApplication")}
                </p>
              </div>
              {summary.data?.billing_mode === "unlimited" ? (
                <Infinity className="size-8 text-primary" />
              ) : (
                <WalletCards className="size-8 text-primary" />
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5">
              <p className="text-sm text-muted-foreground">{t("billing.balance")}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums">
                {money.format(summary.data?.balance_uzs ?? 0)} UZS
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5">
              <p className="text-sm text-muted-foreground">
                {summary.data?.billing_mode === "unlimited"
                  ? t("billing.applications")
                  : t("billing.price")}
              </p>
              <p className="mt-2 text-2xl font-semibold tabular-nums">
                {summary.data?.billing_mode === "unlimited"
                  ? t("billing.unlimited")
                  : `${money.format(summary.data?.application_price_uzs ?? 0)} UZS`}
              </p>
              {summary.data?.remaining_applications != null && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("billing.remaining", { count: summary.data.remaining_applications })}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>{t("billing.history")}</CardTitle>
        </CardHeader>
        <CardContent>
          {transactions.isPending ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-14 w-full" />
              ))}
            </div>
          ) : transactions.isError ? (
            <p className="text-sm text-destructive">{transactions.error.message}</p>
          ) : transactions.data?.items.length ? (
            <div className="space-y-2">
              {transactions.data.items.map((transaction) => {
                const positive = transaction.amount_uzs > 0;
                return (
                  <div
                    key={transaction.id}
                    className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={cn(
                          "grid size-9 place-items-center rounded-full",
                          positive
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-amber-500/10 text-amber-600",
                        )}
                      >
                        {positive ? <ArrowDownLeft /> : <ArrowUpRight />}
                      </span>
                      <div>
                        <p className="text-sm font-medium">
                          {transaction.kind === "signup_bonus"
                            ? t("billing.welcomeBonus")
                            : transaction.kind === "top_up"
                              ? t("billing.topUp")
                              : t("billing.applicationCharge")}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {transaction.vacancy_title ?? transaction.description ?? "—"} ·{" "}
                          {new Date(transaction.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p
                        className={cn(
                          "font-semibold tabular-nums",
                          positive ? "text-emerald-600" : "text-foreground",
                        )}
                      >
                        {positive ? "+" : ""}{money.format(transaction.amount_uzs)} UZS
                      </p>
                      <Badge variant="outline">
                        {t("billing.after")}: {money.format(transaction.balance_after_uzs)} UZS
                      </Badge>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {t("billing.empty")}
            </p>
          )}

          <div className="mt-4 flex items-center justify-between border-t pt-4 text-sm">
            <span className="text-muted-foreground">
              {page} / {totalPages}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                {t("common.back")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                {t("common.next")}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
