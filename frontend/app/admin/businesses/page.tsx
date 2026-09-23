"use client";

import { AdminCreateBusinessModal } from "@/components/admin/AdminCreateBusinessModal";
import { AdminIdentityNav } from "@/components/admin/AdminIdentityNav";
import { AdminAct, AdminPage } from "@/components/admin/AdminUi";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/Toast";
import {
  formatBusinessAddress,
  statusTone,
} from "@/lib/admin/identityDirectory";
import { downloadPdf } from "@/lib/admin/downloadPdf";
import { ApiError } from "@/lib/api/client";
import { CompanyLogo, companyLocation } from "@/components/company/CompanyBrand";
import { identityApi, type Business } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type TypeFilter = "all" | "buyer" | "supplier";
type StatusFilter = "all" | "pending" | "verified" | "suspended" | "rejected" | "active";
type DomainFilter = "all" | "has_domain" | "missing_domain";
type SortKey = "updated" | "name" | "type" | "status";

function AdminBusinessesPageInner() {
  const searchParams = useSearchParams();
  const typeFromUrl = searchParams.get("type");
  const qFromUrl = searchParams.get("q") ?? "";
  const initialType: TypeFilter =
    typeFromUrl === "buyer" || typeFromUrl === "supplier" ? typeFromUrl : "all";

  const { hasPermission } = useAuth();
  const canManage = hasPermission("businesses.manage");
  const { success, error: toastError } = useToast();
  const [rows, setRows] = useState<Business[]>([]);
  const [typeFilter, setTypeFilter] = useState<TypeFilter>(initialType);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [domainFilter, setDomainFilter] = useState<DomainFilter>("all");
  const [cityNeedle, setCityNeedle] = useState("");
  const [query, setQuery] = useState(qFromUrl);
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [createType, setCreateType] = useState<"buyer" | "supplier" | null>(null);

  useEffect(() => {
    setTypeFilter(initialType);
    setPage(1);
  }, [initialType]);

  useEffect(() => {
    setQuery(qFromUrl);
    setPage(1);
  }, [qFromUrl]);

  const load = useCallback(() => {
    setError(null);
    setLoading(true);
    void identityApi
      .listPlatformBusinesses({
        account_type: typeFilter === "all" ? undefined : typeFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
        q: query.trim() || undefined,
        page,
        page_size: pageSize,
      })
      .then((result) => {
        setRows(result.data);
        setTotal(result.meta.total);
      })
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load companies.",
        ),
      )
      .finally(() => setLoading(false));
  }, [page, pageSize, query, statusFilter, typeFilter]);

  useEffect(() => {
    const handle = window.setTimeout(() => load(), query ? 280 : 0);
    return () => window.clearTimeout(handle);
  }, [load, query]);

  useEffect(() => {
    setPage(1);
  }, [typeFilter, statusFilter, query, pageSize]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  const viewRows = useMemo(() => {
    let list = [...rows];
    const city = cityNeedle.trim().toLowerCase();
    if (domainFilter === "has_domain") {
      list = list.filter((r) => Boolean(r.email_domain));
    } else if (domainFilter === "missing_domain") {
      list = list.filter((r) => !r.email_domain);
    }
    if (city) {
      list = list.filter((r) => {
        const a = r.address;
        const blob = [a?.city, a?.governorate, a?.district, a?.country]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return blob.includes(city);
      });
    }
    list.sort((a, b) => {
      if (sortKey === "name") return a.name.localeCompare(b.name);
      if (sortKey === "type") return (a.type || "").localeCompare(b.type || "");
      if (sortKey === "status") return (a.status || "").localeCompare(b.status || "");
      return 0;
    });
    return list;
  }, [cityNeedle, domainFilter, rows, sortKey]);

  const stats = useMemo(
    () => [
      { label: "Matching", value: total },
      { label: "This page", value: viewRows.length },
      { label: "Buyers (page)", value: viewRows.filter((r) => r.type === "buyer").length },
      {
        label: "Suppliers (page)",
        value: viewRows.filter((r) => r.type === "supplier").length,
      },
    ],
    [total, viewRows],
  );

  const title =
    typeFilter === "buyer"
      ? "Buyers"
      : typeFilter === "supplier"
        ? "Supplier companies"
        : "Companies";

  function exportPage() {
    downloadPdf(
      `tradebay-companies-page-${page}.pdf`,
      [
        "id",
        "name",
        "type",
        "status",
        "email_domain",
        "legal_name",
        "tax_number",
        "contact_email",
        "verification_status",
        "city",
      ],
      viewRows.map((r) => [
        r.id,
        r.name,
        r.type || "",
        r.status || "",
        r.email_domain || "",
        r.legal_name || "",
        r.tax_number || "",
        r.contact_email || "",
        r.verification_status || "",
        r.address?.city || "",
      ]),
      { title: `TradeBay ${title.toLowerCase()}`, subtitle: `Page ${page} · ${viewRows.length} row(s)` },
    );
    success("PDF exported", `${viewRows.length} companies`);
  }

  return (
    <AdminPage>
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.admin.home} className="hover:underline">
          Admin
        </Link>{" "}
        / Identity / {title}
      </p>
      <DirectoryMast
        title={title}
        mark="Platform"
        size="page"
        actions={
          <div className="flex flex-wrap gap-2">
            {canManage && typeFilter === "buyer" ? (
              <AdminAct tone="go" arrow onClick={() => setCreateType("buyer")}>
                Add buyer
              </AdminAct>
            ) : null}
            {canManage && typeFilter === "supplier" ? (
              <AdminAct tone="go" arrow onClick={() => setCreateType("supplier")}>
                Add supplier
              </AdminAct>
            ) : null}
            {canManage && typeFilter === "all" ? (
              <>
                <AdminAct tone="go" arrow onClick={() => setCreateType("buyer")}>
                  Add buyer
                </AdminAct>
                <AdminAct tone="ghost" arrow onClick={() => setCreateType("supplier")}>
                  Add supplier
                </AdminAct>
              </>
            ) : null}
            <AdminAct tone="soft" onClick={exportPage} disabled={viewRows.length === 0}>
              Export PDF
            </AdminAct>
          </div>
        }
      />

      <AdminIdentityNav />

      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t load businesses" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      <div className="tb-summary">
        {stats.map((stat) => (
          <div key={stat.label} className="tb-summary-item">
            <p className="tb-summary-label">{stat.label}</p>
            <p className="tb-summary-value tb-num">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="tb-toolbar flex-wrap gap-y-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, domain, email, tax…"
          className="h-9 w-full max-w-md border-0 border-b border-[#b8c0b9] bg-transparent px-0 text-sm outline-none focus:border-[#e86f2a]"
        />
        {(
          [
            ["all", "All types"],
            ["buyer", "Buyers"],
            ["supplier", "Suppliers"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTypeFilter(key)}
            className="tb-filter"
            data-active={typeFilter === key}
          >
            {label}
          </button>
        ))}
        {(
          [
            ["all", "All statuses"],
            ["pending", "Pending"],
            ["verified", "Verified"],
            ["active", "Active"],
            ["suspended", "Suspended"],
            ["rejected", "Rejected"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setStatusFilter(key)}
            className="tb-filter"
            data-active={statusFilter === key}
          >
            {label}
          </button>
        ))}
        <select
          className="h-9 rounded-lg border border-[#d4e0da] bg-white px-2 text-sm"
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
        >
          <option value="updated">Sort: recent</option>
          <option value="name">Sort: name</option>
          <option value="type">Sort: type</option>
          <option value="status">Sort: status</option>
        </select>
        <select
          className="h-9 rounded-lg border border-[#d4e0da] bg-white px-2 text-sm"
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
        >
          {[10, 20, 50, 100].map((n) => (
            <option key={n} value={n}>
              {n} / page
            </option>
          ))}
        </select>
      </div>

      <div className="tb-cc-filters sm:grid-cols-2">
          <label className="block text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
            Company email domain
            <select
              className="mt-1.5 h-10 w-full rounded-lg border border-[#d4e0da] bg-white px-3 text-sm"
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value as DomainFilter)}
            >
              <option value="all">Any</option>
              <option value="has_domain">Has domain configured</option>
              <option value="missing_domain">Missing domain</option>
            </select>
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
            City / governorate contains
            <input
              value={cityNeedle}
              onChange={(e) => setCityNeedle(e.target.value)}
              placeholder="e.g. Beirut, Mount Lebanon…"
              className="mt-1.5 h-10 w-full rounded-lg border border-[#d4e0da] bg-white px-3 text-sm outline-none focus:border-[#e86f2a]"
            />
          </label>
        </div>

      <div className="tb-data mt-4">
        {loading ? (
          <LoadingEntity entity="businesses" className="py-12 justify-center" />
        ) : viewRows.length === 0 ? (
          <div className="tb-empty">
            <h3>No companies match this filter</h3>
            <p>Widen type or status, or clear advanced filters on this page.</p>
          </div>
        ) : (
          <ul>
            {viewRows.map((row) => {
              const open = expandedId === row.id;
              const pendingReview = row.verification_status === "pending";
              const profileHref = ROUTES.admin.businessDetail(row.id);
              return (
                <li key={row.id} className="tb-data-row tb-co-card grid-cols-1">
                  <div className="tb-co-card__body">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="tb-co-card__brand min-w-0">
                      <CompanyLogo url={row.logo_url} name={row.name} />
                      <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={profileHref}
                          className="font-semibold text-[#0c1612] hover:text-[#0d3b2a] hover:underline"
                        >
                          {row.name}
                        </Link>
                        {row.verification_status === "verified" ||
                        row.status === "verified" ? (
                          <VerifiedBadge verified label="Verified" />
                        ) : null}
                        <span className="tb-status" data-tone={statusTone(row.type)}>
                          {row.type}
                        </span>
                        {row.status !== "verified" ? (
                          <span className="tb-status" data-tone={statusTone(row.status)}>
                            {row.status}
                          </span>
                        ) : null}
                        {row.verification_status &&
                        row.verification_status !== "verified" ? (
                          <span
                            className="tb-status"
                            data-tone={statusTone(row.verification_status)}
                          >
                            {row.verification_status}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 text-sm text-[#5a6a62]">
                        {companyLocation(row)}
                        {row.email_domain ? (
                          <>
                            {" · "}
                            <span className="font-semibold text-[#0d3b2a]">@{row.email_domain}</span>
                          </>
                        ) : (
                          <span className="text-[#b42318]"> · No email domain</span>
                        )}
                        {row.contact_email ? ` · ${row.contact_email}` : ""}
                      </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {pendingReview ? (
                        <AdminAct href={ROUTES.admin.suppliers} tone="ghost">
                          Needs review
                        </AdminAct>
                      ) : null}
                      <AdminAct href={profileHref} tone="go" arrow>
                        Open profile
                      </AdminAct>
                      <AdminAct
                        tone="ghost"
                        onClick={() => setExpandedId(open ? null : row.id)}
                      >
                        {open ? "Hide" : "Quick view"}
                      </AdminAct>
                    </div>
                  </div>
                  {open ? (
                    <div className="mt-4 grid gap-3 border-t border-[#e8efeb] pt-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
                          Legal name
                        </p>
                        <p className="mt-1 text-[#0c1612]">{row.legal_name || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
                          Tax number
                        </p>
                        <p className="mt-1 text-[#0c1612]">{row.tax_number || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
                          Email domain
                        </p>
                        <p className="mt-1 text-[#0c1612]">{row.email_domain || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
                          Contact
                        </p>
                        <p className="mt-1 text-[#0c1612]">
                          {row.contact_email || "—"}
                          {row.contact_phone ? ` · ${row.contact_phone}` : ""}
                        </p>
                      </div>
                      <div className="sm:col-span-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
                          Address
                        </p>
                        <p className="mt-1 text-[#0c1612]">{formatBusinessAddress(row)}</p>
                      </div>
                    </div>
                  ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {total > 0 ? (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <p className="tb-meta">
            {total} matching · {viewRows.length} after page filters
          </p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}

      <AdminCreateBusinessModal
        open={createType !== null}
        accountType={createType ?? "buyer"}
        onClose={() => setCreateType(null)}
        onSubmit={async (payload) => {
          try {
            const result = await identityApi.createPlatformBusiness(payload);
            success(
              payload.account_type === "supplier" ? "Supplier created" : "Buyer created",
              result.business.name,
            );
            load();
          } catch (err) {
            const message =
              err instanceof ApiError ? err.message : "Could not create company.";
            toastError("Couldn't create", message);
            throw new Error(message);
          }
        }}
      />
    </AdminPage>
  );
}

export default function AdminBusinessesPage() {
  return (
    <PermissionGate
      permission="businesses.read"
      fallbackTitle="Business directory is restricted"
      fallbackDescription="Platform staff access is required to view companies."
    >
      <Suspense fallback={<LoadingEntity entity="directory" className="p-8" />}>
        <AdminBusinessesPageInner />
      </Suspense>
    </PermissionGate>
  );
}
