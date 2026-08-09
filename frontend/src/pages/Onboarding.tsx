import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { MarkdownField } from "@/components/markdown-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuth } from "@/store/auth";

/** Three-step wizard: company → bot → first vacancy. Each step reads its "already done"
 *  state from the API, so a half-finished onboarding resumes where it left off instead of
 *  restarting. */
export default function OnboardingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const setCompanyId = useAuth((s) => s.setCompanyId);

  const [companyName, setCompanyName] = useState("");
  const [botToken, setBotToken] = useState("");
  const [vacancyTitle, setVacancyTitle] = useState("");
  const [vacancyDescription, setVacancyDescription] = useState("");

  const me = useQuery({ queryKey: ["me"], queryFn: api.auth.me });
  const company = me.data?.companies[0];

  const bot = useQuery({
    queryKey: ["bot"],
    queryFn: api.bot.get,
    enabled: Boolean(company),
    retry: false,
  });

  const createCompany = useMutation({
    mutationFn: () => api.company.create({ name: companyName.trim() }),
    onSuccess: async (created) => {
      setCompanyId(created.id);
      await qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(t("toast.created"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const connectBot = useMutation({
    mutationFn: () => api.bot.connect(botToken.trim()),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["bot"] });
      toast.success(t("toast.botConnected"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const createVacancy = useMutation({
    mutationFn: () =>
      api.vacancies.create({
        title: vacancyTitle.trim(),
        description: vacancyDescription.trim(),
        status: "active",
      }),
    onSuccess: () => {
      toast.success(t("toast.created"));
      navigate("/");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const hasCompany = Boolean(company);
  const hasBot = Boolean(bot.data);
  const current = !hasCompany ? 1 : !hasBot ? 2 : 3;

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 p-4 py-10">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">{t("onboarding.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("onboarding.step", { n: current })}</p>
      </div>

      <div className="flex items-center gap-2">
        {[1, 2, 3].map((step) => (
          <div
            key={step}
            className={cn(
              "h-1.5 flex-1 rounded-full transition-colors",
              step <= current ? "bg-primary" : "bg-muted",
            )}
          />
        ))}
      </div>

      {/* Step 1 — company */}
      <Card className={cn(current !== 1 && "opacity-60")}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {hasCompany && <Check className="h-4 w-4 text-emerald-500" />}
            {t("onboarding.companyTitle")}
          </CardTitle>
          <CardDescription>{t("onboarding.companyDesc")}</CardDescription>
        </CardHeader>
        {current === 1 && (
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="company">{t("onboarding.companyName")}</Label>
              <Input
                id="company"
                value={companyName}
                placeholder="Acme Coffee"
                onChange={(e) => setCompanyName(e.target.value)}
              />
            </div>
            <Button
              onClick={() => createCompany.mutate()}
              disabled={!companyName.trim() || createCompany.isPending}
            >
              {t("common.create")}
            </Button>
          </CardContent>
        )}
      </Card>

      {/* Step 2 — bot */}
      <Card className={cn(current !== 2 && "opacity-60")}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {hasBot && <Check className="h-4 w-4 text-emerald-500" />}
            {t("onboarding.botTitle")}
          </CardTitle>
          <CardDescription>{t("onboarding.botDesc")}</CardDescription>
        </CardHeader>
        {current === 2 && (
          <CardContent className="space-y-4">
            <ol className="space-y-2 text-sm text-muted-foreground">
              {["botStep1", "botStep2", "botStep3"].map((key, index) => (
                <li key={key} className="flex gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-foreground">
                    {index + 1}
                  </span>
                  {t(`onboarding.${key}`)}
                </li>
              ))}
            </ol>

            <a
              href="https://t.me/BotFather"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
            >
              @BotFather <ExternalLink className="h-3 w-3" />
            </a>

            <div className="space-y-2">
              <Label htmlFor="token">{t("onboarding.botToken")}</Label>
              <Input
                id="token"
                value={botToken}
                placeholder="123456789:AAH…"
                onChange={(e) => setBotToken(e.target.value)}
              />
            </div>

            <Button
              onClick={() => connectBot.mutate()}
              disabled={!botToken.trim() || connectBot.isPending}
            >
              {connectBot.isPending ? t("common.loading") : t("onboarding.connect")}
            </Button>
          </CardContent>
        )}
      </Card>

      {/* Step 3 — first vacancy */}
      <Card className={cn(current !== 3 && "opacity-60")}>
        <CardHeader>
          <CardTitle className="text-base">{t("onboarding.vacancyTitle")}</CardTitle>
          <CardDescription>{t("onboarding.vacancyDesc")}</CardDescription>
        </CardHeader>
        {current === 3 && (
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="vacancy">{t("vacancies.name")}</Label>
              <Input
                id="vacancy"
                value={vacancyTitle}
                placeholder="Бариста"
                onChange={(e) => setVacancyTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="vdesc">{t("vacancies.description")}</Label>
              <MarkdownField
                id="vdesc"
                rows={4}
                value={vacancyDescription}
                onChange={setVacancyDescription}
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => createVacancy.mutate()}
                disabled={!vacancyTitle.trim() || createVacancy.isPending}
              >
                {t("common.create")}
              </Button>
              <Button variant="ghost" onClick={() => navigate("/")}>
                {t("onboarding.skip")}
              </Button>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
