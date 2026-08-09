import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bot,
  Building2,
  Check,
  ChevronDown,
  Clock3,
  FileText,
  Globe2,
  Inbox,
  LayoutGrid,
  MapPin,
  MessageCircle,
  Newspaper,
  PenLine,
  Phone,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { LANGUAGES, setLanguage } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import "./landing.css";

function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={cn("tl-reveal", visible && "is-visible", className)}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

function LangSwitch({ className }: { className?: string }) {
  const { i18n } = useTranslation();
  return (
    <div className={cn("tl-font-mono flex items-center gap-1 text-xs", className)}>
      {LANGUAGES.map((lang) => (
        <button
          key={lang.code}
          onClick={() => setLanguage(lang.code)}
          className={cn(
            "rounded-full px-2.5 py-1 uppercase tracking-wide transition-colors",
            i18n.language === lang.code
              ? "bg-[var(--tl-cyan)] text-[var(--tl-cyan-ink)]"
              : "text-[var(--tl-muted)] hover:text-[var(--tl-text)]",
          )}
        >
          {lang.code}
        </button>
      ))}
    </div>
  );
}

function NavBar() {
  const { t } = useTranslation();
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-[var(--tl-bg)]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-8">
        <a href="#hero" className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--tl-cyan)] to-[var(--tl-lime)] tl-font-mono text-sm font-bold text-[var(--tl-cyan-ink)]">
            T
          </span>
          <span className="tl-font-display text-lg font-semibold tracking-tight">Talento</span>
        </a>

        <nav className="tl-font-mono hidden items-center gap-7 text-[13px] uppercase tracking-wide text-[var(--tl-muted)] md:flex">
          <a href="#features" className="transition-colors hover:text-[var(--tl-text)]">
            {t("landing.nav.features")}
          </a>
          <a href="#how" className="transition-colors hover:text-[var(--tl-text)]">
            {t("landing.nav.how")}
          </a>
          <a href="#showcase" className="transition-colors hover:text-[var(--tl-text)]">
            {t("landing.nav.showcase")}
          </a>
          <a href="#faq" className="transition-colors hover:text-[var(--tl-text)]">
            {t("landing.nav.faq")}
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <LangSwitch className="hidden sm:flex" />
          <Link
            to="/login"
            className="hidden text-sm font-medium text-[var(--tl-muted)] transition-colors hover:text-[var(--tl-text)] sm:inline-block"
          >
            {t("landing.nav.login")}
          </Link>
          <Link
            to="/register"
            className="group inline-flex items-center gap-1.5 rounded-full bg-[var(--tl-lime)] px-4 py-2 text-sm font-semibold text-[var(--tl-lime-ink)] transition-transform hover:scale-[1.03] active:scale-[0.98]"
          >
            {t("landing.nav.start")}
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </header>
  );
}

function PhoneMock() {
  const { t } = useTranslation();
  return (
    <div className="relative">
      <div
        aria-hidden
        className="tl-card tl-float absolute -left-8 -top-6 z-0 hidden w-52 rounded-2xl p-3 sm:block"
        style={{ animationDelay: "0.4s" }}
      >
        <p className="tl-font-mono mb-2 text-[10px] uppercase tracking-wide text-[var(--tl-muted)]">
          {t("landing.showcase.tabKanban")}
        </p>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--tl-lime)]" />
            <span className="text-xs">Азиз К.</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--tl-cyan)]" />
            <span className="text-xs">Малика Ю.</span>
          </div>
        </div>
      </div>

      <div className="tl-phone tl-float-slow relative z-10 mx-auto w-[300px] px-4 pb-5 pt-4 sm:w-[320px]">
        <div className="mb-3 flex items-center gap-2.5 border-b border-white/10 pb-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[var(--tl-cyan)] to-[var(--tl-lime)]">
            <Bot className="h-4.5 w-4.5 text-[var(--tl-cyan-ink)]" />
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight">{t("landing.hero.botName")}</p>
            <p className="flex items-center gap-1.5 text-[11px] text-[var(--tl-muted)]">
              <span className="tl-pulse h-1.5 w-1.5 rounded-full bg-[var(--tl-lime)]" />
              {t("landing.hero.botStatus")}
            </p>
          </div>
        </div>

        <div className="space-y-2.5">
          <div className="tl-bubble-bot max-w-[85%] px-3 py-2 text-[13px] leading-snug">
            {t("landing.hero.welcomeMsg")}
          </div>

          <div className="tl-bubble-bot max-w-[92%] overflow-hidden">
            <div className="h-16 bg-gradient-to-br from-[var(--tl-cyan-dim)] via-transparent to-[rgba(215,255,94,0.12)]" />
            <div className="space-y-1.5 px-3 py-2.5">
              <p className="text-[13px] font-semibold">{t("landing.hero.vacancyTitle")}</p>
              <p className="tl-font-mono text-[11px] text-[var(--tl-lime)]">
                {t("landing.hero.vacancyPay")}
              </p>
              <p className="flex items-center gap-1 text-[11px] text-[var(--tl-muted)]">
                <MapPin className="h-3 w-3" /> {t("landing.hero.vacancyBranch")}
              </p>
              <button className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--tl-cyan)] py-1.5 text-[12px] font-semibold text-[var(--tl-cyan-ink)]">
                <Send className="h-3 w-3" />
                {t("landing.hero.applyBtn")}
              </button>
            </div>
          </div>

          <div className="tl-bubble-bot flex w-fit items-center gap-1.5 px-3 py-2.5">
            <span className="tl-dot" />
            <span className="tl-dot" />
            <span className="tl-dot" />
          </div>
        </div>
      </div>
    </div>
  );
}

function Hero() {
  const { t } = useTranslation();
  return (
    <section id="hero" className="relative overflow-hidden pb-20 pt-14 sm:pb-28 sm:pt-20">
      <div aria-hidden className="tl-glow pointer-events-none absolute inset-0 -z-10" />
      <div className="mx-auto grid max-w-7xl items-center gap-16 px-6 lg:grid-cols-[1.1fr_0.9fr] lg:gap-10 lg:px-8">
        <div>
          <div className="tl-anim-in tl-font-mono mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--tl-muted)]">
            <Sparkles className="h-3 w-3 text-[var(--tl-lime)]" />
            {t("landing.hero.badge")}
          </div>

          <h1 className="tl-anim-in tl-delay-1 tl-font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
            {t("landing.hero.titleLine1")}
            <br />
            <span className="tl-text-gradient italic">{t("landing.hero.titleLine2")}</span>
          </h1>

          <p className="tl-anim-in tl-delay-2 mt-6 max-w-lg text-lg leading-relaxed text-[var(--tl-muted)]">
            {t("landing.hero.subtitle")}
          </p>

          <div className="tl-anim-in tl-delay-3 mt-8 flex flex-wrap items-center gap-4">
            <Link
              to="/register"
              className="group inline-flex items-center gap-2 rounded-full bg-[var(--tl-lime)] px-6 py-3 text-sm font-semibold text-[var(--tl-lime-ink)] transition-transform hover:scale-[1.03] active:scale-[0.98]"
            >
              {t("landing.hero.ctaPrimary")}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#how"
              className="group inline-flex items-center gap-2 rounded-full border border-white/15 px-6 py-3 text-sm font-semibold text-[var(--tl-text)] transition-colors hover:border-[var(--tl-cyan)] hover:text-[var(--tl-cyan)]"
            >
              {t("landing.hero.ctaSecondary")}
              <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </a>
          </div>

          <div className="tl-anim-in tl-delay-4 mt-14 grid max-w-lg grid-cols-3 gap-6 border-t border-white/10 pt-6">
            {[
              { icon: Clock3, num: t("landing.hero.stat1Num"), label: t("landing.hero.stat1Label") },
              { icon: FileText, num: t("landing.hero.stat2Num"), label: t("landing.hero.stat2Label") },
              { icon: Globe2, num: t("landing.hero.stat3Num"), label: t("landing.hero.stat3Label") },
            ].map((s, i) => (
              <div key={i}>
                <s.icon className="mb-1.5 h-4 w-4 text-[var(--tl-cyan)]" />
                <p className="tl-font-mono text-xl font-semibold leading-tight">{s.num}</p>
                <p className="mt-0.5 text-xs leading-snug text-[var(--tl-muted-2)]">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="tl-anim-in tl-delay-3 flex justify-center lg:justify-end">
          <PhoneMock />
        </div>
      </div>
    </section>
  );
}

const STACK = ["FastAPI", "PostgreSQL 16", "Redis 7", "Celery", "aiogram", "Docker", "Caddy"];

function TrustStrip() {
  const { t } = useTranslation();
  const items = [...STACK, ...STACK];
  return (
    <section className="border-y border-white/5 py-8">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <p className="tl-font-mono mb-4 text-center text-[11px] uppercase tracking-[0.2em] text-[var(--tl-muted-2)]">
          {t("landing.trust.label")}
        </p>
      </div>
      <div className="tl-marquee-wrap tl-scrollbar-hide overflow-hidden">
        <div className="tl-marquee-track gap-3 px-3">
          {items.map((name, i) => (
            <span
              key={i}
              className="tl-font-mono flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-[var(--tl-muted)]"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--tl-cyan)]" />
              {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function SectionKicker({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="tl-font-mono mb-3 text-xs uppercase tracking-[0.2em] text-[var(--tl-cyan)]">{kicker}</p>
      <h2 className="tl-font-display text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
    </div>
  );
}

function HowItWorks() {
  const { t } = useTranslation();
  const steps = [1, 2, 3, 4].map((n) => ({
    num: t(`landing.how.step${n}Num`),
    title: t(`landing.how.step${n}Title`),
    desc: t(`landing.how.step${n}Desc`),
  }));
  return (
    <section id="how" className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <Reveal>
          <SectionKicker kicker={t("landing.how.kicker")} title={t("landing.how.title")} />
        </Reveal>

        <div className="relative mt-16 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div
            aria-hidden
            className="absolute left-0 right-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-white/15 to-transparent lg:block"
          />
          {steps.map((s, i) => (
            <Reveal key={i} delay={i * 90}>
              <div className="relative">
                <p className="tl-font-display text-5xl font-light text-white/15">{s.num}</p>
                <h3 className="tl-font-display mt-3 text-xl font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--tl-muted)]">{s.desc}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  const { t } = useTranslation();
  const items = [
    { icon: MessageCircle, n: 1, span: "sm:col-span-2 sm:row-span-2", accent: true },
    { icon: LayoutGrid, n: 2, span: "sm:col-span-2" },
    { icon: FileText, n: 3, span: "" },
    { icon: PenLine, n: 4, span: "" },
    { icon: MapPin, n: 5, span: "sm:col-span-2" },
    { icon: Globe2, n: 6, span: "", lime: true },
    { icon: BarChart3, n: 7, span: "" },
  ];
  return (
    <section id="features" className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <Reveal>
          <SectionKicker kicker={t("landing.features.kicker")} title={t("landing.features.title")} />
        </Reveal>

        <div className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-4">
          {items.map((it, i) => (
            <Reveal key={i} delay={i * 60} className={it.span}>
              <div
                className={cn(
                  "tl-card h-full rounded-2xl p-6",
                  it.accent && "bg-gradient-to-br from-[var(--tl-cyan-dim)] to-transparent",
                )}
              >
                <span
                  className={cn(
                    "mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl",
                    it.lime ? "bg-[var(--tl-lime)] text-[var(--tl-lime-ink)]" : "bg-[var(--tl-cyan-dim)] text-[var(--tl-cyan)]",
                  )}
                >
                  <it.icon className="h-5 w-5" />
                </span>
                <h3 className="tl-font-display text-lg font-semibold">{t(`landing.features.f${it.n}Title`)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--tl-muted)]">
                  {t(`landing.features.f${it.n}Desc`)}
                </p>
              </div>
            </Reveal>
          ))}

          <Reveal delay={480} className="sm:col-span-4">
            <div className="tl-card flex flex-col items-start gap-5 rounded-2xl p-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--tl-cyan-dim)] text-[var(--tl-cyan)]">
                  <ShieldCheck className="h-5 w-5" />
                </span>
                <div>
                  <h3 className="tl-font-display text-lg font-semibold">{t("landing.features.f8Title")}</h3>
                  <p className="text-sm text-[var(--tl-muted)]">{t("landing.features.f8Desc")}</p>
                </div>
              </div>
              <div className="tl-font-mono flex flex-wrap gap-2 text-[11px] text-[var(--tl-muted)]">
                {["AES-256", "bcrypt", "rate limit", "HTTPS"].map((tag) => (
                  <span key={tag} className="flex items-center gap-1 rounded-full border border-white/10 px-2.5 py-1">
                    <Check className="h-3 w-3 text-[var(--tl-lime)]" />
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

type Tab = "dashboard" | "vacancies" | "kanban" | "bot";

function DashboardMock() {
  const { t } = useTranslation();
  const bars = [40, 65, 50, 90, 70, 55, 80];
  return (
    <div className="grid gap-6 sm:grid-cols-[1fr_1.4fr]">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-1">
        {[
          { label: t("landing.showcase.dashTotal"), value: "128" },
          { label: t("landing.showcase.dashWeek"), value: "24" },
          { label: t("landing.showcase.dashActive"), value: "4" },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <p className="tl-font-mono text-2xl font-semibold text-[var(--tl-cyan)]">{s.value}</p>
            <p className="mt-1 text-xs text-[var(--tl-muted)]">{s.label}</p>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
        <p className="mb-4 text-xs text-[var(--tl-muted)]">{t("landing.showcase.dashByDay")}</p>
        <div className="flex h-32 items-end gap-3">
          {bars.map((h, i) => (
            <div
              key={i}
              className="tl-bar flex-1 rounded-t-md bg-gradient-to-t from-[var(--tl-cyan)] to-[var(--tl-lime)]"
              style={{ height: `${h}%`, animationDelay: `${i * 80}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function VacanciesMock() {
  const { t } = useTranslation();
  const rows = [
    { key: "vacBarista", pay: "4.0 – 6.0M", branch: "Чиланзар", status: "vacActive" },
    { key: "vacCashier", pay: "3.5 – 5.0M", branch: "Юнусабад", status: "vacActive" },
    { key: "vacAdmin", pay: "6.0 – 9.0M", branch: "Самарканд", status: "vacActive" },
    { key: "vacCourier", pay: "3.0 – 7.0M", branch: "Чиланзар", status: "vacDraft" },
  ];
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div
          key={r.key}
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
        >
          <div>
            <p className="text-sm font-semibold">{t(`landing.showcase.${r.key}`)}</p>
            <p className="flex items-center gap-1 text-xs text-[var(--tl-muted)]">
              <MapPin className="h-3 w-3" /> {r.branch}
            </p>
          </div>
          <p className="tl-font-mono text-xs text-[var(--tl-lime)]">{r.pay}</p>
          <span
            className={cn(
              "tl-font-mono rounded-full px-2.5 py-1 text-[10px] uppercase tracking-wide",
              r.status === "vacActive"
                ? "bg-[var(--tl-cyan-dim)] text-[var(--tl-cyan)]"
                : "bg-white/10 text-[var(--tl-muted)]",
            )}
          >
            {t(`landing.showcase.${r.status}`)}
          </span>
        </div>
      ))}
    </div>
  );
}

const KANBAN_CANDIDATES: Record<string, { name: string; color: string }[]> = {
  kanbanNew: [
    { name: "Азиз К.", color: "#35b4e8" },
    { name: "Нилуфар А.", color: "#d7ff5e" },
  ],
  kanbanInterview: [
    { name: "Дилшод Р.", color: "#ff7a59" },
    { name: "Тимур С.", color: "#35b4e8" },
  ],
  kanbanOffer: [{ name: "Севара М.", color: "#d7ff5e" }],
  kanbanHired: [{ name: "Жасур Т.", color: "#35b4e8" }],
};

function KanbanMock() {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {Object.entries(KANBAN_CANDIDATES).map(([key, people]) => (
        <div key={key} className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="tl-font-mono mb-3 text-[10px] uppercase tracking-wide text-[var(--tl-muted)]">
            {t(`landing.showcase.${key}`)}
          </p>
          <div className="space-y-2">
            {people.map((p) => (
              <div key={p.name} className="tl-kanban-card rounded-lg border border-white/10 bg-white/[0.04] p-2.5">
                <div className="flex items-center gap-2">
                  <span
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-[#04141c]"
                    style={{ background: p.color }}
                  >
                    {p.name[0]}
                  </span>
                  <span className="text-[11px] leading-tight">{p.name}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function BotMenuMock() {
  const { t } = useTranslation();
  const buttons = [
    { icon: Building2, key: "botMenuCompany" },
    { icon: MapPin, key: "botMenuBranches" },
    { icon: FileText, key: "botMenuVacancies" },
    { icon: Newspaper, key: "botMenuNews" },
    { icon: Phone, key: "botMenuContacts" },
    { icon: Inbox, key: "botMenuApplications" },
  ];
  return (
    <div className="mx-auto grid max-w-md grid-cols-2 gap-3">
      {buttons.map((b) => (
        <div
          key={b.key}
          className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3.5 text-sm"
        >
          <b.icon className="h-4 w-4 text-[var(--tl-cyan)]" />
          {t(`landing.showcase.${b.key}`)}
        </div>
      ))}
    </div>
  );
}

function Showcase() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("dashboard");
  const tabs: { id: Tab; label: string }[] = [
    { id: "dashboard", label: t("landing.showcase.tabDashboard") },
    { id: "vacancies", label: t("landing.showcase.tabVacancies") },
    { id: "kanban", label: t("landing.showcase.tabKanban") },
    { id: "bot", label: t("landing.showcase.tabBot") },
  ];
  return (
    <section id="showcase" className="py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-6 lg:px-8">
        <Reveal>
          <SectionKicker kicker={t("landing.showcase.kicker")} title={t("landing.showcase.title")} />
        </Reveal>

        <Reveal delay={120}>
          <div className="tl-font-mono mx-auto mt-10 flex w-fit flex-wrap justify-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1 text-xs">
            {tabs.map((tb) => (
              <button
                key={tb.id}
                onClick={() => setTab(tb.id)}
                className={cn(
                  "rounded-full px-4 py-2 uppercase tracking-wide transition-colors",
                  tab === tb.id
                    ? "bg-[var(--tl-cyan)] text-[var(--tl-cyan-ink)]"
                    : "text-[var(--tl-muted)] hover:text-[var(--tl-text)]",
                )}
              >
                {tb.label}
              </button>
            ))}
          </div>
        </Reveal>

        <Reveal delay={200}>
          <div className="tl-card mt-8 rounded-3xl p-6 sm:p-10">
            {tab === "dashboard" && <DashboardMock />}
            {tab === "vacancies" && <VacanciesMock />}
            {tab === "kanban" && <KanbanMock />}
            {tab === "bot" && <BotMenuMock />}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function MultilangSection() {
  const { t, i18n } = useTranslation();
  return (
    <section className="border-y border-white/5 py-24 sm:py-32">
      <div className="mx-auto max-w-4xl px-6 text-center lg:px-8">
        <Reveal>
          <p className="tl-font-mono mb-3 text-xs uppercase tracking-[0.2em] text-[var(--tl-cyan)]">
            {t("landing.multilang.kicker")}
          </p>
          <h2 className="tl-font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("landing.multilang.title")}
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-[var(--tl-muted)]">{t("landing.multilang.desc")}</p>
        </Reveal>

        <Reveal delay={150}>
          <div className="mx-auto mt-10 flex w-fit gap-2 rounded-full border border-white/10 bg-white/[0.03] p-1">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => setLanguage(lang.code)}
                className={cn(
                  "tl-font-mono rounded-full px-5 py-2 text-xs uppercase tracking-wide transition-colors",
                  i18n.language === lang.code
                    ? "bg-[var(--tl-lime)] text-[var(--tl-lime-ink)]"
                    : "text-[var(--tl-muted)] hover:text-[var(--tl-text)]",
                )}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </Reveal>

        <Reveal delay={250}>
          <div className="tl-bubble-bot mx-auto mt-8 max-w-md px-5 py-4 text-left text-sm leading-relaxed">
            {t("landing.hero.welcomeMsg")}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function FAQ() {
  const { t } = useTranslation();
  const [open, setOpen] = useState<number>(0);
  const items = [1, 2, 3, 4, 5].map((n) => ({
    q: t(`landing.faq.q${n}`),
    a: t(`landing.faq.a${n}`),
  }));

  return (
    <section id="faq" className="py-24 sm:py-32">
      <div className="mx-auto max-w-3xl px-6 lg:px-8">
        <Reveal>
          <SectionKicker kicker={t("landing.faq.kicker")} title={t("landing.faq.title")} />
        </Reveal>

        <div className="mt-12 divide-y divide-white/10 border-y border-white/10">
          {items.map((item, i) => (
            <div key={i}>
              <button
                onClick={() => setOpen(open === i ? -1 : i)}
                className="flex w-full items-center justify-between gap-4 py-5 text-left"
              >
                <span className="font-medium">{item.q}</span>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 shrink-0 text-[var(--tl-muted)] transition-transform",
                    open === i && "rotate-180 text-[var(--tl-cyan)]",
                  )}
                />
              </button>
              <div className={cn("tl-faq-panel", open === i && "tl-open")}>
                <div>
                  <p className="pb-5 text-sm leading-relaxed text-[var(--tl-muted)]">{item.a}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCTA() {
  const { t } = useTranslation();
  return (
    <section className="px-6 py-24 sm:py-32 lg:px-8">
      <Reveal>
        <div className="tl-pattern relative mx-auto max-w-5xl overflow-hidden rounded-[2.5rem] border border-white/10 bg-gradient-to-br from-[rgba(53,180,232,0.14)] via-[var(--tl-bg-alt)] to-[rgba(215,255,94,0.08)] px-8 py-16 text-center sm:px-16">
          <h2 className="tl-font-display text-4xl font-semibold tracking-tight sm:text-5xl">
            {t("landing.cta.title")}
          </h2>
          <p className="mx-auto mt-4 max-w-md text-[var(--tl-muted)]">{t("landing.cta.subtitle")}</p>
          <Link
            to="/register"
            className="group mt-8 inline-flex items-center gap-2 rounded-full bg-[var(--tl-lime)] px-7 py-3.5 text-sm font-semibold text-[var(--tl-lime-ink)] transition-transform hover:scale-[1.03] active:scale-[0.98]"
          >
            {t("landing.cta.button")}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  const { t } = useTranslation();
  return (
    <footer className="border-t border-white/5 py-14">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="flex flex-col gap-10 sm:flex-row sm:justify-between">
          <div className="max-w-xs">
            <div className="flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--tl-cyan)] to-[var(--tl-lime)] tl-font-mono text-xs font-bold text-[var(--tl-cyan-ink)]">
                T
              </span>
              <span className="tl-font-display text-base font-semibold">Talento</span>
            </div>
            <p className="mt-3 text-sm text-[var(--tl-muted)]">{t("landing.footer.tagline")}</p>
            <LangSwitch className="mt-5" />
          </div>

          <div className="flex gap-16">
            <div>
              <p className="tl-font-mono mb-3 text-[11px] uppercase tracking-wide text-[var(--tl-muted-2)]">
                {t("landing.footer.product")}
              </p>
              <ul className="space-y-2 text-sm text-[var(--tl-muted)]">
                <li>
                  <a href="#features" className="hover:text-[var(--tl-text)]">
                    {t("landing.nav.features")}
                  </a>
                </li>
                <li>
                  <a href="#how" className="hover:text-[var(--tl-text)]">
                    {t("landing.nav.how")}
                  </a>
                </li>
                <li>
                  <a href="#showcase" className="hover:text-[var(--tl-text)]">
                    {t("landing.nav.showcase")}
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <p className="tl-font-mono mb-3 text-[11px] uppercase tracking-wide text-[var(--tl-muted-2)]">
                {t("landing.footer.company")}
              </p>
              <ul className="space-y-2 text-sm text-[var(--tl-muted)]">
                <li>
                  <Link to="/login" className="hover:text-[var(--tl-text)]">
                    {t("landing.nav.login")}
                  </Link>
                </li>
                <li>
                  <a href="#faq" className="hover:text-[var(--tl-text)]">
                    {t("landing.nav.faq")}
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="tl-font-mono mt-12 flex flex-col gap-2 border-t border-white/10 pt-6 text-[11px] text-[var(--tl-muted-2)] sm:flex-row sm:justify-between">
          <span>© {new Date().getFullYear()} Talento. {t("landing.footer.rights")}</span>
          <span>FastAPI · React · Telegram Bot API</span>
        </div>
      </div>
    </footer>
  );
}

export default function LandingPage() {
  return (
    <div className="tl relative min-h-screen">
      <div aria-hidden className="tl-pattern pointer-events-none fixed inset-0 -z-10 opacity-70" />
      <NavBar />
      <main>
        <Hero />
        <TrustStrip />
        <HowItWorks />
        <Features />
        <Showcase />
        <MultilangSection />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
