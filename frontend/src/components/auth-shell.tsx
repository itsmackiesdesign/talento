import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Stack from "@mui/material/Stack";
import TextField, { type TextFieldProps } from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import useMediaQuery from "@mui/material/useMediaQuery";
import { alpha, useTheme } from "@mui/material/styles";
import { Bot, Eye, EyeOff, Moon, ShieldCheck, Sun } from "lucide-react";
import { forwardRef, lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { FocusEvent, FormEvent, PointerEvent } from "react";
import { useTranslation } from "react-i18next";

import { BrandLogo, TalentoMark } from "@/components/brand-logo";
import type { AuthSceneSignals, AuthVisualState } from "@/components/auth-scene-types";
import { useColorMode } from "@/theme";

const AuthScene = lazy(async () => {
  // @ts-expect-error This visual-only JSX module is intentionally excluded from the application type graph.
  return import("@/components/auth-scene.jsx");
});

type RenderPath = "checking" | "live" | "fallback";

function AuthSceneLoader() {
  return (
    <Stack
      aria-hidden
      alignItems="center"
      justifyContent="center"
      spacing={1.5}
      sx={{ position: "absolute", inset: 0, color: alpha("#FFFFFF", 0.84) }}
    >
      <Box
        sx={{
          animation: "authLoader 1.4s ease-in-out infinite",
          "@keyframes authLoader": {
            "0%, 100%": { opacity: 0.32, transform: "scale(0.94)" },
            "50%": { opacity: 0.8, transform: "scale(1)" },
          },
          "@media (prefers-reduced-motion: reduce)": { animation: "none", opacity: 0.56 },
        }}
      >
        <TalentoMark color="currentColor" size={86} />
      </Box>
      <Typography variant="overline" sx={{ color: "inherit", letterSpacing: 2.2 }}>
        talento
      </Typography>
    </Stack>
  );
}

export function AuthShell({
  title,
  subtitle,
  children,
  feedbackState = "idle",
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  feedbackState?: Exclude<AuthVisualState, "typing">;
}) {
  const { t } = useTranslation();
  const { mode, toggleMode } = useColorMode();
  const theme = useTheme();
  const desktopScene = useMediaQuery(theme.breakpoints.up("lg"), { noSsr: true });
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)", { noSsr: true });
  const [fieldActive, setFieldActive] = useState(false);
  const [renderPath, setRenderPath] = useState<RenderPath>("checking");
  const [sceneReady, setSceneReady] = useState(false);
  const pointer = useRef({ x: 0, y: 0 });
  const lastInputAt = useRef(-10_000);
  const signals = useMemo<AuthSceneSignals>(() => ({ pointer, lastInputAt }), []);
  const visualState: AuthVisualState = feedbackState === "idle" && fieldActive ? "typing" : feedbackState;

  useEffect(() => {
    setSceneReady(false);
    if (!desktopScene) {
      setRenderPath("fallback");
      return;
    }
    if (reducedMotion) {
      console.info("[talento auth] static fallback: reduced-motion");
      setRenderPath("fallback");
      return;
    }
    try {
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
      if (!context) {
        console.info("[talento auth] static fallback: webgl-unavailable");
        setRenderPath("fallback");
        return;
      }
      setRenderPath("live");
    } catch {
      console.info("[talento auth] static fallback: webgl-check-failed");
      setRenderPath("fallback");
    }
  }, [desktopScene, reducedMotion]);

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    pointer.current.x = Math.min(1, Math.max(-1, ((event.clientX - bounds.left) / bounds.width) * 2 - 1));
    pointer.current.y = Math.min(1, Math.max(-1, -(((event.clientY - bounds.top) / bounds.height) * 2 - 1)));
  };

  const handleFocus = () => setFieldActive(true);
  const handleBlur = (event: FocusEvent<HTMLElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFieldActive(false);
  };
  const handleInput = (_event: FormEvent<HTMLElement>) => {
    lastInputAt.current = performance.now();
  };

  return (
    <Box
      data-auth-visual-state={visualState}
      onPointerMove={handlePointerMove}
      sx={{
        minHeight: "100dvh",
        display: "grid",
        gridTemplateColumns: { xs: "1fr", lg: "minmax(500px, 0.98fr) minmax(520px, 1.02fr)" },
        bgcolor: "background.paper",
      }}
    >
      <Box
        component="section"
        data-render-path={renderPath}
        data-scene-ready={sceneReady}
        aria-label={t("auth.visualLabel", { defaultValue: "Интерактивный знак talento" })}
        sx={{
          display: { xs: "none", lg: "flex" },
          position: "relative",
          isolation: "isolate",
          minHeight: "100dvh",
          flexDirection: "column",
          overflow: "hidden",
          p: { lg: 5, xl: 6 },
          color: "common.white",
          background: "linear-gradient(148deg, #100D78 0%, #2520D8 48%, #4742FF 100%)",
        }}
      >
        <Box
          aria-hidden
          sx={{
            position: "absolute",
            inset: 0,
            zIndex: -3,
            opacity: 0.4,
            backgroundImage: [
              `radial-gradient(circle at 18% 10%, ${alpha("#FFFFFF", 0.36)} 0, transparent 25%)`,
              `radial-gradient(circle at 78% 62%, ${alpha("#9F9CFF", 0.62)} 0, transparent 34%)`,
              `linear-gradient(${alpha("#FFFFFF", 0.075)} 1px, transparent 1px)`,
              `linear-gradient(90deg, ${alpha("#FFFFFF", 0.075)} 1px, transparent 1px)`,
            ].join(","),
            backgroundSize: "auto, auto, 52px 52px, 52px 52px",
          }}
        />
        <Box
          aria-hidden
          sx={{
            position: "absolute",
            inset: 0,
            zIndex: -2,
            opacity: 0.2,
            background: "url('/assets/media/talento-human-frames.webp') center / cover no-repeat",
            filter: "saturate(.55) contrast(1.1)",
            maskImage: "linear-gradient(90deg, transparent 0%, #000 12%, #000 88%, transparent 100%)",
          }}
        />
        <Box
          aria-hidden
          sx={{
            position: "absolute",
            inset: 0,
            zIndex: -1,
            opacity: visualState === "error" ? 1 : 0,
            transition: visualState === "error"
              ? "opacity 130ms cubic-bezier(.2,.8,.2,1)"
              : "opacity 1700ms cubic-bezier(.16,1,.3,1)",
            background: "radial-gradient(circle at 62% 38%, rgba(255,76,91,.76) 0, rgba(138,13,35,.72) 34%, rgba(45,6,29,.24) 76%), linear-gradient(145deg, #4D0716, #A50D2A 55%, #3F174B)",
          }}
        />

        <Box sx={{ position: "relative", zIndex: 3 }}><BrandLogo inverse /></Box>

        <Box
          aria-hidden
          sx={{
            position: "absolute",
            inset: { lg: "46px 0 156px", xl: "52px 0 166px" },
            zIndex: 0,
            background: "radial-gradient(ellipse 84% 74% at 50% 42%, rgba(5, 5, 7, 0.5) 0%, rgba(5, 5, 7, 0.22) 48%, rgba(5, 5, 7, 0) 82%)",
          }}
        >
          <Box
            sx={{
              position: "absolute",
              inset: "5% 4%",
              display: "grid",
              placeItems: "center",
              opacity: renderPath === "live" && sceneReady ? 0 : 0.17,
              transform: visualState === "success" ? "translateY(-18px) scale(1.08)" : "none",
              transition: "opacity 420ms ease, transform 700ms cubic-bezier(.16,1,.3,1)",
            }}
          >
            <TalentoMark color="#FFFFFF" size="min(42vw, 360px)" />
          </Box>
          {renderPath === "live" && (
            <Suspense fallback={<AuthSceneLoader />}>
              <AuthScene visualState={visualState} signals={signals} onReady={() => setSceneReady(true)} />
            </Suspense>
          )}
        </Box>

        <Stack
          spacing={2.2}
          sx={{
            position: "relative",
            zIndex: 2,
            mt: "auto",
            mb: 3.5,
            maxWidth: 560,
            opacity: visualState === "success" ? 0.26 : 1,
            transform: visualState === "success" ? "translateY(10px)" : "none",
            transition: "opacity 420ms ease, transform 620ms cubic-bezier(.16,1,.3,1)",
          }}
        >
          <Chip
            label={t("auth.heroBadge", { defaultValue: "Telegram-first hiring" })}
            sx={{
              alignSelf: "flex-start",
              color: "common.white",
              bgcolor: alpha("#FFFFFF", 0.12),
              border: `1px solid ${alpha("#FFFFFF", 0.18)}`,
              backdropFilter: "blur(10px)",
            }}
          />
          <Typography variant="h2" sx={{ maxWidth: 520, fontSize: { lg: 38, xl: 46 }, letterSpacing: -1.2 }}>
            {t("auth.heroTitle", { defaultValue: "От первого сообщения до первого рабочего дня" })}
          </Typography>
          <Typography sx={{ maxWidth: 510, color: alpha("#FFFFFF", 0.74), fontSize: 17, lineHeight: 1.62 }}>
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
                sx={{ px: 1.5, py: 1, borderRadius: 1.25, bgcolor: alpha("#050507", 0.2), backdropFilter: "blur(8px)" }}
              >
                <Icon size={18} />
                <Typography variant="body2" fontWeight={700}>{label}</Typography>
              </Stack>
            ))}
          </Stack>
        </Stack>

        <Typography variant="caption" sx={{ position: "relative", zIndex: 2, color: alpha("#FFFFFF", 0.58) }}>
          © {new Date().getFullYear()} talento
        </Typography>
      </Box>

      <Box
        component="main"
        onFocusCapture={handleFocus}
        onBlurCapture={handleBlur}
        onInputCapture={handleInput}
        sx={{
          position: "relative",
          display: "grid",
          placeItems: "center",
          overflow: "hidden",
          p: { xs: 2, sm: 4, lg: 8 },
        }}
      >
        <Box
          aria-hidden
          sx={{
            position: "absolute",
            width: 420,
            height: 420,
            left: -300,
            top: "50%",
            transform: "translateY(-50%)",
            borderRadius: "50%",
            opacity: visualState === "typing" ? 0.22 : visualState === "error" ? 0.16 : 0,
            filter: "blur(70px)",
            bgcolor: visualState === "error" ? "error.main" : "primary.main",
            transition: "opacity 500ms ease, background-color 300ms ease",
          }}
        />
        <Tooltip
          title={mode === "dark"
            ? t("common.lightTheme", { defaultValue: "Светлая тема" })
            : t("common.darkTheme", { defaultValue: "Тёмная тема" })}
        >
          <IconButton
            onClick={toggleMode}
            aria-label={t("common.changeTheme", { defaultValue: "Изменить тему" })}
            sx={{ position: "absolute", zIndex: 2, top: { xs: 16, sm: 24 }, right: { xs: 16, sm: 24 } }}
          >
            {mode === "dark" ? <Sun size={20} /> : <Moon size={20} />}
          </IconButton>
        </Tooltip>

        <Stack spacing={4} sx={{ position: "relative", zIndex: 1, width: "100%", maxWidth: 420 }}>
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
