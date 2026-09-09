import AppBar from "@mui/material/AppBar";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha, useTheme } from "@mui/material/styles";
import {
  Bot,
  BriefcaseBusiness,
  Building2,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Newspaper,
  Settings,
  ShieldCheck,
  Sun,
  WalletCards,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { BrandLogo } from "@/components/brand-logo";
import { LANGUAGES, setLanguage } from "@/lib/i18n";
import type { Me } from "@/lib/types";
import { useAuth } from "@/store/auth";
import { useColorMode } from "@/theme";

const DRAWER_WIDTH = 280;

const PRIMARY_NAV = [
  { to: "/", key: "dashboard", icon: LayoutDashboard, end: true },
  { to: "/applications", key: "applications", icon: Inbox },
  { to: "/vacancies", key: "vacancies", icon: BriefcaseBusiness },
  { to: "/bot-builder", key: "builder", icon: Bot },
  { to: "/branches", key: "branches", icon: Building2 },
] as const;

const SECONDARY_NAV = [
  { to: "/news", key: "news", icon: Newspaper },
  { to: "/settings", key: "settings", icon: Settings },
] as const;

const money = new Intl.NumberFormat("uz-UZ");

function isPathActive(pathname: string, to: string, end?: boolean) {
  if (end) return pathname === to;
  return pathname === to || pathname.startsWith(`${to}/`);
}

function NavItems({
  items,
  onNavigate,
}: {
  items: readonly {
    to: string;
    key: string;
    icon: LucideIcon;
    end?: boolean;
  }[];
  onNavigate: () => void;
}) {
  const { t } = useTranslation();
  const { pathname } = useLocation();

  return (
    <List disablePadding sx={{ px: 2 }}>
      {items.map(({ to, key, icon: Icon, end }) => {
        const selected = isPathActive(pathname, to, end);
        return (
          <ListItemButton
            key={to}
            component={Link}
            to={to}
            aria-current={selected ? "page" : undefined}
            selected={selected}
            onClick={onNavigate}
            sx={{
              minHeight: 46,
              mb: 0.5,
              px: 1.5,
              borderRadius: 1,
              color: selected ? "primary.main" : "text.secondary",
              "&.Mui-selected": {
                color: "primary.main",
                bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                "&:hover": { bgcolor: (theme) => alpha(theme.palette.primary.main, 0.16) },
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 38, color: "inherit" }}>
              <Icon size={20} />
            </ListItemIcon>
            <ListItemText
              primary={t(`nav.${key}`, { defaultValue: key === "builder" ? "Конструктор" : key })}
              primaryTypographyProps={{ variant: "body2", fontWeight: selected ? 700 : 600 }}
            />
          </ListItemButton>
        );
      })}
    </List>
  );
}

export function AppLayout({ me, children }: { me: Me; children: React.ReactNode }) {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const { mode, toggleMode } = useColorMode();
  const navigate = useNavigate();
  const logout = useAuth((state) => state.logout);
  const [mobileOpen, setMobileOpen] = useState(false);
  const company = me.companies[0];
  const themeActionLabel = mode === "dark"
    ? t("common.lightTheme", { defaultValue: "Светлая тема" })
    : t("common.darkTheme", { defaultValue: "Тёмная тема" });

  const closeMobileNav = () => setMobileOpen(false);

  const drawerContent = (
    <Stack sx={{ height: "100%" }}>
      <Toolbar sx={{ minHeight: "80px !important", px: 3.5 }}>
        <Link to="/" onClick={closeMobileNav} aria-label="talento" style={{ textDecoration: "none" }}>
          <BrandLogo />
        </Link>
      </Toolbar>

      <Box sx={{ px: 3, pb: 2 }}>
        <Typography variant="caption" color="text.secondary" noWrap>
          {t("settings.tabCompany")}
        </Typography>
        <Typography variant="subtitle2" noWrap sx={{ mt: 0.25 }}>
          {company?.name}
        </Typography>
      </Box>

      <Typography variant="overline" color="text.disabled" sx={{ px: 3.5, pt: 1, pb: 1 }}>
        {t("nav.workspace", { defaultValue: "Рабочее пространство" })}
      </Typography>
      <NavItems items={PRIMARY_NAV} onNavigate={closeMobileNav} />

      <Typography variant="overline" color="text.disabled" sx={{ px: 3.5, pt: 3, pb: 1 }}>
        {t("nav.management", { defaultValue: "Управление" })}
      </Typography>
      <NavItems items={SECONDARY_NAV} onNavigate={closeMobileNav} />

      {me.user.is_platform_admin && (
        <List disablePadding sx={{ px: 2, mt: 0.5 }}>
          <ListItemButton
            component={Link}
            to="/admin"
            onClick={closeMobileNav}
            sx={{ minHeight: 46, px: 1.5, borderRadius: 1, color: "primary.main" }}
          >
            <ListItemIcon sx={{ minWidth: 38, color: "inherit" }}>
              <ShieldCheck size={20} />
            </ListItemIcon>
            <ListItemText
              primary="Platform admin"
              primaryTypographyProps={{ variant: "body2", fontWeight: 700 }}
            />
          </ListItemButton>
        </List>
      )}

      <Box sx={{ flexGrow: 1 }} />

      {company && me.role === "owner" && (
        <Box sx={{ px: 2, pb: 1 }}>
          <Box
            component={Link}
            to="/billing"
            onClick={closeMobileNav}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              p: 1.5,
              color: "text.primary",
              textDecoration: "none",
              borderRadius: 1.5,
              bgcolor: (value) => alpha(value.palette.primary.main, 0.08),
              border: (value) => `1px solid ${alpha(value.palette.primary.main, 0.18)}`,
              transition: theme.transitions.create(["background-color", "box-shadow"]),
              "&:hover": {
                bgcolor: (value) => alpha(value.palette.primary.main, 0.14),
                boxShadow: `0 8px 20px ${alpha(theme.palette.primary.main, 0.1)}`,
              },
            }}
          >
            <Avatar sx={{ width: 40, height: 40, bgcolor: "primary.main" }}>
              <WalletCards size={20} />
            </Avatar>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="caption" color="primary.main" fontWeight={700}>
                {t("billing.balance")}
              </Typography>
              <Typography variant="subtitle2" noWrap sx={{ fontVariantNumeric: "tabular-nums" }}>
                {company.billing_mode === "unlimited"
                  ? t("billing.unlimited")
                  : `${money.format(company.balance_uzs)} UZS`}
              </Typography>
            </Box>
          </Box>
        </Box>
      )}

      <Divider sx={{ borderStyle: "dashed" }} />

      <Box sx={{ p: 2 }}>
        <Stack direction="row" spacing={0.5} sx={{ mb: 1.5 }}>
          {LANGUAGES.map((language) => (
            <Button
              key={language.code}
              size="small"
              variant={i18n.language === language.code ? "contained" : "text"}
              onClick={() => setLanguage(language.code)}
              sx={{ flex: 1, minWidth: 0 }}
            >
              {language.code.toUpperCase()}
            </Button>
          ))}
        </Stack>

        <Stack direction="row" alignItems="center" spacing={1.25}>
          <Avatar
            sx={{ width: 38, height: 38, bgcolor: "primary.main", fontSize: 15, fontWeight: 700 }}
          >
            {me.user.full_name.trim().slice(0, 1).toUpperCase()}
          </Avatar>
          <Box sx={{ minWidth: 0, flexGrow: 1 }}>
            <Typography variant="subtitle2" noWrap>{me.user.full_name}</Typography>
            <Typography variant="caption" color="text.secondary" noWrap display="block">
              {me.user.email}
            </Typography>
          </Box>
          <Tooltip title={themeActionLabel}>
            <IconButton size="small" onClick={toggleMode} aria-label={themeActionLabel}>
              {mode === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </IconButton>
          </Tooltip>
          <Tooltip title={t("nav.logout")}>
            <IconButton
              size="small"
              aria-label={t("nav.logout")}
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <LogOut size={18} />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>
    </Stack>
  );

  return (
    <Box sx={{ display: { lg: "flex" }, minHeight: "100dvh" }}>
      <Box component="nav" sx={{ width: { lg: DRAWER_WIDTH }, flexShrink: { lg: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={closeMobileNav}
          ModalProps={{ keepMounted: true }}
          PaperProps={{ sx: { width: DRAWER_WIDTH } }}
          sx={{ display: { xs: "block", lg: "none" } }}
        >
          {drawerContent}
        </Drawer>
        <Drawer
          variant="permanent"
          open
          PaperProps={{
            sx: {
              width: DRAWER_WIDTH,
              borderRight: `1px dashed ${theme.palette.divider}`,
              bgcolor: "background.paper",
            },
          }}
          sx={{ display: { xs: "none", lg: "block" } }}
        >
          {drawerContent}
        </Drawer>
      </Box>

      <AppBar
        elevation={0}
        color="transparent"
        sx={{
          width: { lg: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { lg: `${DRAWER_WIDTH}px` },
          borderBottom: { xs: `1px dashed ${theme.palette.divider}`, lg: 0 },
          bgcolor: alpha(theme.palette.background.default, 0.88),
          backdropFilter: "blur(12px)",
        }}
      >
        <Toolbar
          sx={{
            minHeight: { xs: "64px !important", lg: "80px !important" },
            px: { xs: 2, lg: 5 },
          }}
        >
          <IconButton
            onClick={() => setMobileOpen(true)}
            aria-label={t("common.openMenu", { defaultValue: "Открыть меню" })}
            sx={{ display: { lg: "none" }, mr: 1 }}
          >
            <Menu size={22} />
          </IconButton>
          <Box sx={{ display: { xs: "block", lg: "none" } }}><BrandLogo /></Box>
          <Box sx={{ flexGrow: 1 }} />
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ display: { xs: "none", sm: "block" }, mr: 1 }}
          >
            {company?.name}
          </Typography>
          <Tooltip title={themeActionLabel}>
            <IconButton onClick={toggleMode} aria-label={themeActionLabel}>
              {mode === "dark" ? <Sun size={20} /> : <Moon size={20} />}
            </IconButton>
          </Tooltip>
          <Avatar
            sx={{ ml: 1, width: 38, height: 38, bgcolor: "primary.main", fontSize: 14, fontWeight: 700 }}
          >
            {me.user.full_name.trim().slice(0, 1).toUpperCase()}
          </Avatar>
        </Toolbar>
      </AppBar>

      <Box
        component="main"
        id="main-content"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          width: { lg: `calc(100% - ${DRAWER_WIDTH}px)` },
          pt: { xs: 10, lg: 12 },
          pb: { xs: 5, lg: 8 },
          px: { xs: 2, sm: 3, lg: 5 },
        }}
      >
        <Box sx={{ width: "100%", maxWidth: 1440, mx: "auto" }}>{children}</Box>
      </Box>
    </Box>
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
    <Stack
      direction={{ xs: "column", sm: "row" }}
      alignItems={{ xs: "stretch", sm: "flex-start" }}
      justifyContent="space-between"
      spacing={2}
      sx={{ mb: { xs: 3, md: 5 } }}
    >
      <Box>
        <Typography component="h1" variant="h4">{title}</Typography>
        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, maxWidth: 720 }}>
            {description}
          </Typography>
        )}
      </Box>
      {action && <Box sx={{ flexShrink: 0 }}>{action}</Box>}
    </Stack>
  );
}
