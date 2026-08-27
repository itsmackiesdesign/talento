import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { useAuth } from "@/store/auth";

export default function InvitePage() {
  const { t } = useTranslation();
  const { token = "" } = useParams<{ token: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const accessToken = useAuth((state) => state.accessToken);
  const setCompanyId = useAuth((state) => state.setCompanyId);

  const invitation = useQuery({
    queryKey: ["team-invitation", token],
    queryFn: () => api.invitations.preview(token),
    enabled: Boolean(token),
    retry: false,
  });

  const accept = useMutation({
    mutationFn: () => api.invitations.accept(token),
    onSuccess: async (result) => {
      setCompanyId(result.company_id);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success(t("invite.accepted"));
      navigate("/settings?tab=team", { replace: true });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (invitation.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Skeleton className="h-64 w-full max-w-md" />
      </div>
    );
  }

  if (invitation.isError || !invitation.data) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>{t("invite.invalidTitle")}</CardTitle>
            <CardDescription>{t("invite.invalidDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full">
              <Link to="/">{t("invite.goHome")}</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const authState = { from: location, email: invitation.data.email };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Users className="h-7 w-7" />
          </span>
          <CardTitle>{t("invite.title", { company: invitation.data.company_name })}</CardTitle>
          <CardDescription>
            {t("invite.desc", { email: invitation.data.email })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2 rounded-lg border p-3 text-sm">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <span>
              {t("invite.expires", { date: formatDateTime(invitation.data.expires_at) })}
            </span>
          </div>

          {accessToken ? (
            <Button
              className="w-full"
              disabled={accept.isPending}
              onClick={() => accept.mutate()}
            >
              {accept.isPending ? t("common.loading") : t("invite.accept")}
            </Button>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <Button asChild variant="outline">
                <Link to="/login" state={authState}>
                  {t("auth.login")}
                </Link>
              </Button>
              <Button asChild>
                <Link to="/register" state={authState}>
                  {t("auth.register")}
                </Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
