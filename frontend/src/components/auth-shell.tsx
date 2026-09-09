import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Stack from "@mui/material/Stack";
import TextField, { type TextFieldProps } from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha } from "@mui/material/styles";
import { Bot, Eye, EyeOff, Moon, ShieldCheck, Sparkles, Sun } from "lucide-react";
import { forwardRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { BrandLogo } from "@/components/brand-logo";
import { useColorMode } from "@/theme";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();
  const { mode, toggleMode } = useColorMode();

  return (
    <Box
      sx={{
        minHeight: "100dvh",
        display: "grid",
        gridTemplateColumns: { xs: "1fr", lg: "minmax(440px, 0.92fr) minmax(520px, 1.08fr)" },
        bgcolor: "background.paper",
      }}
    >
      <Box
        component="section"
        sx={{
          display: { xs: "none", lg: "flex" },
          position: "relative",
          isolation: "isolate",
          minHeight: "100dvh",
          flexDirection: "column",
          overflow: "hidden",
          p: 6,
          color: "common.white",
          background: "linear-gradient(145deg, #15118F 0%, #2F2BFF 52%, #5B57FF 100%)",
        }}
      >
        <Box
          aria-hidden
          sx={{
            position: "absolute",
            inset: 0,
            zIndex: -1,
            opacity: 0.34,
            backgroundImage: [
              `radial-gradient(circle at 18% 12%, ${alpha("#FFFFFF", 0.55)} 0, transparent 24%)`,
              `radial-gradient(circle at 82% 88%, ${alpha("#9F9CFF", 0.8)} 0, transparent 31%)`,
              `linear-gradient(${alpha("#FFFFFF", 0.08)} 1px, transparent 1px)`,
              `linear-gradient(90deg, ${alpha("#FFFFFF", 0.08)} 1px, transparent 1px)`,
            ].join(","),
            backgroundSize: "auto, auto, 48px 48px, 48px 48px",
          }}
        />

        <BrandLogo inverse />

        <Stack spacing={3} sx={{ my: "auto", maxWidth: 560 }}>
          <Chip
            icon={<Sparkles size={16} />}
            label={t("auth.heroBadge", { defaultValue: "Telegram-first hiring" })}
            sx={{
              alignSelf: "flex-start",
              color: "common.white",
              bgcolor: alpha("#FFFFFF", 0.13),
              border: `1px solid ${alpha("#FFFFFF", 0.18)}`,
              "& .MuiChip-icon": { color: "inherit" },
            }}
          />
          <Typography variant="h2" sx={{ maxWidth: 520, fontSize: { lg: 46, xl: 56 } }}>
            {t("auth.heroTitle", { defaultValue: "От первого сообщения до первого рабочего дня" })}
          </Typography>
          <Typography sx={{ maxWidth: 500, color: alpha("#FFFFFF", 0.72), fontSize: 18, lineHeight: 1.65 }}>
            {t("auth.heroSubtitle", {
              defaultValue: "Соберите путь кандидата в Telegram, управляйте воронкой и не теряйте сильных людей между этапами.",
            })}
          </Typography>

          <Stack direction="row" spacing={1.25} flexWrap="wrap" useFlexGap>
            {[
              { icon: Bot, label: t("auth.heroAutomation", { defaultValue: "Автоматизация 24/7" }) },
              { icon: ShieldCheck, label: t("auth.heroControl", { defaultValue: "Контроль HR-команды" }) },
            ].map(({ icon: Icon, label }) => (
              <Stack
                key={label}
                direction="row"
                alignItems="center"
                spacing={1}
                sx={{ px: 1.5, py: 1, borderRadius: 1.25, bgcolor: alpha("#050507", 0.18) }}
              >
                <Icon size={18} />
                <Typography variant="body2" fontWeight={700}>{label}</Typography>
              </Stack>
            ))}
          </Stack>
        </Stack>

        <Typography variant="caption" sx={{ color: alpha("#FFFFFF", 0.6) }}>
          © {new Date().getFullYear()} talento
        </Typography>
      </Box>

      <Box component="main" sx={{ position: "relative", display: "grid", placeItems: "center", p: { xs: 2, sm: 4, lg: 8 } }}>
        <Tooltip
          title={mode === "dark"
            ? t("common.lightTheme", { defaultValue: "Светлая тема" })
            : t("common.darkTheme", { defaultValue: "Тёмная тема" })}
        >
          <IconButton
            onClick={toggleMode}
            aria-label={t("common.changeTheme", { defaultValue: "Изменить тему" })}
            sx={{ position: "absolute", top: { xs: 16, sm: 24 }, right: { xs: 16, sm: 24 } }}
          >
            {mode === "dark" ? <Sun size={20} /> : <Moon size={20} />}
          </IconButton>
        </Tooltip>

        <Stack spacing={4} sx={{ width: "100%", maxWidth: 420 }}>
          <Box sx={{ display: { lg: "none" } }}><BrandLogo /></Box>
          <Box>
            <Typography component="h1" variant="h3">{title}</Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>{subtitle}</Typography>
          </Box>
          {children}
        </Stack>
      </Box>
    </Box>
  );
}

export const PasswordTextField = forwardRef<HTMLInputElement, Omit<TextFieldProps, "type">>(function PasswordTextField(
  { InputProps, ...props },
  ref,
) {
  const [visible, setVisible] = useState(false);

  return (
    <TextField
      {...props}
      inputRef={ref}
      type={visible ? "text" : "password"}
      InputProps={{
        ...InputProps,
        endAdornment: (
          <InputAdornment position="end">
            <IconButton
              edge="end"
              onClick={() => setVisible((current) => !current)}
              aria-label={visible ? "Hide password" : "Show password"}
            >
              {visible ? <EyeOff size={20} /> : <Eye size={20} />}
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
});
