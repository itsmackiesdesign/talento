import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppLayout } from "@/components/layout";
import { Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useAuth } from "@/store/auth";

import ApplicationsPage from "@/pages/Applications";
import BranchesPage from "@/pages/Branches";
import DashboardPage from "@/pages/Dashboard";
import LandingPage from "@/pages/Landing";
import LoginPage from "@/pages/Login";
import NewsPage from "@/pages/News";
import OnboardingPage from "@/pages/Onboarding";
import QuestionsPage from "@/pages/Questions";
import RegisterPage from "@/pages/Register";
import SettingsPage from "@/pages/Settings";
import VacanciesPage from "@/pages/Vacancies";

function FullPageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-3">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}

/** Gate for everything behind login. Also routes users with no company into onboarding —
 *  the panel is meaningless until a company exists, and every tenant-scoped request would
 *  otherwise 403. */
function RequireCompany({ children }: { children: React.ReactNode }) {
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

  return <AppLayout me={data}>{children}</AppLayout>;
}

export default function App() {
  const accessToken = useAuth((s) => s.accessToken);

  return (
    <Routes>
      <Route
        path="/login"
        element={accessToken ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={accessToken ? <Navigate to="/" replace /> : <RegisterPage />}
      />
      <Route
        path="/onboarding"
        element={accessToken ? <OnboardingPage /> : <Navigate to="/login" replace />}
      />

      <Route
        path="/"
        element={accessToken ? <RequireCompany><DashboardPage /></RequireCompany> : <LandingPage />}
      />
      <Route path="/branches" element={<RequireCompany><BranchesPage /></RequireCompany>} />
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
      <Route path="/settings" element={<RequireCompany><SettingsPage /></RequireCompany>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
