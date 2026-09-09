import { zodResolver } from "@hookform/resolvers/zod";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Link from "@mui/material/Link";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link as RouterLink, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { AuthShell, PasswordTextField } from "@/components/auth-shell";
import { api } from "@/lib/api";
import { useAuth } from "@/store/auth";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

function LoginExitSkeleton() {
  return (
    <Stack spacing={2.5} aria-live="polite" aria-label="Вход выполнен. Загружаем рабочее пространство.">
      <Stack spacing={1}>
        <Skeleton variant="rounded" height={14} width="24%" />
        <Skeleton variant="rounded" height={52} />
      </Stack>
      <Stack spacing={1}>
        <Skeleton variant="rounded" height={14} width="29%" />
        <Skeleton variant="rounded" height={52} />
      </Stack>
      <Skeleton variant="rounded" height={48} />
      <Typography variant="body2" color="text.secondary" textAlign="center">
        Открываем ваше рабочее пространство…
      </Typography>
    </Stack>
  );
}

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setTokens = useAuth((state) => state.setTokens);
  const [feedbackState, setFeedbackState] = useState<"idle" | "error" | "success">("idle");
  const [authError, setAuthError] = useState<string | null>(null);
  const errorTimer = useRef<number | null>(null);
  const routeState = location.state as {
    from?: { pathname?: string; search?: string };
    email?: string;
  } | null;

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: routeState?.email ?? "", password: "" },
  });

  useEffect(() => () => {
    if (errorTimer.current !== null) window.clearTimeout(errorTimer.current);
  }, []);

  const triggerErrorFeedback = (message?: string) => {
    if (errorTimer.current !== null) window.clearTimeout(errorTimer.current);
    if (message) setAuthError(message);
    setFeedbackState("error");
    errorTimer.current = window.setTimeout(() => setFeedbackState("idle"), 880);
  };

  const mutation = useMutation({
    mutationFn: api.auth.login,
    onSuccess: async (tokens) => {
      setAuthError(null);
      setFeedbackState("success");
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const transition = new Promise<void>((resolve) => window.setTimeout(resolve, reducedMotion ? 100 : 880));
      await transition;
      setTokens(tokens.access_token, tokens.refresh_token);
      const from = routeState?.from;
      if (from?.pathname) {
        navigate(`${from.pathname}${from.search ?? ""}`);
        return;
      }
      let destination = "/";
      try {
        const me = await api.auth.me();
        destination = me.user.is_platform_admin ? "/admin" : "/";
      } catch { /* The authenticated home remains a safe fallback. */ }
      navigate(destination);
    },
    onError: (error: Error) => triggerErrorFeedback(error.message),
  });

  return (
    <AuthShell title={t("auth.loginTitle")} subtitle={t("auth.loginSubtitle")} feedbackState={feedbackState}>
      {feedbackState === "success" ? (
        <LoginExitSkeleton />
      ) : (
        <>
          <Stack
            component="form"
            noValidate
            spacing={2.5}
            onChange={() => setAuthError(null)}
            onSubmit={form.handleSubmit(
              (values) => {
                setAuthError(null);
                mutation.mutate(values);
              },
              () => triggerErrorFeedback(),
            )}
          >
            <TextField
              label={t("auth.email")}
              type="email"
              autoComplete="email"
              autoFocus
              fullWidth
              error={Boolean(form.formState.errors.email)}
              helperText={form.formState.errors.email
                ? t("auth.emailInvalid", { defaultValue: "Введите корректный email" })
                : " "}
              FormHelperTextProps={{ role: form.formState.errors.email ? "alert" : undefined }}
              {...form.register("email")}
            />
            <PasswordTextField
              label={t("auth.password")}
              autoComplete="current-password"
              fullWidth
              error={Boolean(form.formState.errors.password)}
              helperText={form.formState.errors.password ? t("auth.password") : " "}
              FormHelperTextProps={{ role: form.formState.errors.password ? "alert" : undefined }}
              {...form.register("password")}
            />
            {authError && <Alert severity="error" role="alert">{authError}</Alert>}
            <Button
              type="submit"
              size="large"
              variant="contained"
              fullWidth
              disabled={mutation.isPending}
              startIcon={mutation.isPending ? <CircularProgress size={18} color="inherit" /> : undefined}
            >
              {mutation.isPending ? t("common.loading") : t("auth.login")}
            </Button>
          </Stack>

          <Typography variant="body2" color="text.secondary" textAlign="center">
            {t("auth.noAccount")}{" "}
            <Link component={RouterLink} to="/register" state={location.state} fontWeight={700} underline="hover">
              {t("auth.register")}
            </Link>
          </Typography>
        </>
      )}
    </AuthShell>
  );
}
