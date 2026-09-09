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
  full_name: z.string().min(1),
  email: z.string().email(),
  password: z.string().min(8),
});

export default function RegisterPage() {
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
    defaultValues: { full_name: "", email: routeState?.email ?? "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: api.auth.register,
    onSuccess: (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      const from = routeState?.from;
      navigate(from?.pathname ? `${from.pathname}${from.search ?? ""}` : "/onboarding");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <AuthShell title={t("auth.registerTitle")} subtitle={t("auth.registerSubtitle")}>
      <Stack
        component="form"
        noValidate
        spacing={2.5}
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      >
        <TextField
          label={t("auth.fullName")}
          autoComplete="name"
          autoFocus
          fullWidth
          error={Boolean(form.formState.errors.full_name)}
          helperText={form.formState.errors.full_name
            ? t("auth.nameRequired", { defaultValue: "Укажите имя и фамилию" })
            : " "}
          {...form.register("full_name")}
        />
        <TextField
          label={t("auth.email")}
          type="email"
          autoComplete="email"
          fullWidth
          error={Boolean(form.formState.errors.email)}
          helperText={form.formState.errors.email
            ? t("auth.emailInvalid", { defaultValue: "Введите корректный email" })
            : " "}
          {...form.register("email")}
        />
        <PasswordTextField
          label={t("auth.password")}
          autoComplete="new-password"
          fullWidth
          error={Boolean(form.formState.errors.password)}
          helperText={t("auth.passwordHint")}
          {...form.register("password")}
        />
        <Button type="submit" size="large" variant="contained" fullWidth disabled={mutation.isPending}>
          {mutation.isPending ? t("common.loading") : t("auth.register")}
        </Button>
      </Stack>

      <Typography variant="body2" color="text.secondary" textAlign="center">
        {t("auth.hasAccount")}{" "}
        <Link component={RouterLink} to="/login" state={location.state} fontWeight={700} underline="hover">
          {t("auth.login")}
        </Link>
      </Typography>
    </AuthShell>
  );
}
