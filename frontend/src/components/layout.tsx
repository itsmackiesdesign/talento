import {
  Building2,
  Briefcase,
  Inbox,
  LayoutDashboard,
  Newspaper,
  LogOut,
  Menu,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
  WalletCards,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { LANGUAGES, setLanguage } from "@/lib/i18n";
import type { Me } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAuth } from "@/store/auth";

function useTheme() {
  const [dark, setDark] = useState(
    () => localStorage.getItem("talento-theme") !== "light",
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("talento-theme", dark ? "dark" : "light");
  }, [dark]);
  return { dark, toggle: () => setDark((d) => !d) };
}

const NAV = [
  { to: "/", key: "dashboard", icon: LayoutDashboard, end: true },
  { to: "/vacancies", key: "vacancies", icon: Briefcase, end: false },
  { to: "/branches", key: "branches", icon: Building2, end: false },
  { to: "/news", key: "news", icon: Newspaper, end: false },
  { to: "/applications", key: "applications", icon: Inbox, end: false },
  { to: "/settings", key: "settings", icon: Settings, end: false },
] as const;

const money = new Intl.NumberFormat("uz-UZ");

export function AppLayout({ me, children }: { me: Me; children: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const { dark, toggle } = useTheme();
  const navigate = useNavigate();
  const logout = useAuth((s) => s.logout);
  const [mobileOpen, setMobileOpen] = useState(false);

  const company = me.companies[0];

  const nav = (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ to, key, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={() => setMobileOpen(false)}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )
          }
        >
          <Icon className="h-4 w-4" />
          {t(`nav.${key}`)}
        </NavLink>
      ))}
      {me.user.is_platform_admin && (
        <NavLink
          to="/admin"
          onClick={() => setMobileOpen(false)}
          className="mt-3 flex items-center gap-3 rounded-lg border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/10"
        >
          <ShieldCheck className="h-4 w-4" />
          Platform admin
        </NavLink>
      )}
    </nav>
  );

  const sidebarBody = (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-lg font-semibold tracking-tight">Talento</p>
          <p className="truncate text-xs text-muted-foreground">{company?.name}</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label={t("common.close")}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {nav}

      <div className="mt-auto space-y-3">
        {company && me.role === "owner" && (
          <NavLink
            to="/billing"
            onClick={() => setMobileOpen(false)}
            aria-label={t("billing.title")}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 rounded-xl border border-primary/40 bg-primary/10 p-3 shadow-sm transition-colors hover:bg-primary/15",
                isActive && "ring-1 ring-primary/50",
              )
            }
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/15 text-primary transition-colors group-hover:bg-primary/20">
              <WalletCards className="h-5 w-5" />
            </span>
            <span className="min-w-0">
              <span className="block text-xs font-medium text-primary">
                {t("billing.balance")}
              </span>
              <span className="mt-0.5 block truncate text-base font-semibold tabular-nums tracking-tight">
                {company.billing_mode === "unlimited"
                  ? t("billing.unlimited")
                  : `${money.format(company.balance_uzs)} UZS`}
              </span>
            </span>
          </NavLink>
        )}

        <div className="flex gap-1">
          {LANGUAGES.map((lang) => (
            <Button
              key={lang.code}
              variant={i18n.language === lang.code ? "secondary" : "ghost"}
              size="sm"
              className="flex-1 px-1 text-xs"
              onClick={() => setLanguage(lang.code)}
            >
              {lang.code.toUpperCase()}
            </Button>
          ))}
        </div>

        <div className="flex items-center justify-between rounded-lg border p-2">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium">{me.user.full_name}</p>
            <p className="truncate text-xs text-muted-foreground">{me.user.email}</p>
          </div>
          <div className="flex shrink-0">
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="Theme">
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("nav.logout")}
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
      <aside className="sticky top-0 hidden h-screen border-r lg:block">{sidebarBody}</aside>

      {/* Mobile: the same sidebar as an overlay drawer. */}
      {mobileOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/60 lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="fixed inset-y-0 left-0 z-50 w-64 border-r bg-background lg:hidden">
            {sidebarBody}
          </aside>
        </>
      )}

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur lg:hidden">
          <Button variant="ghost" size="icon" onClick={() => setMobileOpen(true)} aria-label="Menu">
            <Menu className="h-5 w-5" />
          </Button>
          <span className="font-semibold">Talento</span>
        </header>

        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}
