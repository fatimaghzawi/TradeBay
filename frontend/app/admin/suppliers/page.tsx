"use client";

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
import { verificationDocumentHref } from "@/lib/media";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type VerifyFilter =
  | "pending"
  | "all"
  | "verified"
  | "unverified"
  | "rejected"
  | "revoked";

function AdminSuppliersPageInner() {
  const { hasPermission } = useAuth();
  const canVerify = hasPermission("suppliers.verify");
  const { success, error: toastError } = useToast();
  const [rows, setRows] = useState<Business[]>([]);
  const [filter, setFilter] = useState<VerifyFilter>("pending");
  const [query, setQuery] = useState("");
  const [docsOnly, setDocsOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [queueCount, setQueueCount] = useState<number | null>(null);

  const load = useCallback(() => {
    setError(null);
    setLoading(true);
    const verification_status = filter === "all" ? undefined : filter;
    void identityApi
      .listPlatformSuppliers({
        verification_status,
        q: query.trim() || undefined,
        page,
        page_size: pageSize,
      })
      .then((result) => {
        const list = result.data;
        setRows(list);
        setTotal(result.meta.total);
        setExpandedId((current) => {
          if (current && list.some((r) => r.id === current)) return current;
          const firstPending = list.find((r) => r.verification_status === "pending");
          return firstPending?.id ?? list[0]?.id ?? null;
        });
      })
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load suppliers.",
        ),
      )
      .finally(() => setLoading(false));
  }, [filter, page, pageSize, query]);

  useEffect(() => {
    const handle = window.setTimeout(() => load(), query ? 280 : 0);
    return () => window.clearTimeout(handle);
  }, [load, query]);

  useEffect(() => {
    setPage(1);
  }, [filter, query, pageSize]);

  useEffect(() => {
    void identityApi
      .listPlatformSuppliers({ verification_status: "pending", page: 1, page_size: 1 })
      .then((r) => setQueueCount(r.meta.total))
      .catch(() => setQueueCount(null));
  }, [rows]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  const viewRows = useMemo(() => {
    if (!docsOnly) return rows;
    return rows.filter((r) => (r.verification_documents?.length ?? 0) > 0);
  }, [docsOnly, rows]);

  function review(
    businessId: string,
    decision: "approve" | "reject" | "revoke",
    reason?: string,
  ) {
    setBusyId(businessId);
    setError(null);
    void identityApi
      .reviewSupplierVerification(businessId, decision, reason)
      .then(() => {
        success(
          decision === "approve"
            ? "Supplier approved"
            : decision === "revoke"
              ? "Selling rights revoked"
              : "Supplier rejected",
          decision === "approve"
            ? "Selling rights are unlocked for this business."
            : decision === "revoke"
              ? "All of their products were taken offline. Buyers can no longer order them."
              : "Supplier can fix documents and resubmit.",
        );
        setRejectId(null);
        setRejectReason("");
        load();
      })
      .catch((err) => {
        const message =
          err instanceof ApiError ? err.message : `Unable to ${decision} supplier.`;
        setError(message);
        toastError("Review failed", message);
      })
      .finally(() => setBusyId(null));
  }

  function exportPage() {
    downloadPdf(
      `tradebay-suppliers-page-${page}.pdf`,
      [
        "id",
        "name",
        "company_status",
        "verification_status",
        "email_domain",
        "contact_email",
        "docs",
        "rejection_reason",
      ],
      viewRows.map((r) => [
        r.id,
        r.name,
        r.status || "",
        r.verification_status || "",
        r.email_domain || "",
        r.contact_email || "",
        String(r.verification_documents?.length ?? 0),
        r.rejection_reason || "",
      ]),
      {
        title: "TradeBay supplier verification",
        subtitle: `Page ${page} · ${viewRows.length} row(s)`,
      },
    );
    success("PDF exported", `${viewRows.length} suppliers`);
  }

  return (
    <AdminPage>
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.admin.home} className="hover:underline">
          Admin
        </Link>{" "}
        / Identity / Verification
      </p>
      <DirectoryMast
        title="Supplier verification"
        mark="Platform"
        size="page"
        actions={
          <div className="flex flex-wrap gap-2">
            <AdminAct tone="soft" onClick={exportPage} disabled={viewRows.length === 0}>
              Export PDF
            </AdminAct>
            <AdminAct
              href={`${ROUTES.admin.businesses}?type=supplier`}
              tone="go"
              arrow
            >
              Supplier directory
            </AdminAct>
          </div>
        }
      />

      <AdminIdentityNav />

      <div className="tb-summary">
        {[
          { label: "Queue (pending)", value: queueCount ?? "—" },
          { label: "Matching filter", value: total },
          { label: "This page", value: viewRows.length },
          {
            label: "With documents",
            value: rows.filter((r) => (r.verification_documents?.length ?? 0) > 0).length,
          },
        ].map((stat) => (
          <div key={stat.label} className="tb-summary-item">
            <p className="tb-summary-label">{stat.label}</p>
            <p className="tb-summary-value tb-num">{stat.value}</p>
          </div>
        ))}
      </div>

      {error ? (
        <FeedbackBanner tone="error" title="Supplier review error" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      <div className="tb-toolbar flex-wrap gap-y-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search supplier name, domain, email, tax…"
          className="h-9 w-full max-w-md border-0 border-b border-[#b8c0b9] bg-transparent px-0 text-sm outline-none focus:border-[#e86f2a]"
        />
        {(
          [
            ["pending", "Pending"],
            ["verified", "Verified"],
            ["unverified", "Unverified"],
            ["rejected", "Rejected"],
            ["revoked", "Revoked"],
            ["all", "All"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => {
              setFilter(key);
              setExpandedId(null);
            }}
            className="tb-filter"
            data-active={filter === key}
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          className="tb-filter"
          data-active={docsOnly}
          onClick={() => setDocsOnly((v) => !v)}
        >
          Has documents
        </button>
        <select
          className="h-9 rounded-lg border border-[#d4e0da] bg-white px-2 text-sm"
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
        >
          {[10, 20, 50].map((n) => (
            <option key={n} value={n}>
              {n} / page
            </option>
          ))}
        </select>
      </div>

      <div className="tb-data">
        {loading ? (
          <LoadingEntity entity="suppliers" className="py-12 justify-center" />
        ) : viewRows.length === 0 ? (
          <div className="tb-empty">
            <h3>
              {filter === "pending" ? "Verification queue is clear" : "No suppliers match"}
            </h3>
            <p>Adjust verification status or search to find supplier packages.</p>
          </div>
        ) : (
          <ul>
            {viewRows.map((row) => {
              const pending = row.verification_status === "pending";
              const verified = row.verification_status === "verified";
              const open = expandedId === row.id;
              const docs = row.verification_documents ?? [];
              const profileHref = ROUTES.admin.businessDetail(row.id);
              return (
                <li key={row.id} className="tb-data-row tb-co-card grid-cols-1">
                  <div className="tb-co-card__body">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="tb-co-card__brand min-w-0 text-left">
                      <CompanyLogo url={row.logo_url} name={row.name} />
                      <div className="min-w-0">
                      <Link
                        href={profileHref}
                        className="inline-flex items-center gap-2 font-semibold text-[#0c1612] hover:text-[#0d3b2a] hover:underline"
                      >
                        {row.name}
                        {verified ? <VerifiedBadge verified label="Verified" /> : null}
                      </Link>
                      <p className="mt-0.5 text-sm text-[#5a6a62]">
                        {companyLocation(row)}
                        {` · Company: ${row.status}`}
                        {row.verification_status &&
                        row.verification_status !== "verified"
                          ? ` · Profile: ${row.verification_status}`
                          : ""}
                        {row.email_domain ? ` · @${row.email_domain}` : ""}
                        {` · ${docs.length} doc${docs.length === 1 ? "" : "s"}`}
                      </p>
                      <AdminAct
                        tone="ghost"
                        onClick={() => setExpandedId(open ? null : row.id)}
                      >
                        {open ? "Hide details" : "Review package"}
                      </AdminAct>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <AdminAct href={profileHref} tone="ghost" arrow>
                        Open profile
                      </AdminAct>
                      {pending && canVerify ? (
                        <>
                          <AdminAct
                            tone="ok"
                            arrow
                            busy={busyId === row.id}
                            disabled={busyId === row.id}
                            onClick={() => {
                              if (
                                !window.confirm(`Approve ${row.name} for selling rights?`)
                              ) {
                                return;
                              }
                              review(row.id, "approve");
                            }}
                          >
                            {busyId === row.id ? "…" : "Approve"}
                          </AdminAct>
                          <AdminAct
                            tone="danger"
                            disabled={busyId === row.id}
                            onClick={() => {
                              setRejectId(row.id);
                              setRejectReason("");
                              setExpandedId(row.id);
                            }}
                          >
                            Reject
                          </AdminAct>
                        </>
                      ) : verified && canVerify ? (
                        <>
                          <VerifiedBadge verified size="md" label="Verified supplier" />
                          <AdminAct
                            tone="danger"
                            disabled={busyId === row.id}
                            busy={busyId === row.id}
                            onClick={() => {
                              if (
                                !window.confirm(
                                  `Revoke selling rights for ${row.name}? All of their products will be taken offline so buyers cannot order them.`,
                                )
                              ) {
                                return;
                              }
                              const reason = window.prompt(
                                "Reason for revoking selling rights (optional)",
                                "",
                              );
                              if (reason === null) return;
                              review(row.id, "revoke", reason.trim() || undefined);
                            }}
                          >
                            {busyId === row.id ? "…" : "Revoke selling rights"}
                          </AdminAct>
                        </>
                      ) : verified ? (
                        <VerifiedBadge verified size="md" label="Verified supplier" />
                      ) : (
                        <span
                          className="tb-status"
                          data-tone={statusTone(row.verification_status || row.status)}
                        >
                          {row.verification_status ?? row.status}
                        </span>
                      )}
                      {!canVerify && pending ? (
                        <span className="tb-meta">Need suppliers.verify to decide</span>
                      ) : null}
                    </div>
                  </div>

                  {open ? (
                    <div className="mt-4 space-y-4 rounded-xl bg-[#e8ebe6] p-4">
                      <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
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

                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">
                          Submitted documents ({docs.length})
                        </p>
                        {docs.length === 0 ? (
                          <p className="mt-2 text-sm text-[#5a6a62]">
                            No documents on file for this supplier.
                          </p>
                        ) : (
                          <ul className="mt-2 space-y-2">
                            {docs.map((doc, idx) => {
                              const href = verificationDocumentHref(doc.url);
                              return (
                              <li
                                key={`${doc.document_type}-${idx}`}
                                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#dce5e0] bg-white px-3 py-2 text-sm"
                              >
                                <div>
                                  <p className="font-semibold text-[#0c1612]">
                                    {doc.document_type || "Document"}
                                  </p>
                                  <p className="text-xs text-[#5a6a62]">
                                    {doc.file_name || "Untitled file"}
                                    {doc.uploaded_at
                                      ? ` · ${new Date(doc.uploaded_at).toLocaleString()}`
                                      : ""}
                                  </p>
                                </div>
                                {href ? (
                                  <a
                                    href={href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="rounded-lg bg-[#0d3b2a] px-3 py-1.5 text-xs font-semibold text-white"
                                  >
                                    Open file
                                  </a>
                                ) : (
                                  <span className="text-xs text-[#5a6a62]">
                                    File not stored — ask the supplier to resubmit
                                  </span>
                                )}
                              </li>
                              );
                            })}
                          </ul>
                        )}
                      </div>

                      {row.rejection_reason ? (
                        <p className="rounded-lg bg-[#fef3f2] px-3 py-2 text-sm text-[#b42318]">
                          Last rejection reason: {row.rejection_reason}
                        </p>
                      ) : null}

                      {rejectId === row.id ? (
                        <div className="space-y-2 rounded-xl border border-[#f3c1bb] bg-white p-3">
                          <label className="block text-sm font-semibold text-[#0c1612]">
                            Rejection reason
                            <textarea
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                              rows={3}
                              placeholder="Explain what the supplier must fix…"
                              className="mt-1.5 w-full rounded-xl border border-[#dce5e0] px-3 py-2 text-sm outline-none focus:border-[#e86f2a]/55 focus:ring-2 focus:ring-[#e86f2a]/15"
                            />
                          </label>
                          <div className="flex justify-end gap-2">
                            <AdminAct
                              tone="soft"
                              onClick={() => {
                                setRejectId(null);
                                setRejectReason("");
                              }}
                            >
                              Cancel
                            </AdminAct>
                            <AdminAct
                              tone="danger"
                              busy={busyId === row.id}
                              disabled={busyId === row.id || !rejectReason.trim()}
                              onClick={() => review(row.id, "reject", rejectReason.trim())}
                            >
                              Confirm reject
                            </AdminAct>
                          </div>
                        </div>
                      ) : null}
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
          <p className="tb-meta">{total} matching</p>
          <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
        </div>
      ) : null}
    </AdminPage>
  );
}

export default function AdminSuppliersPage() {
  return (
    <PermissionGate
      permission="suppliers.read"
      fallbackTitle="Supplier verification is restricted"
      fallbackDescription="Platform staff access is required to review suppliers."
    >
      <AdminSuppliersPageInner />
    </PermissionGate>
  );
}
