import { useQuery } from "@tanstack/react-query";
import Box from "@mui/material/Box";
import Skeleton from "@mui/material/Skeleton";
import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppLayout } from "@/components/layout";
import { api } from "@/lib/api";
import { useAuth } from "@/store/auth";

const ApplicationsPage = lazy(() => import("@/pages/Applications"));
const BranchesPage = lazy(() => import("@/pages/Branches"));
const BillingPage = lazy(() => import("@/pages/Billing"));
const BotBuilderPage = lazy(() => import("@/pages/BotBuilder"));
const DashboardPage = lazy(() => import("@/pages/Dashboard"));
const LandingPage = lazy(() => import("@/pages/Landing"));
const InvitePage = lazy(() => import("@/pages/Invite"));
const LoginPage = lazy(() => import("@/pages/Login"));
const NewsPage = lazy(() => import("@/pages/News"));
const OnboardingPage = lazy(() => import("@/pages/Onboarding"));
const QuestionsPage = lazy(() => import("@/pages/Questions"));
const RegisterPage = lazy(() => import("@/pages/Register"));
const SettingsPage = lazy(() => import("@/pages/Settings"));
const VacanciesPage = lazy(() => import("@/pages/Vacancies"));
const AdminAccessDenied = lazy(() => import("@/pages/Admin").then((module) => ({ default: module.AdminAccessDenied })));
const AdminHomePage = lazy(() => import("@/pages/Admin").then((module) => ({ default: module.AdminHomePage })));
const AdminTenantPage = lazy(() => import("@/pages/Admin").then((module) => ({ default: module.AdminTenantPage })));

function FullPageLoader() {
  return (
    <Box sx={{ minHeight: "100dvh", display: "grid", placeItems: "center", p: 3 }}>
      <Box sx={{ width: "100%", maxWidth: 480 }}>
        <Skeleton variant="text" width="52%" height={44} />
        <Skeleton variant="rounded" height={132} sx={{ mt: 2 }} />
        <Skeleton variant="rounded" height={132} sx={{ mt: 2 }} />
      </Box>
    </Box>
  );
}

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

/** Gate for everything behind login. Also routes users with no company into onboarding —
 *  the panel is meaningless until a company exists, and every tenant-scoped request would
 *  otherwise 403. */
function RequireCompany({
  children,
  ownerOnly = false,
}: {
  children: React.ReactNode;
  ownerOnly?: boolean;
}) {
  const location = useLocation();
  const accessToken = useAuth((s) => s.accessToken);
  const setCompanyId = useAuth((s) => s.setCompanyId);

  const { data, isPending, isError } = useQuery({
    queryKey: ["me"],
    queryFn: api.auth.me,
    enabled: Boolean(accessToken),
  });

  const companyId = data?.companies[0]?.id;
  useEffect(() => {
    if (companyId && useAuth.getState().companyId !== companyId) setCompanyId(companyId);
  }, [companyId, setCompanyId]);

  if (!accessToken) return <Navigate to="/login" replace state={{ from: location }} />;
  if (isPending) return <FullPageLoader />;
  if (isError) return <Navigate to="/login" replace />;
  if (!data.companies[0]) return <Navigate to="/onboarding" replace />;
  if (ownerOnly && data.role !== "owner") return <Navigate to="/" replace />;

  return <AppLayout me={data}>{children}</AppLayout>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const accessToken = useAuth((s) => s.accessToken);
  const { data, isPending, isError } = useQuery({
    queryKey: ["me"],
    queryFn: api.auth.me,
    enabled: Boolean(accessToken),
  });

  if (!accessToken) return <Navigate to="/login" replace state={{ from: location }} />;
  if (isPending) return <FullPageLoader />;
  if (isError) return <Navigate to="/login" replace />;
  if (!data.user.is_platform_admin) return <AdminAccessDenied />;
  return children;
}

export default function App() {
  const accessToken = useAuth((s) => s.accessToken);

  return (
    <Suspense fallback={<FullPageLoader />}>
      <ScrollToTop />
      <Routes>
      <Route
        path="/login"
        element={accessToken ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={accessToken ? <Navigate to="/" replace /> : <RegisterPage />}
      />
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route
        path="/onboarding"
        element={accessToken ? <OnboardingPage /> : <Navigate to="/login" replace />}
      />

      <Route path="/admin" element={<RequireAdmin><AdminHomePage /></RequireAdmin>} />
      <Route
        path="/admin/tenants/:id"
        element={<RequireAdmin><AdminTenantPage /></RequireAdmin>}
      />

      <Route
        path="/"
        element={accessToken ? <RequireCompany><DashboardPage /></RequireCompany> : <LandingPage />}
      />
      <Route path="/branches" element={<RequireCompany><BranchesPage /></RequireCompany>} />
      <Route path="/bot-builder" element={<RequireCompany><BotBuilderPage /></RequireCompany>} />
      <Route path="/vacancies" element={<RequireCompany><VacanciesPage /></RequireCompany>} />
      <Route
        path="/vacancies/:id/questions"
        element={<RequireCompany><QuestionsPage /></RequireCompany>}
      />
      <Route path="/news" element={<RequireCompany><NewsPage /></RequireCompany>} />
      <Route path="/applications" element={<RequireCompany><ApplicationsPage /></RequireCompany>} />
      <Route
        path="/applications/:id"
        element={<RequireCompany><ApplicationsPage /></RequireCompany>}
      />
      <Route
        path="/billing"
        element={<RequireCompany ownerOnly><BillingPage /></RequireCompany>}
      />
      <Route path="/settings" element={<RequireCompany><SettingsPage /></RequireCompany>} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
