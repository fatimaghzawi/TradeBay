"use client";

import { AdminIdentityNav } from "@/components/admin/AdminIdentityNav";
import { AdminBusinessRolesPanel } from "@/components/admin/AdminBusinessRolesPanel";
import { AdminAct, AdminPage } from "@/components/admin/AdminUi";
import { AdminProductPhoto, productPrimaryImageUrl } from "@/components/admin/AdminProductPhoto";
import { SuspendAccountModal } from "@/components/admin/SuspendAccountModal";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { ChangeMemberRoleModal } from "@/components/team/ChangeMemberRoleModal";
import { AdminCompanyHero, companyInitials } from "@/components/company/CompanyBrand";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity } from "@/components/ui/LoadingState";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/Toast";
import {
  formatBusinessAddress,
  statusTone,
} from "@/lib/admin/identityDirectory";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Product } from "@/lib/api/catalogApi";
import {
  identityApi,
  type AuditEvent,
  type Business,
  type Member,
} from "@/lib/api/identityApi";
import type {
  PurchaseOrderSummary,
  RFQSummary,
} from "@/lib/api/procurementApi";
import { ROUTES } from "@/lib/constants";
import {
  auditHeadline,
  auditTone,
  formatAuditWhen,
} from "@/lib/identity/auditCopy";
import { mediaUrl, verificationDocumentHref } from "@/lib/media";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type ProfileTab = "overview" | "roles" | "products" | "orders" | "activity";
type ProductStatusFilter = "all" | "active" | "draft" | "inactive";
type OrderStatusFilter = "all" | "pending" | "confirmed" | "cancelled" | "completed";
type PurchaseSubView = "orders" | "rfqs";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-[#5a6a62]">{label}</p>
      <p className="mt-1 text-sm text-[#0c1612]">{value}</p>
    </div>
  );
}

function memberDisplayName(member: Member): string {
  const name = [member.first_name, member.last_name].filter(Boolean).join(" ").trim();
  return name || member.email || "Unknown member";
}

function productPriceLabel(product: Product): string {
  const tier = product.prices?.find((p) => p.is_active) ?? product.prices?.[0];
  if (!tier) return "No price";
  return `${tier.unit_price} ${tier.currency}`;
}

function productStockLabel(product: Product): string {
  if (!product.inventory) return "No stock row";
  return `${product.inventory.available_quantity} avail · ${product.inventory.reserved_quantity} reserved`;
}

export default function AdminBusinessProfilePage() {
  const params = useParams<{ id: string }>();
  const businessId = params.id;
  const { hasPermission, user: currentUser } = useAuth();
  const canSuspendUsers = hasPermission("users.update");
  const canVerify = hasPermission("suppliers.verify");
  const canReadProducts = hasPermission("products.read");
  const canReadOrders = hasPermission("orders.read");
  const canReadRfqs = hasPermission("rfqs.read");
  const canReadAudit = hasPermission("audit_logs.read");
  const canReadRoles = hasPermission("roles.read");
  const canManageRoles = hasPermission("roles.manage");
  const { success, error: toastError } = useToast();

  const [tab, setTab] = useState<ProfileTab>("overview");
  const [business, setBusiness] = useState<Business | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [membersPage, setMembersPage] = useState(1);
  const [membersTotal, setMembersTotal] = useState(0);
  const [memberQuery, setMemberQuery] = useState("");
  const [memberStatus, setMemberStatus] = useState<"all" | "active" | "suspended" | "invited">(
    "all",
  );
  const [suspendUserId, setSuspendUserId] = useState<string | null>(null);
  const [suspendLabel, setSuspendLabel] = useState("");
  const [roleMember, setRoleMember] = useState<Member | null>(null);
  const membersPageSize = 20;

  const [products, setProducts] = useState<Product[]>([]);
  const [productsTotal, setProductsTotal] = useState(0);
  const [productsPage, setProductsPage] = useState(1);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [productQuery, setProductQuery] = useState("");
  const [productStatus, setProductStatus] = useState<ProductStatusFilter>("all");
  const productsPageSize = 12;

  const [purchaseView, setPurchaseView] = useState<PurchaseSubView>("orders");
  const [orders, setOrders] = useState<PurchaseOrderSummary[]>([]);
  const [ordersTotal, setOrdersTotal] = useState(0);
  const [ordersPage, setOrdersPage] = useState(1);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [orderStatus, setOrderStatus] = useState<OrderStatusFilter>("all");
  const ordersPageSize = 12;

  const [rfqs, setRfqs] = useState<RFQSummary[]>([]);
  const [rfqsTotal, setRfqsTotal] = useState(0);
  const [rfqsPage, setRfqsPage] = useState(1);
  const [rfqsLoading, setRfqsLoading] = useState(false);
  const [rfqsError, setRfqsError] = useState<string | null>(null);
  const rfqsPageSize = 12;

  const [activity, setActivity] = useState<AuditEvent[]>([]);
  const [activityTotal, setActivityTotal] = useState(0);
  const [activityPage, setActivityPage] = useState(1);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  const activityPageSize = 20;

  const loadBusiness = useCallback(() => {
    if (!businessId) return;
    setError(null);
    setLoading(true);

    void identityApi
      .getPlatformBusiness(businessId)
      .then((item) => setBusiness(item))
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load this business profile.",
        ),
      )
      .finally(() => setLoading(false));
  }, [businessId]);

  const loadMembers = useCallback(() => {
    if (!businessId) return;
    setMembersError(null);
    setMembersLoading(true);

    void identityApi
      .listPlatformBusinessMembers(businessId, {
        page: membersPage,
        page_size: membersPageSize,
        status: memberStatus === "all" ? undefined : memberStatus,
        q: memberQuery.trim() || undefined,
      })
      .then((result) => {
        setMembers(result.data);
        setMembersTotal(result.meta.total);
      })
      .catch((err) =>
        setMembersError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load members for this business.",
        ),
      )
      .finally(() => setMembersLoading(false));
  }, [businessId, memberQuery, memberStatus, membersPage]);

  const loadProducts = useCallback(() => {
    if (!businessId || !canReadProducts) return;
    setProductsError(null);
    setProductsLoading(true);
    void catalogApi
      .listProducts({
        supplier_business_id: businessId,
        status: productStatus === "all" ? undefined : productStatus,
        q: productQuery.trim() || undefined,
        include_details: true,
        page: productsPage,
        page_size: productsPageSize,
      })
      .then((result) => {
        setProducts(result.data);
        setProductsTotal(result.meta.total);
      })
      .catch((err) =>
        setProductsError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load this company's products.",
        ),
      )
      .finally(() => setProductsLoading(false));
  }, [businessId, canReadProducts, productQuery, productStatus, productsPage]);

  const loadOrders = useCallback(() => {
    if (!businessId || !canReadOrders) return;
    setOrdersError(null);
    setOrdersLoading(true);
    void identityApi
      .listPlatformBusinessOrders(businessId, {
        status: orderStatus === "all" ? undefined : orderStatus,
        page: ordersPage,
        page_size: ordersPageSize,
      })
      .then((result) => {
        setOrders(result.data);
        setOrdersTotal(result.meta.total);
      })
      .catch((err) =>
        setOrdersError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load this company's purchase orders.",
        ),
      )
      .finally(() => setOrdersLoading(false));
  }, [businessId, canReadOrders, orderStatus, ordersPage]);

  const loadRfqs = useCallback(() => {
    if (!businessId || !canReadRfqs) return;
    setRfqsError(null);
    setRfqsLoading(true);
    void identityApi
      .listPlatformBusinessRfqs(businessId, {
        page: rfqsPage,
        page_size: rfqsPageSize,
      })
      .then((result) => {
        setRfqs(result.data);
        setRfqsTotal(result.meta.total);
      })
      .catch((err) =>
        setRfqsError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load this company's RFQs.",
        ),
      )
      .finally(() => setRfqsLoading(false));
  }, [businessId, canReadRfqs, rfqsPage]);

  const loadActivity = useCallback(() => {
    if (!businessId || !canReadAudit) return;
    setActivityError(null);
    setActivityLoading(true);
    void identityApi
      .listPlatformBusinessAuditLogs(businessId, {
        page: activityPage,
        page_size: activityPageSize,
      })
      .then((result) => {
        setActivity(result.data);
        setActivityTotal(result.meta.total);
      })
      .catch((err) =>
        setActivityError(
          err instanceof ApiError
            ? err.message
            : "Couldn't load company activity.",
        ),
      )
      .finally(() => setActivityLoading(false));
  }, [activityPage, businessId, canReadAudit]);

  useEffect(() => {
    loadBusiness();
  }, [loadBusiness]);

  // Prefetch totals for tab badges when profile + type are known.
  useEffect(() => {
    if (!businessId || !business) return;
    const isSupplierBiz = business.type === "supplier";
    const isBuyerBiz = business.type === "buyer";
    if (isSupplierBiz && canReadProducts) {
      void catalogApi
        .listProducts({
          supplier_business_id: businessId,
          page: 1,
          page_size: 1,
        })
        .then((result) => setProductsTotal(result.meta.total))
        .catch(() => undefined);
    }
    if (isBuyerBiz && canReadOrders) {
      void identityApi
        .listPlatformBusinessOrders(businessId, { page: 1, page_size: 1 })
        .then((result) => setOrdersTotal(result.meta.total))
        .catch(() => undefined);
    }
    if (isBuyerBiz && canReadRfqs) {
      void identityApi
        .listPlatformBusinessRfqs(businessId, { page: 1, page_size: 1 })
        .then((result) => setRfqsTotal(result.meta.total))
        .catch(() => undefined);
    }
    if (canReadAudit) {
      void identityApi
        .listPlatformBusinessAuditLogs(businessId, { page: 1, page_size: 1 })
        .then((result) => setActivityTotal(result.meta.total))
        .catch(() => undefined);
    }
  }, [business, businessId, canReadAudit, canReadOrders, canReadProducts, canReadRfqs]);

  useEffect(() => {
    const handle = window.setTimeout(() => loadMembers(), memberQuery ? 280 : 0);
    return () => window.clearTimeout(handle);
  }, [loadMembers, memberQuery]);

  useEffect(() => {
    setMembersPage(1);
  }, [memberQuery, memberStatus]);

  useEffect(() => {
    if (tab !== "products" || !canReadProducts) return;
    const handle = window.setTimeout(() => loadProducts(), productQuery ? 280 : 0);
    return () => window.clearTimeout(handle);
  }, [tab, canReadProducts, loadProducts, productQuery]);

  useEffect(() => {
    setProductsPage(1);
  }, [productQuery, productStatus]);

  useEffect(() => {
    if (tab !== "orders") return;
    if (purchaseView === "orders" && !canReadOrders && canReadRfqs) {
      setPurchaseView("rfqs");
      return;
    }
    if (purchaseView === "rfqs" && !canReadRfqs && canReadOrders) {
      setPurchaseView("orders");
      return;
    }
    if (purchaseView === "orders" && canReadOrders) loadOrders();
    if (purchaseView === "rfqs" && canReadRfqs) loadRfqs();
  }, [tab, purchaseView, canReadOrders, canReadRfqs, loadOrders, loadRfqs]);

  useEffect(() => {
    setOrdersPage(1);
  }, [orderStatus]);

  useEffect(() => {
    if (tab !== "activity" || !canReadAudit) return;
    loadActivity();
  }, [tab, canReadAudit, loadActivity]);

  // Leave commercial tabs that don't apply to this company type.
  useEffect(() => {
    if (!business) return;
    if (tab === "products" && business.type !== "supplier") setTab("overview");
    if (tab === "orders" && business.type !== "buyer") setTab("overview");
  }, [business, tab]);

  const membersPageCount = Math.max(1, Math.ceil(membersTotal / membersPageSize) || 1);
  const productsPageCount = Math.max(1, Math.ceil(productsTotal / productsPageSize) || 1);
  const ordersPageCount = Math.max(1, Math.ceil(ordersTotal / ordersPageSize) || 1);
  const rfqsPageCount = Math.max(1, Math.ceil(rfqsTotal / rfqsPageSize) || 1);
  const activityPageCount = Math.max(1, Math.ceil(activityTotal / activityPageSize) || 1);

  function reload() {
    loadBusiness();
    loadMembers();
    if (tab === "products") loadProducts();
    if (tab === "orders") {
      if (purchaseView === "orders") loadOrders();
      if (purchaseView === "rfqs") loadRfqs();
    }
    if (tab === "activity") loadActivity();
  }

  function review(decision: "approve" | "reject", reason?: string) {
    if (!businessId) return;
    setBusy(true);
    setError(null);
    void identityApi
      .reviewSupplierVerification(businessId, decision, reason)
      .then(() => {
        success(
          decision === "approve" ? "Supplier approved" : "Supplier rejected",
          decision === "approve"
            ? "Selling rights are unlocked for this business."
            : "Supplier can fix documents and resubmit.",
        );
        setRejectOpen(false);
        setRejectReason("");
        reload();
      })
      .catch((err) => {
        const message =
          err instanceof ApiError ? err.message : `Unable to ${decision} supplier.`;
        setError(message);
        toastError("Review failed", message);
      })
      .finally(() => setBusy(false));
  }

  const pending = business?.verification_status === "pending";
  const isSupplier = business?.type === "supplier";
  const isBuyer = business?.type === "buyer";
  const docs = business?.verification_documents ?? [];
  const canSeePurchases = canReadOrders || canReadRfqs;
  const purchasesTotal = ordersTotal + rfqsTotal;

  const tabs: { id: ProfileTab; label: string; hint?: string; locked?: boolean }[] = [
    { id: "overview", label: "Overview" },
    {
      id: "roles",
      label: "Roles",
      hint: canReadRoles ? undefined : "Access unavailable",
      locked: !canReadRoles,
    },
  ];
  if (isSupplier) {
    tabs.push({
      id: "products",
      label: "Products",
      hint: canReadProducts ? undefined : "Access unavailable",
      locked: !canReadProducts,
    });
  }
  if (isBuyer) {
    tabs.push({
      id: "orders",
      label: "Purchases",
      hint: canSeePurchases ? undefined : "Access unavailable",
      locked: !canSeePurchases,
    });
  }
  tabs.push({
    id: "activity",
    label: "Activity",
    hint: canReadAudit ? undefined : "Access unavailable",
    locked: !canReadAudit,
  });

  return (
    <AdminPage>
      <p className="tb-ov-crumb mb-3">
        <Link href={ROUTES.admin.businesses} className="hover:underline">
          Companies
        </Link>
        {isSupplier ? (
          <>
            {" "}
            /{" "}
            <Link href={ROUTES.admin.suppliers} className="hover:underline">
              Verification
            </Link>
          </>
        ) : null}{" "}
        / Profile
      </p>
      <DirectoryMast
        title={loading ? "Company profile" : business?.name || "Company profile"}
        mark="Platform"
        size="page"
      />

      <AdminIdentityNav />

      {error ? (
        <FeedbackBanner tone="error" title="Profile error" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      {loading ? (
        <LoadingEntity entity="profile" className="py-12 justify-center" />
      ) : !business ? (
        <div className="tb-empty">
          <h3>Business not found</h3>
          <p>This company may have been removed, or you may not have access.</p>
        </div>
      ) : (
        <>
          <AdminCompanyHero
            business={business}
            memberCount={membersTotal}
            badges={
              <>
                <span className="tb-status" data-tone={statusTone(business.type)}>
                  {business.type}
                </span>
                {business.status === "verified" ||
                business.verification_status === "verified" ? (
                  <VerifiedBadge verified size="md" label="Verified" />
                ) : null}
                {business.status !== "verified" ? (
                  <span className="tb-status" data-tone={statusTone(business.status)}>
                    {business.status}
                  </span>
                ) : null}
                {business.verification_status &&
                business.verification_status !== "verified" ? (
                  <span
                    className="tb-status"
                    data-tone={statusTone(business.verification_status)}
                  >
                    {business.verification_status}
                  </span>
                ) : null}
              </>
            }
            actions={
              isSupplier && pending && canVerify ? (
                <>
                  <AdminAct
                    tone="ok"
                    arrow
                    busy={busy}
                    disabled={busy}
                    onClick={() => review("approve")}
                  >
                    {busy ? "…" : "Approve supplier"}
                  </AdminAct>
                  <AdminAct
                    tone="danger"
                    disabled={busy}
                    onClick={() => {
                      setRejectOpen(true);
                      setRejectReason("");
                    }}
                  >
                    Reject
                  </AdminAct>
                </>
              ) : null
            }
          />

          <nav className="tb-admin-id-nav mt-5" aria-label="Company profile sections">
            <span className="tb-admin-id-nav__label">View</span>
            {tabs.map((item) => (
              <button
                key={item.id}
                type="button"
                data-active={tab === item.id}
                disabled={item.locked}
                title={item.hint}
                onClick={() => setTab(item.id)}
                className="disabled:cursor-not-allowed disabled:opacity-45"
              >
                {item.label}
                {item.id === "products" && canReadProducts && productsTotal > 0
                  ? ` (${productsTotal})`
                  : null}
                {item.id === "orders" && canSeePurchases && purchasesTotal > 0
                  ? ` (${purchasesTotal})`
                  : null}
                {item.id === "activity" && canReadAudit && activityTotal > 0
                  ? ` (${activityTotal})`
                  : null}
              </button>
            ))}
          </nav>

          {tab === "overview" ? (
            <>
              <div className="mt-2 grid gap-x-8 gap-y-4 border-b border-[#d4e0da] py-6 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Legal name" value={business.legal_name || "—"} />
                <Field label="Tax number" value={business.tax_number || "—"} />
                <Field label="Email domain" value={business.email_domain || "—"} />
                <Field
                  label="Contact"
                  value={
                    [business.contact_email, business.contact_phone].filter(Boolean).join(" · ") ||
                    "—"
                  }
                />
                <Field label="Website" value={business.website || "—"} />
                <Field label="Address" value={formatBusinessAddress(business)} />
                <Field
                  label="Created"
                  value={
                    business.created_at
                      ? new Date(business.created_at).toLocaleString()
                      : "—"
                  }
                />
                <Field
                  label="Updated"
                  value={
                    business.updated_at
                      ? new Date(business.updated_at).toLocaleString()
                      : "—"
                  }
                />
              </div>

              <section className="mt-8">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <h2 className="tb-section-label">Team members</h2>
                    <p className="mt-1 text-sm text-[#5a6a62]">
                      People with access to this company ({membersTotal}).
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <input
                      value={memberQuery}
                      onChange={(e) => setMemberQuery(e.target.value)}
                      placeholder="Search member name or email…"
                      className="h-9 w-full max-w-xs rounded-lg border border-[#d4e0da] px-3 text-sm outline-none focus:border-[#e86f2a]"
                    />
                    {(
                      [
                        ["all", "All"],
                        ["active", "Active"],
                        ["suspended", "Suspended"],
                        ["invited", "Invited"],
                      ] as const
                    ).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        className="tb-filter"
                        data-active={memberStatus === key}
                        onClick={() => setMemberStatus(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {membersError ? (
                  <FeedbackBanner
                    tone="error"
                    title="Couldn’t load members"
                    onDismiss={() => setMembersError(null)}
                  >
                    {membersError}
                  </FeedbackBanner>
                ) : null}

                {membersLoading ? (
                  <LoadingEntity entity="members" />
                ) : members.length === 0 ? (
                  <p className="mt-4 text-sm text-[#5a6a62]">No members match this filter.</p>
                ) : (
                  <>
                    <ul className="tb-data mt-3">
                      {members.map((member) => (
                        <li
                          key={member.id}
                          className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="tb-co-avatar" aria-hidden>
                              {business?.logo_url || member.avatar_url ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={mediaUrl(business?.logo_url || member.avatar_url)} alt="" />
                              ) : (
                                <span>{companyInitials(memberDisplayName(member))}</span>
                              )}
                            </div>
                            <div className="min-w-0">
                            <p className="font-semibold text-[#0c1612]">
                              {memberDisplayName(member)}
                            </p>
                            <p className="mt-0.5 text-sm text-[#5a6a62]">
                              {member.email || "No email"}
                              {member.role_name ? ` · ${member.role_name}` : ""}
                              {member.joined_at
                                ? ` · joined ${new Date(member.joined_at).toLocaleDateString()}`
                                : ""}
                            </p>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className="tb-status"
                              data-tone={statusTone(member.status)}
                            >
                              {member.status}
                            </span>
                            {member.user_status ? (
                              <span
                                className="tb-status"
                                data-tone={statusTone(member.user_status)}
                              >
                                user: {member.user_status}
                              </span>
                            ) : null}
                            <AdminAct href={ROUTES.admin.users} tone="ghost" arrow>
                              Find in Users
                            </AdminAct>
                            {canManageRoles && member.status === "active" ? (
                              <AdminAct tone="go" onClick={() => setRoleMember(member)}>
                                Change role
                              </AdminAct>
                            ) : null}
                            {canSuspendUsers &&
                            member.user_id &&
                            member.user_id !== currentUser?.id &&
                            member.user_status !== "suspended" ? (
                              <AdminAct
                                tone="danger"
                                onClick={() => {
                                  setSuspendUserId(member.user_id);
                                  setSuspendLabel(memberDisplayName(member));
                                }}
                              >
                                Suspend user
                              </AdminAct>
                            ) : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                    {membersTotal > 0 ? (
                      <Pagination
                        page={membersPage}
                        pageCount={membersPageCount}
                        onPageChange={setMembersPage}
                      />
                    ) : null}
                  </>
                )}
              </section>

              {isSupplier ? (
                <section className="mt-10">
                  <div>
                    <h2 className="tb-section-label">Verification documents</h2>
                    <p className="mt-2 text-sm text-[#4a5f55]">
                      Files submitted for supplier selling rights.
                    </p>
                  </div>

                  {docs.length === 0 ? (
                    <p className="mt-3 text-sm text-[#5a6a62]">No documents on file.</p>
                  ) : (
                    <ul className="tb-data mt-3">
                      {docs.map((doc, idx) => {
                        const href = verificationDocumentHref(doc.url);
                        return (
                        <li
                          key={`${doc.document_type}-${idx}`}
                          className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]"
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

                  {business.rejection_reason ? (
                    <p className="mt-3 rounded-xl bg-[#fef3f2] px-3 py-2 text-sm text-[#b42318]">
                      Last rejection reason: {business.rejection_reason}
                    </p>
                  ) : null}

                  {rejectOpen ? (
                    <div className="mt-3 space-y-2 rounded-xl border border-[#f3c1bb] bg-[#fffafa] p-3">
                      <label className="block text-sm font-semibold text-[#0c1612]">
                        Rejection reason
                        <textarea
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          rows={3}
                          placeholder="Explain what the supplier must fix…"
                          className="mt-1.5 w-full rounded-xl border border-[#dce5e0] bg-white px-3 py-2 text-sm outline-none focus:border-[#e86f2a]/55 focus:ring-2 focus:ring-[#e86f2a]/15"
                        />
                      </label>
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          className="h-9 rounded-xl px-3 text-sm font-semibold text-[#5a6a62] hover:bg-[#f3f6f4]"
                          onClick={() => {
                            setRejectOpen(false);
                            setRejectReason("");
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          disabled={busy || !rejectReason.trim()}
                          className="h-9 rounded-xl bg-[#b42318] px-3 text-sm font-semibold text-white disabled:opacity-60"
                          onClick={() => review("reject", rejectReason.trim())}
                        >
                          Confirm reject
                        </button>
                      </div>
                    </div>
                  ) : null}
                </section>
              ) : null}

              <section className="mt-10 grid gap-3 sm:grid-cols-2">
                {isSupplier && canReadProducts ? (
                  <button
                    type="button"
                    className="tb-panel p-4 text-left"
                    onClick={() => setTab("products")}
                  >
                    <p className="tb-section-label">Products</p>
                    <p className="mt-2 text-sm text-[#5a6a62]">
                      Open the full catalog for this supplier
                      {productsTotal > 0 ? ` (${productsTotal} listed)` : ""}.
                    </p>
                  </button>
                ) : null}
                {isBuyer && canSeePurchases ? (
                  <button
                    type="button"
                    className="tb-panel p-4 text-left"
                    onClick={() => setTab("orders")}
                  >
                    <p className="tb-section-label">Purchases &amp; orders</p>
                    <p className="mt-2 text-sm text-[#5a6a62]">
                      RFQs and purchase orders for this buyer
                      {purchasesTotal > 0
                        ? ` (${ordersTotal} orders · ${rfqsTotal} RFQs)`
                        : ""}
                      .
                    </p>
                  </button>
                ) : null}
                {canReadAudit ? (
                  <button
                    type="button"
                    className="tb-panel p-4 text-left"
                    onClick={() => setTab("activity")}
                  >
                    <p className="tb-section-label">Activity</p>
                    <p className="mt-2 text-sm text-[#5a6a62]">
                      Review identity and security events for this company.
                    </p>
                  </button>
                ) : null}
              </section>
            </>
          ) : null}

          {tab === "roles" && canReadRoles && business ? (
            <AdminBusinessRolesPanel
              businessId={businessId}
              businessName={business.name || "this company"}
            />
          ) : null}

          {tab === "products" && isSupplier && canReadProducts ? (
            <section className="mt-2">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h2 className="tb-section-label">Company products</h2>
                  <p className="mt-1 text-sm text-[#5a6a62]">
                    Full catalog for this supplier — including draft and inactive listings
                    ({productsTotal}).
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <input
                    value={productQuery}
                    onChange={(e) => setProductQuery(e.target.value)}
                    placeholder="Search product name…"
                    className="h-9 w-full max-w-xs rounded-lg border border-[#d4e0da] px-3 text-sm outline-none focus:border-[#e86f2a]"
                  />
                  {(
                    [
                      ["all", "All"],
                      ["active", "Active"],
                      ["draft", "Draft"],
                      ["inactive", "Inactive"],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className="tb-filter"
                      data-active={productStatus === key}
                      onClick={() => setProductStatus(key)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {productsError ? (
                <FeedbackBanner
                  tone="error"
                  title="Couldn’t load products"
                  onDismiss={() => setProductsError(null)}
                >
                  {productsError}
                </FeedbackBanner>
              ) : null}

              {productsLoading ? (
                <LoadingEntity entity="products" className="mt-4" />
              ) : products.length === 0 ? (
                <div className="tb-empty mt-4">
                  <h3>No products</h3>
                  <p>This company has no listings matching the current filter.</p>
                </div>
              ) : (
                <>
                  <ul className="tb-data mt-3">
                    {products.map((product) => (
                      <li
                        key={product.id}
                        className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]"
                      >
                        <div className="flex min-w-0 items-start gap-3">
                          <AdminProductPhoto
                            url={productPrimaryImageUrl(product)}
                            alt={product.name}
                          />
                          <div className="min-w-0">
                            <Link
                              href={ROUTES.admin.productDetail(product.id)}
                              className="font-semibold text-[#0c1612] hover:underline"
                            >
                              {product.name}
                            </Link>
                            <p className="mt-0.5 text-sm text-[#5a6a62]">
                              {product.sku}
                              {` · MOQ ${product.moq} ${product.unit}`}
                              {` · ${productPriceLabel(product)}`}
                              {` · ${productStockLabel(product)}`}
                            </p>
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className="tb-status"
                            data-tone={statusTone(product.status)}
                          >
                            {product.status}
                          </span>
                          <AdminAct
                            href={ROUTES.admin.productDetail(product.id)}
                            tone="go"
                            arrow
                          >
                            Open product
                          </AdminAct>
                        </div>
                      </li>
                    ))}
                  </ul>
                  {productsTotal > 0 ? (
                    <Pagination
                      page={productsPage}
                      pageCount={productsPageCount}
                      onPageChange={setProductsPage}
                    />
                  ) : null}
                </>
              )}
            </section>
          ) : null}

          {tab === "orders" && isBuyer && canSeePurchases ? (
            <section className="mt-2">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h2 className="tb-section-label">Purchases &amp; orders</h2>
                  <p className="mt-1 text-sm text-[#5a6a62]">
                    Buyer procurement trail — RFQs and purchase orders for this company.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {canReadOrders ? (
                    <button
                      type="button"
                      className="tb-filter"
                      data-active={purchaseView === "orders"}
                      onClick={() => setPurchaseView("orders")}
                    >
                      Orders{ordersTotal > 0 ? ` (${ordersTotal})` : ""}
                    </button>
                  ) : null}
                  {canReadRfqs ? (
                    <button
                      type="button"
                      className="tb-filter"
                      data-active={purchaseView === "rfqs"}
                      onClick={() => setPurchaseView("rfqs")}
                    >
                      RFQs{rfqsTotal > 0 ? ` (${rfqsTotal})` : ""}
                    </button>
                  ) : null}
                </div>
              </div>

              {purchaseView === "orders" && canReadOrders ? (
                <>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {(
                      [
                        ["all", "All"],
                        ["pending", "Pending"],
                        ["confirmed", "Confirmed"],
                        ["completed", "Completed"],
                        ["cancelled", "Cancelled"],
                      ] as const
                    ).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        className="tb-filter"
                        data-active={orderStatus === key}
                        onClick={() => setOrderStatus(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>

                  {ordersError ? (
                    <FeedbackBanner
                      tone="error"
                      title="Couldn’t load orders"
                      onDismiss={() => setOrdersError(null)}
                    >
                      {ordersError}
                    </FeedbackBanner>
                  ) : null}

                  {ordersLoading ? (
                    <LoadingEntity entity="purchase orders" />
                  ) : orders.length === 0 ? (
                    <div className="tb-empty mt-4">
                      <h3>No purchase orders</h3>
                      <p>This buyer has no orders matching the current filter.</p>
                    </div>
                  ) : (
                    <>
                      <ul className="tb-data mt-3">
                        {orders.map((order) => (
                          <li
                            key={order.id}
                            className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]"
                          >
                            <div>
                              <p className="font-semibold text-[#0c1612]">
                                {order.order_number || "Purchase order"}
                              </p>
                              <p className="mt-0.5 text-sm text-[#5a6a62]">
                                {order.total} {order.currency}
                                {order.created_at
                                  ? ` · ${new Date(order.created_at).toLocaleString()}`
                                  : ""}
                              </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className="tb-status"
                                data-tone={statusTone(order.status)}
                              >
                                {order.status}
                              </span>
                              <AdminAct href={ROUTES.procurementOrder(order.id)} tone="go" arrow>
                                Open order
                              </AdminAct>
                              {order.supplier_business_id ? (
                                <AdminAct
                                  href={ROUTES.admin.businessDetail(order.supplier_business_id)}
                                  tone="ghost"
                                >
                                  Supplier
                                </AdminAct>
                              ) : null}
                            </div>
                          </li>
                        ))}
                      </ul>
                      {ordersTotal > 0 ? (
                        <Pagination
                          page={ordersPage}
                          pageCount={ordersPageCount}
                          onPageChange={setOrdersPage}
                        />
                      ) : null}
                    </>
                  )}
                </>
              ) : null}

              {purchaseView === "rfqs" && canReadRfqs ? (
                <>
                  {rfqsError ? (
                    <FeedbackBanner
                      tone="error"
                      title="Couldn’t load RFQs"
                      onDismiss={() => setRfqsError(null)}
                    >
                      {rfqsError}
                    </FeedbackBanner>
                  ) : null}

                  {rfqsLoading ? (
                    <LoadingEntity entity="RFQs" />
                  ) : rfqs.length === 0 ? (
                    <div className="tb-empty mt-4">
                      <h3>No RFQs</h3>
                      <p>This buyer has not created any purchase requests yet.</p>
                    </div>
                  ) : (
                    <>
                      <ul className="tb-data mt-3">
                        {rfqs.map((rfq) => (
                          <li
                            key={rfq.id}
                            className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]"
                          >
                            <div>
                              <p className="font-semibold text-[#0c1612]">
                                {rfq.title || rfq.rfq_number || "RFQ"}
                              </p>
                              <p className="mt-0.5 text-sm text-[#5a6a62]">
                                {rfq.rfq_number}
                                {` · ${rfq.currency}`}
                                {` · ${rfq.invite_count} invite${rfq.invite_count === 1 ? "" : "s"}`}
                                {` · ${rfq.quotation_count} quote${rfq.quotation_count === 1 ? "" : "s"}`}
                                {rfq.created_at
                                  ? ` · ${new Date(rfq.created_at).toLocaleString()}`
                                  : ""}
                              </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="tb-status" data-tone={statusTone(rfq.status)}>
                                {rfq.status}
                              </span>
                              <AdminAct href={ROUTES.procurementRfq(rfq.id)} tone="go" arrow>
                                Open RFQ
                              </AdminAct>
                            </div>
                          </li>
                        ))}
                      </ul>
                      {rfqsTotal > 0 ? (
                        <Pagination
                          page={rfqsPage}
                          pageCount={rfqsPageCount}
                          onPageChange={setRfqsPage}
                        />
                      ) : null}
                    </>
                  )}
                </>
              ) : null}
            </section>
          ) : null}

          {tab === "activity" && canReadAudit ? (
            <section className="mt-2">
              <div>
                <h2 className="tb-section-label">Company activity</h2>
                <p className="mt-1 text-sm text-[#5a6a62]">
                  Identity and security events for this company ({activityTotal}).
                </p>
              </div>

              {activityError ? (
                <FeedbackBanner
                  tone="error"
                  title="Couldn’t load activity"
                  onDismiss={() => setActivityError(null)}
                >
                  {activityError}
                </FeedbackBanner>
              ) : null}

              {activityLoading ? (
                <LoadingEntity entity="activity" />
              ) : activity.length === 0 ? (
                <div className="tb-empty mt-4">
                  <h3>No activity yet</h3>
                  <p>Events will appear here as the company team works in TradeBay.</p>
                </div>
              ) : (
                <>
                  <ul className="tb-data mt-3">
                    {activity.map((event) => {
                      const tone = auditTone(event);
                      return (
                        <li
                          key={event.id}
                          className="tb-data-row grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto]"
                        >
                          <div>
                            <p className="font-semibold text-[#0c1612]">
                              {auditHeadline(event)}
                            </p>
                            <p className="mt-0.5 text-sm text-[#5a6a62]">
                              {event.action || "action"}
                              {event.resource_type ? ` · ${event.resource_type}` : ""}
                              {event.ip_address ? ` · ${event.ip_address}` : ""}
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className="tb-status"
                              data-tone={
                                tone === "ok" ? "ok" : tone === "warn" ? "bad" : "wait"
                              }
                            >
                              {formatAuditWhen(event.created_at)}
                            </span>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                  {activityTotal > 0 ? (
                    <Pagination
                      page={activityPage}
                      pageCount={activityPageCount}
                      onPageChange={setActivityPage}
                    />
                  ) : null}
                </>
              )}
            </section>
          ) : null}
        </>
      )}

      <SuspendAccountModal
        open={Boolean(suspendUserId)}
        title="Suspend account"
        subjectLabel={suspendLabel || "user"}
        confirmLabel="Suspend account"
        onClose={() => {
          setSuspendUserId(null);
          setSuspendLabel("");
        }}
        onConfirm={async (reason) => {
          if (!suspendUserId) return;
          try {
            await identityApi.suspendPlatformUser(suspendUserId, reason);
            success("Account suspended", `${suspendLabel} was signed out of all sessions.`);
            setSuspendUserId(null);
            loadMembers();
          } catch (err) {
            throw new Error(
              err instanceof ApiError ? err.message : "Suspension failed.",
            );
          }
        }}
      />
      <ChangeMemberRoleModal
        open={Boolean(roleMember)}
        member={roleMember}
        businessId={businessId}
        onClose={() => setRoleMember(null)}
        onUpdated={loadMembers}
      />
    </AdminPage>
  );
}
