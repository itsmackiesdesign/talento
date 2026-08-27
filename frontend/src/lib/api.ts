/** Typed fetch wrapper with automatic access-token refresh.
 *
 *  Access tokens live 15 minutes. Rather than pre-emptively refreshing on a timer, a 401
 *  triggers exactly one refresh attempt and the original request is replayed. Concurrent
 *  401s share a single in-flight refresh (`refreshPromise`) so a page that fires six
 *  queries at once does not burn six refresh tokens.
 */

import { useAuth } from "@/store/auth";
import type {
  AdminAuditItem,
  AdminCompanyDetail,
  AdminCompanyPage,
  AdminStats,
  BalanceTransaction,
  BalanceTransactionPage,
  BillingSummary,
  ApplicationDetail,
  ApplicationPage,
  ApplicationStatusOut,
  Bot,
  Branch,
  Comment,
  Company,
  DashboardStats,
  FilterOptions,
  LinkCode,
  Me,
  NewsItem,
  Question,
  TeamMember,
  TeamInvitation,
  TeamInvitationAccepted,
  TeamInvitationCreated,
  TeamInvitationPreview,
  TokenPair,
  Translations,
  Vacancy,
  WebhookStatus,
} from "./types";

/** API origin.
 *
 *  Empty (the default) means same-origin `/api/v1`, served through the Vite dev proxy.
 *  Setting `VITE_API_URL` points the browser straight at another origin — a tunnel, or a
 *  separately deployed API — in which case that origin must appear in the backend's
 *  CORS_ORIGINS.
 */
const API_ORIGIN = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
const BASE = `${API_ORIGIN}/api/v1`;

/** ngrok's free tier serves an HTML interstitial to anything with a browser User-Agent,
 *  which would arrive here as an unparseable response. This header opts out of it, and is
 *  harmless against any other host. */
const EXTRA_HEADERS: Record<string, string> = API_ORIGIN.includes("ngrok")
  ? { "ngrok-skip-browser-warning": "true" }
  : {};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

let refreshPromise: Promise<boolean> | null = null;

async function runRefresh(): Promise<boolean> {
  const { refreshToken, setTokens, logout } = useAuth.getState();
  if (!refreshToken) {
    logout();
    return false;
  }
  try {
    const resp = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...EXTRA_HEADERS },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!resp.ok) {
      logout();
      return false;
    }
    const tokens: TokenPair = await resp.json();
    setTokens(tokens.access_token, tokens.refresh_token);
    return true;
  } catch {
    logout();
    return false;
  }
}

async function parseError(resp: Response): Promise<string> {
  try {
    const body = await resp.json();
    if (typeof body.detail === "string") return body.detail;
    // FastAPI validation errors arrive as a list of {loc, msg}.
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((d: { loc?: string[]; msg: string }) => {
          const field = d.loc?.filter((p) => p !== "body").join(".");
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join("; ");
    }
    return resp.statusText;
  } catch {
    return resp.statusText || "Ошибка сети";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const { accessToken, companyId } = useAuth.getState();
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  for (const [key, value] of Object.entries(EXTRA_HEADERS)) headers.set(key, value);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (companyId) headers.set("X-Company-Id", companyId);

  const resp = await fetch(`${BASE}${path}`, { ...options, headers });

  if (resp.status === 401 && retry) {
    refreshPromise ??= runRefresh().finally(() => {
      refreshPromise = null;
    });
    if (await refreshPromise) return request<T>(path, options, false);
  }

  if (!resp.ok) throw new ApiError(resp.status, await parseError(resp));
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });

function qs(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const api = {
  auth: {
    register: (data: { email: string; password: string; full_name: string }) =>
      post<TokenPair>("/auth/register", data),
    login: (data: { email: string; password: string }) => post<TokenPair>("/auth/login", data),
    me: () => get<Me>("/auth/me"),
  },

  admin: {
    stats: () => get<AdminStats>("/admin/stats"),
    companies: (params: {
      q?: string;
      tenant_status?: "all" | "active" | "suspended";
      page?: number;
      page_size?: number;
    }) => get<AdminCompanyPage>(`/admin/companies${qs(params)}`),
    company: (id: string) => get<AdminCompanyDetail>(`/admin/companies/${id}`),
    updateCompany: (
      id: string,
      data: {
        billing_mode?: "unlimited" | "pay_per_application";
        application_price_uzs?: number;
        is_suspended?: boolean;
        suspension_reason?: string | null;
      },
    ) => patch<AdminCompanyDetail>(`/admin/companies/${id}`, data),
    topUpBalance: (id: string, data: { amount_uzs: number; description?: string }) =>
      post<BalanceTransaction>(`/admin/companies/${id}/balance/top-up`, data),
    balanceTransactions: (id: string, page = 1) =>
      get<BalanceTransactionPage>(
        `/admin/companies/${id}/billing/transactions${qs({ page, page_size: 25 })}`,
      ),
    audit: (limit = 50) => get<AdminAuditItem[]>(`/admin/audit${qs({ limit })}`),
  },

  billing: {
    summary: () => get<BillingSummary>("/billing/summary"),
    transactions: (page = 1) =>
      get<BalanceTransactionPage>(`/billing/transactions${qs({ page, page_size: 25 })}`),
  },

  company: {
    create: (data: { name: string; default_language?: string }) =>
      post<Company>("/companies", data),
    get: () => get<Company>("/company"),
    update: (data: Partial<Company>) => patch<Company>("/company", data),
    setLanguages: (enabled_languages: string[]) =>
      patch<Company>("/company", { enabled_languages }),
    team: () => get<TeamMember[]>("/company/team"),
    invitations: () => get<TeamInvitation[]>("/company/team/invitations"),
    invite: (email: string) =>
      post<TeamInvitationCreated>("/company/team/invitations", { email }),
    revokeInvitation: (id: string) => del<void>(`/company/team/invitations/${id}`),
    removeMember: (userId: string) => del<void>(`/company/team/${userId}`),
    transferOwnership: (userId: string) =>
      post<TeamMember[]>(`/company/team/${userId}/transfer-ownership`),
  },

  invitations: {
    preview: (token: string) =>
      get<TeamInvitationPreview>(`/team/invitations/${encodeURIComponent(token)}`),
    accept: (token: string) =>
      post<TeamInvitationAccepted>(`/team/invitations/${encodeURIComponent(token)}/accept`),
  },

  bot: {
    get: () => get<Bot>("/bot"),
    connect: (token: string) => post<Bot>("/bot", { token }),
    update: (data: Partial<Bot>) => patch<Bot>("/bot", data),
    disconnect: () => del<void>("/bot"),
    webhookStatus: () => get<WebhookStatus>("/bot/webhook-status"),
  },

  branches: {
    list: () => get<Branch[]>("/branches"),
    create: (data: Partial<Branch>) => post<Branch>("/branches", data),
    update: (id: string, data: Partial<Branch>) => patch<Branch>(`/branches/${id}`, data),
    remove: (id: string, moveTo?: string | null) =>
      del<void>(`/branches/${id}${qs({ move_vacancies_to: moveTo ?? "null" })}`),
    reorder: (ids: string[]) => post<void>("/branches/reorder", { ids }),
  },

  vacancies: {
    list: (params: { branch_id?: string; status?: string } = {}) =>
      get<Vacancy[]>(`/vacancies${qs(params)}`),
    get: (id: string) => get<Vacancy>(`/vacancies/${id}`),
    create: (data: Partial<Vacancy>) => post<Vacancy>("/vacancies", data),
    update: (id: string, data: Partial<Vacancy> & { clear_branch?: boolean }) =>
      patch<Vacancy>(`/vacancies/${id}`, data),
    remove: (id: string) => del<void>(`/vacancies/${id}`),
    duplicate: (id: string, data: { branch_id?: string | null; title?: string }) =>
      post<Vacancy>(`/vacancies/${id}/duplicate`, data),
    reorder: (ids: string[]) => post<void>("/vacancies/reorder", { ids }),
  },

  questions: {
    list: (vacancyId?: string | "null") =>
      get<Question[]>(`/questions${qs({ vacancy_id: vacancyId })}`),
    create: (data: Partial<Question>) => post<Question>("/questions", data),
    update: (id: string, data: Partial<Question>) => patch<Question>(`/questions/${id}`, data),
    remove: (id: string) => del<void>(`/questions/${id}`),
    copy: (id: string, vacancyId: string | null) =>
      post<Question>(`/questions/${id}/copy`, { vacancy_id: vacancyId }),
    reorder: (ids: string[]) => post<void>("/questions/reorder", { ids }),
  },

  news: {
    list: () => get<NewsItem[]>("/news"),
    create: (data: Partial<NewsItem>) => post<NewsItem>("/news", data),
    update: (id: string, data: Partial<NewsItem>) => patch<NewsItem>(`/news/${id}`, data),
    remove: (id: string) => del<void>(`/news/${id}`),
    reorder: (ids: string[]) => post<void>("/news/reorder", { ids }),
  },

  applications: {
    list: (params: {
      status?: string;
      vacancy_id?: string;
      branch_id?: string;
      date_from?: string;
      date_to?: string;
      search?: string;
      answers?: string;
      page?: number;
      page_size?: number;
    }) => get<ApplicationPage>(`/applications${qs(params)}`),
    get: (id: string) => get<ApplicationDetail>(`/applications/${id}`),
    setStatus: (id: string, statusId: string) =>
      patch<ApplicationDetail>(`/applications/${id}/status`, { status_id: statusId }),
    comment: (id: string, text: string) =>
      post<Comment>(`/applications/${id}/comments`, { text }),
    remove: (id: string) => del<void>(`/applications/${id}`),
    filters: () => get<FilterOptions>("/applications/meta/filters"),
    exportUrl: (params: Record<string, string | undefined>) =>
      `${BASE}/applications/export${qs({ ...params, format: "csv" })}`,
  },

  applicationStatuses: {
    list: () => get<ApplicationStatusOut[]>("/application-statuses"),
    create: (data: { label: string; translations?: Translations; notify_candidate?: boolean }) =>
      post<ApplicationStatusOut>("/application-statuses", data),
    update: (
      id: string,
      data: Partial<{ label: string; translations: Translations; notify_candidate: boolean }>,
    ) => patch<ApplicationStatusOut>(`/application-statuses/${id}`, data),
    remove: (id: string, moveApplicationsTo?: string) =>
      del<void>(`/application-statuses/${id}${qs({ move_applications_to: moveApplicationsTo })}`),
    reorder: (ids: string[]) => post<void>("/application-statuses/reorder", { ids }),
  },

  dashboard: {
    stats: (days = 30) => get<DashboardStats>(`/dashboard/stats${qs({ days })}`),
  },

  notifications: {
    linkCode: () => get<LinkCode>("/notifications/link-code"),
    unlink: () => del<void>("/notifications/link"),
  },
};

/** Upload an image and get back its URL.
 *
 *  Sent as multipart, so it deliberately bypasses `request()` — that wrapper forces a JSON
 *  Content-Type, and setting it by hand on FormData strips the multipart boundary browsers
 *  generate, which makes the body unparseable server-side.
 */
export async function uploadImage(file: File): Promise<{ url: string }> {
  const { accessToken, companyId } = useAuth.getState();
  const body = new FormData();
  body.append("file", file);

  const resp = await fetch(`${BASE}/uploads/image`, {
    method: "POST",
    body,
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(companyId ? { "X-Company-Id": companyId } : {}),
      ...EXTRA_HEADERS,
    },
  });
  if (!resp.ok) throw new ApiError(resp.status, await parseError(resp));
  return resp.json();
}

/** CSV export needs the auth header, so it cannot be a plain <a href>. Fetch the file as
 *  a blob and hand it to a synthesised download link. */
export async function downloadExport(params: Record<string, string | undefined>) {
  const { accessToken, companyId } = useAuth.getState();
  const resp = await fetch(api.applications.exportUrl(params), {
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(companyId ? { "X-Company-Id": companyId } : {}),
      ...EXTRA_HEADERS,
    },
  });
  if (!resp.ok) throw new ApiError(resp.status, await parseError(resp));

  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `applications-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
