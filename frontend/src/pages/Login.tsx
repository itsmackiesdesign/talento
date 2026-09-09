import { zodResolver } from "@hookform/resolvers/zod";
import Button from "@mui/material/Button";
import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link as RouterLink, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { AuthShell, PasswordTextField } from "@/components/auth-shell";
import { api } from "@/lib/api";
import { useAuth } from "@/store/auth";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setTokens = useAuth((state) => state.setTokens);
  const routeState = location.state as {
    from?: { pathname?: string; search?: string };
    email?: string;
  } | null;

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: routeState?.email ?? "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: api.auth.login,
    onSuccess: async (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      const from = routeState?.from;
      if (from?.pathname) {
        navigate(`${from.pathname}${from.search ?? ""}`);
        return;
      }
      try {
        const me = await api.auth.me();
        navigate(me.user.is_platform_admin ? "/admin" : "/");
      } catch {
        navigate("/");
      }
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <AuthShell title={t("auth.loginTitle")} subtitle={t("auth.loginSubtitle")}>
      <Stack
        component="form"
        noValidate
        spacing={2.5}
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
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
          {...form.register("email")}
        />
        <PasswordTextField
          label={t("auth.password")}
          autoComplete="current-password"
          fullWidth
          error={Boolean(form.formState.errors.password)}
          helperText={form.formState.errors.password ? t("auth.password") : " "}
          {...form.register("password")}
        />
        <Button type="submit" size="large" variant="contained" fullWidth disabled={mutation.isPending}>
          {mutation.isPending ? t("common.loading") : t("auth.login")}
        </Button>
      </Stack>

      <Typography variant="body2" color="text.secondary" textAlign="center">
        {t("auth.noAccount")}{" "}
        <Link component={RouterLink} to="/register" state={location.state} fontWeight={700} underline="hover">
          {t("auth.register")}
        </Link>
      </Typography>
    </AuthShell>
  );
}
