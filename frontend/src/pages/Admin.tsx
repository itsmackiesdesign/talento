import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeft,
  Bot,
  BriefcaseBusiness,
  Building2,
  FileText,
  LogOut,
  Search,
  ShieldCheck,
  Users,
  WalletCards,
} from "lucide-react";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label, Skeleton } from "@/components/ui/misc";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { AdminStats } from "@/lib/types";
import { useAuth } from "@/store/auth";

function date(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

const money = new Intl.NumberFormat("uz-UZ");

function AdminShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const logout = useAuth((state) => state.logout);
  return (
    <div className="min-h-screen bg-muted/30">
      <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Link to="/admin" className="flex items-center gap-3 font-semibold">
            <span className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="size-5" />
            </span>
            <span>
              Talento <span className="text-muted-foreground">Platform Admin</span>
            </span>
          </Link>
          <Button
            variant="ghost"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut /> Sign out
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold">{value ?? "—"}</p>
        </div>
        <span className="rounded-lg bg-primary/10 p-3 text-primary">{icon}</span>
      </CardContent>
    </Card>
  );
}

export function AdminHomePage() {
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "suspended">("all");
  const [page, setPage] = useState(1);
  const stats = useQuery({ queryKey: ["admin", "stats"], queryFn: api.admin.stats });
  const companies = useQuery({
    queryKey: ["admin", "companies", search, status, page],
    queryFn: () =>
      api.admin.companies({ q: search, tenant_status: status, page, page_size: 25 }),
  });
  const audit = useQuery({
    queryKey: ["admin", "audit"],
    queryFn: () => api.admin.audit(10),
  });

  const summary: Array<[string, keyof AdminStats, ReactNode]> = [
    ["All tenants", "companies_total", <Building2 key="tenants" />],
    ["Active tenants", "companies_active", <Activity key="active" />],
    ["Suspended", "companies_suspended", <ShieldCheck key="suspended" />],
    ["Users", "users_total", <Users key="users" />],
    ["Active bots", "bots_active", <Bot key="bots" />],
    ["Applications", "applications_total", <FileText key="applications" />],
  ];
  const totalPages = Math.max(1, Math.ceil((companies.data?.total ?? 0) / 25));

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setSearch(searchDraft.trim());
  }

  return (
    <AdminShell>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Platform overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Monitor tenants, plans, usage, bots, and administrative activity.
        </p>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {summary.map(([label, key, icon]) => (
          <StatCard key={key} label={label} value={stats.data?.[key]} icon={icon} />
        ))}
      </section>

      <Card>
        <CardHeader className="gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Tenants</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {companies.data?.total ?? 0} matching companies
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <form onSubmit={submitSearch} className="flex gap-2">
              <Input
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
                placeholder="Search name or slug"
                className="w-full sm:w-64"
              />
              <Button type="submit" variant="outline" size="icon" aria-label="Search">
                <Search />
              </Button>
            </form>
            <Select
              value={status}
              onValueChange={(value: "all" | "active" | "suspended") => {
                setPage(1);
                setStatus(value);
              }}
            >
              <SelectTrigger className="w-full sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All states</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {companies.isPending ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-12 w-full" />
              ))}
            </div>
          ) : companies.isError ? (
            <p className="text-sm text-destructive">{companies.error.message}</p>
          ) : companies.data?.items.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">No tenants found.</p>
          ) : (
            <div className="table-scroll">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="border-b text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="pb-3 font-medium">Company</th>
                    <th className="pb-3 font-medium">State</th>
                    <th className="pb-3 font-medium">Billing</th>
                    <th className="pb-3 font-medium">Bot</th>
                    <th className="pb-3 text-right font-medium">Members</th>
                    <th className="pb-3 text-right font-medium">Vacancies</th>
                    <th className="pb-3 text-right font-medium">Applications</th>
                    <th className="pb-3" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {companies.data?.items.map((company) => (
                    <tr key={company.id}>
                      <td className="py-4">
                        <p className="font-medium">{company.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {company.owner_email ?? company.slug}
                        </p>
                      </td>
                      <td className="py-4">
                        <Badge variant={company.is_suspended ? "destructive" : "success"}>
                          {company.is_suspended ? "Suspended" : "Active"}
                        </Badge>
                      </td>
                      <td className="py-4">
                        <p>
                          {company.billing_mode === "unlimited"
                            ? "Unlimited"
                            : "Pay per application"}
                        </p>
                        {company.billing_mode === "pay_per_application" && (
                          <p className="text-xs text-muted-foreground">
                            {money.format(company.balance_uzs)} UZS
                          </p>
                        )}
                      </td>
                      <td className="py-4 text-muted-foreground">
                        {company.bot_username ? `@${company.bot_username}` : "Not connected"}
                      </td>
                      <td className="py-4 text-right tabular-nums">{company.members_count}</td>
                      <td className="py-4 text-right tabular-nums">{company.vacancies_count}</td>
                      <td className="py-4 text-right tabular-nums">{company.applications_count}</td>
                      <td className="py-4 text-right">
                        <Button asChild variant="outline" size="sm">
                          <Link to={`/admin/tenants/${company.id}`}>Manage</Link>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 flex items-center justify-between border-t pt-4 text-sm">
            <span className="text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent administrative activity</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {audit.data?.length ? (
            audit.data.map((entry) => (
              <div key={entry.id} className="flex flex-col gap-1 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium">
                    {entry.action} · {entry.target_company_name ?? "Deleted tenant"}
                  </p>
                  <p className="text-xs text-muted-foreground">by {entry.actor_email}</p>
                </div>
                <time className="text-xs text-muted-foreground">{date(entry.created_at)}</time>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No administrative changes yet.</p>
          )}
        </CardContent>
      </Card>
    </AdminShell>
  );
}

export function AdminTenantPage() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const [billingMode, setBillingMode] = useState<"unlimited" | "pay_per_application">(
    "unlimited",
  );
  const [applicationPrice, setApplicationPrice] = useState("2000");
  const [topUpAmount, setTopUpAmount] = useState("");
  const [topUpDescription, setTopUpDescription] = useState("");
  const [billingPage, setBillingPage] = useState(1);
  const [reason, setReason] = useState("");
  const tenant = useQuery({
    queryKey: ["admin", "company", id],
    queryFn: () => api.admin.company(id),
    enabled: Boolean(id),
  });
  const balanceHistory = useQuery({
    queryKey: ["admin", "company", id, "balance", billingPage],
    queryFn: () => api.admin.balanceTransactions(id, billingPage),
    enabled: Boolean(id),
  });
  useEffect(() => {
    if (tenant.data) {
      setBillingMode(tenant.data.billing_mode);
      setApplicationPrice(String(tenant.data.application_price_uzs));
      setReason(tenant.data.suspension_reason ?? "");
    }
  }, [tenant.data]);

  const update = useMutation({
    mutationFn: (data: Parameters<typeof api.admin.updateCompany>[1]) =>
      api.admin.updateCompany(id, data),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "company", id], data);
      queryClient.invalidateQueries({ queryKey: ["admin", "companies"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
      toast.success("Tenant updated");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const topUp = useMutation({
    mutationFn: () =>
      api.admin.topUpBalance(id, {
        amount_uzs: Number(topUpAmount),
        description: topUpDescription.trim() || undefined,
      }),
    onSuccess: () => {
      setTopUpAmount("");
      setTopUpDescription("");
      queryClient.invalidateQueries({ queryKey: ["admin", "company", id] });
      queryClient.invalidateQueries({ queryKey: ["admin", "companies"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
      toast.success("Balance topped up");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (tenant.isPending) {
    return (
      <AdminShell>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-72 w-full" />
      </AdminShell>
    );
  }
  if (tenant.isError || !tenant.data) {
    return (
      <AdminShell>
        <Button asChild variant="ghost"><Link to="/admin"><ArrowLeft /> Back</Link></Button>
        <p className="text-destructive">{tenant.error?.message ?? "Tenant not found"}</p>
      </AdminShell>
    );
  }

  const company = tenant.data;
  const metricCards = [
    ["Members", company.members_count, <Users key="members" />],
    ["Branches", company.branches_count, <Building2 key="branches" />],
    ["Vacancies", company.vacancies_count, <BriefcaseBusiness key="vacancies" />],
    ["Applications", company.applications_count, <FileText key="applications" />],
    ["Balance", `${money.format(company.balance_uzs)} UZS`, <WalletCards key="balance" />],
  ] as const;

  return (
    <AdminShell>
      <div className="space-y-3">
        <Button asChild variant="ghost" className="-ml-3">
          <Link to="/admin"><ArrowLeft /> All tenants</Link>
        </Button>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">{company.name}</h1>
              <Badge variant={company.is_suspended ? "destructive" : "success"}>
                {company.is_suspended ? "Suspended" : "Active"}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {company.slug} · created {date(company.created_at)}
            </p>
          </div>
          <div className="text-sm text-muted-foreground">
            <p>{company.owner_email ?? "No owner"}</p>
            <p>{company.bot_username ? `@${company.bot_username}` : "No bot connected"}</p>
          </div>
        </div>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {metricCards.map(([label, value, icon]) => (
          <StatCard key={label} label={label} value={value} icon={icon} />
        ))}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader><CardTitle>Tenant controls</CardTitle></CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <div>
                <h3 className="font-medium">Application billing</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Current balance: {money.format(company.balance_uzs)} UZS
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Billing mode</Label>
                  <Select
                    value={billingMode}
                    onValueChange={(value: "unlimited" | "pay_per_application") =>
                      setBillingMode(value)
                    }
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unlimited">Unlimited</SelectItem>
                      <SelectItem value="pay_per_application">Pay per application</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="application-price">Price per application, UZS</Label>
                  <Input
                    id="application-price"
                    type="number"
                    min={1}
                    value={applicationPrice}
                    onChange={(event) => setApplicationPrice(event.target.value)}
                  />
                </div>
              </div>
              <Button
                disabled={
                  update.isPending ||
                  !Number.isInteger(Number(applicationPrice)) ||
                  Number(applicationPrice) <= 0 ||
                  (billingMode === company.billing_mode &&
                    Number(applicationPrice) === company.application_price_uzs)
                }
                onClick={() =>
                  update.mutate({
                    billing_mode: billingMode,
                    application_price_uzs: Number(applicationPrice),
                  })
                }
              >
                Save billing settings
              </Button>

              <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
                <h4 className="text-sm font-medium">Add funds</h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="top-up-amount">Amount, UZS</Label>
                    <Input
                      id="top-up-amount"
                      type="number"
                      min={1}
                      value={topUpAmount}
                      onChange={(event) => setTopUpAmount(event.target.value)}
                      placeholder="100000"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="top-up-description">Description</Label>
                    <Input
                      id="top-up-description"
                      value={topUpDescription}
                      onChange={(event) => setTopUpDescription(event.target.value)}
                      placeholder="Bank transfer #123"
                    />
                  </div>
                </div>
                <Button
                  variant="secondary"
                  disabled={
                    topUp.isPending ||
                    !Number.isInteger(Number(topUpAmount)) ||
                    Number(topUpAmount) <= 0
                  }
                  onClick={() => topUp.mutate()}
                >
                  Top up balance
                </Button>
              </div>
            </div>

            <div className="border-t pt-5">
              <h3 className="font-medium">Access control</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Suspension immediately blocks tenant API access and stops bot updates.
              </p>
              {company.is_suspended ? (
                <div className="mt-4 space-y-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                  <p className="text-sm">Reason: {company.suspension_reason}</p>
                  <Button
                    variant="outline"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ is_suspended: false })}
                  >
                    Reactivate tenant
                  </Button>
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  <Label htmlFor="suspension-reason">Suspension reason</Label>
                  <Textarea
                    id="suspension-reason"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="Explain why access is being suspended"
                  />
                  <Button
                    variant="destructive"
                    disabled={update.isPending || !reason.trim()}
                    onClick={() => update.mutate({ is_suspended: true, suspension_reason: reason.trim() })}
                  >
                    Suspend tenant
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Members</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {company.members.map((member) => (
              <div key={member.user_id} className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">{member.full_name}</p>
                  <p className="text-xs text-muted-foreground">{member.email}</p>
                </div>
                <Badge variant="outline">{member.role}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Balance history</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {balanceHistory.data?.items.length ? balanceHistory.data.items.map((entry) => (
            <div key={entry.id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium">
                  {entry.kind === "signup_bonus"
                    ? "Welcome bonus"
                    : entry.kind === "top_up"
                      ? "Balance top-up"
                      : "Application charge"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {entry.vacancy_title ?? entry.description ?? "—"} · {date(entry.created_at)}
                </p>
              </div>
              <div className="text-right">
                <p className={entry.amount_uzs > 0 ? "font-semibold text-emerald-600" : "font-semibold"}>
                  {entry.amount_uzs > 0 ? "+" : ""}{money.format(entry.amount_uzs)} UZS
                </p>
                <p className="text-xs text-muted-foreground">
                  Balance: {money.format(entry.balance_after_uzs)} UZS
                </p>
              </div>
            </div>
          )) : <p className="text-sm text-muted-foreground">No balance transactions yet.</p>}
          <div className="flex justify-end gap-2 border-t pt-3">
            <Button variant="outline" size="sm" disabled={billingPage <= 1} onClick={() => setBillingPage(billingPage - 1)}>
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={billingPage * 25 >= (balanceHistory.data?.total ?? 0)}
              onClick={() => setBillingPage(billingPage + 1)}
            >
              Next
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Audit trail</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {company.recent_audit.length ? company.recent_audit.map((entry) => (
            <div key={entry.id} className="flex flex-col gap-1 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium">{entry.action}</p>
                <p className="text-xs text-muted-foreground">by {entry.actor_email}</p>
              </div>
              <time className="text-xs text-muted-foreground">{date(entry.created_at)}</time>
            </div>
          )) : <p className="text-sm text-muted-foreground">No changes recorded yet.</p>}
        </CardContent>
      </Card>
    </AdminShell>
  );
}

export function AdminAccessDenied() {
  const navigate = useNavigate();
  const logout = useAuth((state) => state.logout);
  return (
    <div className="grid min-h-screen place-items-center p-4">
      <Card className="max-w-md">
        <CardHeader><CardTitle>Platform administrator access required</CardTitle></CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>This account is authenticated but does not have permission to manage all tenants.</p>
          <Button onClick={() => { logout(); navigate("/login"); }}>Sign in with another account</Button>
        </CardContent>
      </Card>
    </div>
  );
}
