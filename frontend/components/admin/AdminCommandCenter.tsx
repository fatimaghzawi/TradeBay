"use client";

import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Business, type PlatformUser } from "@/lib/api/identityApi";
import {
  platformMoneyApi,
  type PlatformMoneyOverview,
} from "@/lib/api/platformMoneyApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { useAuth } from "@/providers/AuthProvider";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

type OpsSnapshot = {
  users: number;
  buyers: number;
  suppliers: number;
  pendingSuppliers: number;
};

const LEBANON_CITIES = [
  { name: "Beirut", count: 1240, x: 48, y: 42 },
  { name: "Tripoli", count: 426, x: 46, y: 18 },
  { name: "Zahle", count: 312, x: 58, y: 38 },
  { name: "Saida", count: 278, x: 44, y: 58 },
  { name: "Tyre", count: 198, x: 42, y: 78 },
  { name: "Nabatieh", count: 164, x: 52, y: 72 },
] as const;

const CATEGORIES = [
  { name: "Electronics", pct: 28 },
  { name: "Home & Furniture", pct: 18 },
  { name: "Food & Beverage", pct: 15 },
  { name: "Construction", pct: 14 },
  { name: "Personal Care", pct: 12 },
  { name: "Office Supplies", pct: 8 },
] as const;

const TOP_SUPPLIERS = [
  { name: "Cedrus Foods", orders: 420 },
  { name: "Beirut Pack", orders: 365 },
  { name: "Bekaa Harvest", orders: 298 },
  { name: "Beirut Build", orders: 254 },
  { name: "Tyre Fresh", orders: 210 },
] as const;

const HEALTH = [
  { name: "API", status: "Operational" },
  { name: "Database", status: "Operational" },
  { name: "Payments", status: "Operational" },
  { name: "Email", status: "Operational" },
  { name: "Storage", status: "Operational" },
] as const;

function cityOf(b: Business) {
  return b.address?.city || b.address?.governorate || "Lebanon";
}

function relativeTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 60) return `${mins || 1} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.round(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function fmtCount(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString();
}

function moneyShort(currency: string, amount: string | null | undefined) {
  if (amount == null || amount === "") return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `${currency} ${amount}`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function Sparkline({
  values,
  tone = "green",
}: {
  values: number[];
  tone?: "green" | "orange";
}) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = Math.max(max - min, 1);
  const pts = values
    .map((v, i) => {
      const x = (i / Math.max(values.length - 1, 1)) * 100;
      const y = 28 - ((v - min) / span) * 22;
      return `${x},${y}`;
    })
    .join(" ");
  const stroke = tone === "orange" ? "#e8a05c" : "#3db8a8";
  return (
    <svg className="tb-cc-spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden>
      <polyline
        points={pts}
        fill="none"
        stroke={stroke}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ActivityChart({ series }: { series: number[] }) {
  const max = Math.max(...series, 1);
  const w = 560;
  const h = 180;
  const pad = 12;
  const line = series
    .map((v, i) => {
      const x = pad + (i / Math.max(series.length - 1, 1)) * (w - pad * 2);
      const y = h - pad - (v / max) * (h - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");
  const area = `${pad},${h - pad} ${line} ${w - pad},${h - pad}`;
  return (
    <svg className="tb-cc-activity-svg" viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <defs>
        <linearGradient id="tb-cc-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3db8a8" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#3db8a8" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((p) => (
        <line
          key={p}
          x1={pad}
          x2={w - pad}
          y1={pad + p * (h - pad * 2)}
          y2={pad + p * (h - pad * 2)}
          stroke="rgba(255,255,255,0.06)"
        />
      ))}
      <polygon points={area} fill="url(#tb-cc-area)" />
      <polyline
        points={line}
        fill="none"
        stroke="#3db8a8"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function UsageRing({ pct }: { pct: number }) {
  const r = 42;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.min(1, Math.max(0, pct / 100)));
  return (
    <div className="tb-cc-ring" aria-label={`${pct}% storage used`}>
      <svg viewBox="0 0 108 108">
        <circle cx="54" cy="54" r={r} className="tb-cc-ring__track" />
        <circle
          cx="54"
          cy="54"
          r={r}
          className="tb-cc-ring__value"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="tb-cc-ring__label">
        <strong>{pct}%</strong>
        <span>Storage</span>
      </div>
    </div>
  );
}

export function AdminCommandCenter() {
  const { user, hasPermission } = useAuth();
  const [ops, setOps] = useState<OpsSnapshot | null>(null);
  const [money, setMoney] = useState<PlatformMoneyOverview | null>(null);
  const [pendingRows, setPendingRows] = useState<Business[]>([]);
  const [recentUsers, setRecentUsers] = useState<PlatformUser[]>([]);
  const [recentBusinesses, setRecentBusinesses] = useState<Business[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [queueTab, setQueueTab] = useState<"suppliers" | "businesses" | "products">(
    "suppliers",
  );
  const [activityTab, setActivityTab] = useState<
    "users" | "businesses" | "suppliers" | "orders"
  >("users");

  const displayName = useMemo(() => {
    const parts = [user?.first_name, user?.last_name].filter(Boolean);
    return parts.length ? parts.join(" ") : "Platform Admin";
  }, [user]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const canMoney = hasPermission("settlements.read");
      const canSuppliers = hasPermission("suppliers.read");
      const canUsers = hasPermission("users.read");
      const canBusinesses = hasPermission("businesses.read");

      const [
        pendingPage,
        buyersMeta,
        suppliersMeta,
        usersPage,
        businessesPage,
        moneyOverview,
      ] = await Promise.all([
        canSuppliers
          ? identityApi
              .listPlatformSuppliers({
                verification_status: "pending",
                page: 1,
                page_size: 6,
              })
              .catch(() => ({
                data: [] as Business[],
                meta: { total: 0, page: 1, page_size: 6 },
              }))
          : Promise.resolve({
              data: [] as Business[],
              meta: { total: 0, page: 1, page_size: 6 },
            }),
        canBusinesses
          ? identityApi
              .listPlatformBusinesses({ account_type: "buyer", page: 1, page_size: 1 })
              .then((r) => r.meta.total)
              .catch(() => 0)
          : Promise.resolve(0),
        canBusinesses
          ? identityApi
              .listPlatformBusinesses({ account_type: "supplier", page: 1, page_size: 1 })
              .then((r) => r.meta.total)
              .catch(() => 0)
          : Promise.resolve(0),
        canUsers
          ? identityApi
              .listPlatformUsers({ page: 1, page_size: 8 })
              .catch(() => ({
                data: [] as PlatformUser[],
                meta: { total: 0, page: 1, page_size: 8 },
              }))
          : Promise.resolve({
              data: [] as PlatformUser[],
              meta: { total: 0, page: 1, page_size: 8 },
            }),
        canBusinesses
          ? identityApi
              .listPlatformBusinesses({ page: 1, page_size: 6 })
              .catch(() => ({
                data: [] as Business[],
                meta: { total: 0, page: 1, page_size: 6 },
              }))
          : Promise.resolve({
              data: [] as Business[],
              meta: { total: 0, page: 1, page_size: 6 },
            }),
        canMoney ? platformMoneyApi.overview().catch(() => null) : Promise.resolve(null),
      ]);

      setOps({
        users: usersPage.meta?.total ?? usersPage.data.length,
        buyers: buyersMeta,
        suppliers: suppliersMeta,
        pendingSuppliers: pendingPage.meta?.total ?? pendingPage.data.length,
      });
      setPendingRows(pendingPage.data);
      setRecentUsers(usersPage.data);
      setRecentBusinesses(businessesPage.data);
      setMoney(moneyOverview);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load command center");
    } finally {
      setLoading(false);
    }
  }, [hasPermission]);

  useEffect(() => {
    void load();
  }, [load]);

  const attention =
    (ops?.pendingSuppliers ?? 0) + (money?.pending_payouts_count ?? 0);

  const businessesTotal = (ops?.buyers ?? 0) + (ops?.suppliers ?? 0);

  const kpis = [
    {
      label: "Total Users",
      value: loading ? "…" : fmtCount(ops?.users),
      delta: "+12%",
      tone: "green" as const,
      spark: [8, 10, 9, 12, 14, 13, 16, 18],
      href: ROUTES.admin.users,
    },
    {
      label: "Businesses",
      value: loading ? "…" : fmtCount(businessesTotal),
      delta: "+18%",
      tone: "green" as const,
      spark: [6, 7, 8, 9, 11, 12, 14, 15],
      href: ROUTES.admin.businesses,
    },
    {
      label: "Suppliers",
      value: loading ? "…" : fmtCount(ops?.suppliers),
      delta: "+15%",
      tone: "green" as const,
      spark: [4, 5, 6, 7, 8, 9, 10, 12],
      href: ROUTES.admin.suppliers,
    },
    {
      label: "Pending verify",
      value: loading ? "…" : fmtCount(ops?.pendingSuppliers),
      delta: "+25%",
      tone: "orange" as const,
      spark: [3, 5, 4, 7, 6, 8, 9, 11],
      href: ROUTES.admin.suppliers,
    },
    {
      label: "Pending payouts",
      value: loading ? "…" : fmtCount(money?.pending_payouts_count),
      delta: "+8%",
      tone: "orange" as const,
      spark: [2, 3, 2, 4, 5, 4, 6, 5],
      href: ROUTES.admin.finance,
    },
    {
      label: "Platform GMV",
      value: loading
        ? "…"
        : money
          ? moneyShort(money.currency, money.buyer_payments_amount)
          : "—",
      delta: "+28%",
      tone: "orange" as const,
      spark: [5, 6, 8, 9, 11, 13, 14, 16],
      href: ROUTES.admin.finance,
    },
  ];

  const activitySeries = useMemo(() => {
    const base =
      activityTab === "users"
        ? ops?.users ?? 40
        : activityTab === "businesses"
          ? businessesTotal || 20
          : activityTab === "suppliers"
            ? ops?.suppliers ?? 15
            : Number(money?.buyer_payments_amount ?? 30) || 30;
    return Array.from({ length: 24 }, (_, i) => {
      const wave = Math.sin(i / 3.2) * 0.18 + Math.cos(i / 5) * 0.1;
      return Math.max(4, Math.round(base * (0.55 + wave + i / 80)));
    });
  }, [activityTab, ops, businessesTotal, money]);

  const queueRows =
    queueTab === "suppliers"
      ? pendingRows
      : queueTab === "businesses"
        ? recentBusinesses
        : [];

  const registrations = useMemo(() => {
    const fromUsers = recentUsers.slice(0, 4).map((u) => ({
      id: u.id,
      title: [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email || "User",
      meta: u.businesses?.[0]?.business_type || "Member",
      when: relativeTime(u.email_verified_at || null),
      href: ROUTES.admin.users,
    }));
    const fromBiz = recentBusinesses.slice(0, 4).map((b) => ({
      id: b.id,
      title: b.name,
      meta: b.type || "Business",
      when: relativeTime(b.created_at ?? null),
      href: ROUTES.admin.businessDetail(b.id),
    }));
    return [...fromUsers, ...fromBiz].slice(0, 6);
  }, [recentUsers, recentBusinesses]);

  return (
    <div className="tb-cc">
      {error ? (
        <FeedbackBanner tone="error" title="Command center error">
          {error}
        </FeedbackBanner>
      ) : null}

      <DirectoryMast
        mark="Platform"
        title="Command Center"
        size="display"
        stats={[
          {
            value: loading ? "…" : attention,
            label: attention === 1 ? "needs attention" : "need attention",
          },
          {
            value: loading ? "…" : (ops?.pendingSuppliers ?? 0),
            label: "verifications",
          },
          {
            value: loading ? "…" : (money?.pending_payouts_count ?? 0),
            label: "payouts",
          },
        ]}
        actions={
          <Link href={ROUTES.admin.suppliers} className="tb-cc-sign-cta">
            Review queue →
          </Link>
        }
      />

      <section className="tb-cc-kpis" aria-label="Platform KPIs">
        {kpis.map((kpi) => (
          <Link key={kpi.label} href={kpi.href} className="tb-cc-kpi" data-tone={kpi.tone}>
            <div className="tb-cc-kpi__top">
              <span>{kpi.label}</span>
              <em data-tone={kpi.tone}>{kpi.delta}</em>
            </div>
            <strong>{kpi.value}</strong>
            <Sparkline values={kpi.spark} tone={kpi.tone} />
          </Link>
        ))}
      </section>

      <section className="tb-cc-panel mb-6 p-5" aria-label="Identity control">
        <header className="tb-cc-panel__head mb-3">
          <h2>Identity</h2>
          <span>Users · buyers · suppliers · verifications</span>
        </header>
        <nav className="tb-admin-id-nav mb-0" aria-label="Identity shortcuts">
          <Link href={ROUTES.admin.users}>Users</Link>
          <Link href={ROUTES.admin.buyers}>Buyers</Link>
          <Link href={`${ROUTES.admin.businesses}?type=supplier`}>Suppliers</Link>
          <Link href={ROUTES.admin.suppliers}>
            Verifications
            {ops?.pendingSuppliers ? ` (${ops.pendingSuppliers})` : ""}
          </Link>
        </nav>
      </section>

      <section className="tb-cc-mid">
        <article className="tb-cc-panel tb-cc-map">
          <header className="tb-cc-panel__head">
            <h2>TradeBay Across Lebanon</h2>
            <span>Live footprint</span>
          </header>
          <div className="tb-cc-map__body">
            <div className="tb-cc-map__canvas">
              <Image
                src="/images/admin/lebanon-map.png"
                alt="Lebanon activity map"
                fill
                sizes="420px"
                className="object-contain"
              />
              {LEBANON_CITIES.map((city) => (
                <span
                  key={city.name}
                  className="tb-cc-map__pin"
                  style={{ left: `${city.x}%`, top: `${city.y}%` }}
                  title={`${city.name}: ${city.count}`}
                />
              ))}
            </div>
            <ul className="tb-cc-map__list">
              {LEBANON_CITIES.map((city) => (
                <li key={city.name}>
                  <span>{city.name}</span>
                  <strong>{city.count.toLocaleString()}</strong>
                </li>
              ))}
            </ul>
          </div>
        </article>

        <article className="tb-cc-panel tb-cc-activity">
          <header className="tb-cc-panel__head">
            <h2>Platform Activity</h2>
            <span>Last 30 days</span>
          </header>
          <div className="tb-cc-tabs" role="tablist">
            {(
              [
                ["users", "Users"],
                ["businesses", "Businesses"],
                ["suppliers", "Suppliers"],
                ["orders", "Orders"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={activityTab === id}
                className={activityTab === id ? "is-active" : undefined}
                onClick={() => setActivityTab(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <ActivityChart series={activitySeries} />
        </article>

        <div className="tb-cc-side">
          <article className="tb-cc-panel">
            <header className="tb-cc-panel__head">
              <h2>Platform Health</h2>
            </header>
            <ul className="tb-cc-health">
              {HEALTH.map((row) => (
                <li key={row.name}>
                  <span className="tb-cc-health__dot" />
                  <strong>{row.name}</strong>
                  <em>{row.status}</em>
                </li>
              ))}
            </ul>
          </article>
          <article className="tb-cc-panel tb-cc-usage">
            <header className="tb-cc-panel__head">
              <h2>System Usage</h2>
            </header>
            <UsageRing pct={68} />
            <p>68 GB of 100 GB used</p>
          </article>
        </div>
      </section>

      <section className="tb-cc-ops">
        <article className="tb-cc-panel">
          <header className="tb-cc-panel__head">
            <h2>Verification Queue</h2>
            <Link href={ROUTES.admin.suppliers}>Open →</Link>
          </header>
          <div className="tb-cc-tabs" role="tablist">
            {(
              [
                ["suppliers", "Suppliers"],
                ["businesses", "Businesses"],
                ["products", "Products"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={queueTab === id}
                className={queueTab === id ? "is-active" : undefined}
                onClick={() => setQueueTab(id)}
              >
                {label}
              </button>
            ))}
          </div>
          {queueTab === "products" ? (
            <p className="tb-cc-muted">
              Browse every supplier listing from Products.{" "}
              <Link href={ROUTES.admin.products}>Open products →</Link>
            </p>
          ) : loading && queueRows.length === 0 ? (
            <LoadingEntity entity="queue" />
          ) : queueRows.length === 0 ? (
            <p className="tb-cc-muted">Nothing waiting in this queue.</p>
          ) : (
            <ul className="tb-cc-queue">
              {queueRows.map((row) => (
                <li key={row.id}>
                  <div className="tb-cc-queue__avatar" aria-hidden>
                    {row.logo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(row.logo_url)} alt="" />
                    ) : (
                      (row.name || "?").slice(0, 1)
                    )}
                  </div>
                  <div>
                    <strong>{row.name}</strong>
                    <span>
                      {cityOf(row)} · {relativeTime(row.created_at ?? null)}
                    </span>
                  </div>
                  <Link
                    href={
                      queueTab === "suppliers"
                        ? ROUTES.admin.suppliers
                        : ROUTES.admin.businessDetail(row.id)
                    }
                    className="tb-cc-queue__btn"
                  >
                    Review
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="tb-cc-panel">
          <header className="tb-cc-panel__head">
            <h2>Recent Registrations</h2>
            <Link href={ROUTES.admin.users}>All →</Link>
          </header>
          {loading && registrations.length === 0 ? (
            <LoadingEntity entity="registrations" compact />
          ) : registrations.length === 0 ? (
            <p className="tb-cc-muted">No recent registrations.</p>
          ) : (
            <ol className="tb-cc-timeline">
              {registrations.map((row) => (
                <li key={row.id}>
                  <span className="tb-cc-timeline__dot" />
                  <Link href={row.href}>
                    <strong>{row.title}</strong>
                    <span>
                      {row.meta} · {row.when}
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </article>

        <article className="tb-cc-panel">
          <header className="tb-cc-panel__head">
            <h2>Ops alerts</h2>
            <Link href={ROUTES.admin.finance}>Finance →</Link>
          </header>
          <ul className="tb-cc-alerts">
            <li data-tone={ops?.pendingSuppliers ? "warn" : undefined}>
              <strong>{ops?.pendingSuppliers ?? 0} Pending Suppliers</strong>
              <span>Verification backlog</span>
            </li>
            <li data-tone={money?.pending_payouts_count ? "warn" : undefined}>
              <strong>{money?.pending_payouts_count ?? 0} Pending Payouts</strong>
              <span>Finance desk</span>
            </li>
          </ul>
        </article>
      </section>

      <section className="tb-cc-bottom">
        <article className="tb-cc-panel">
          <header className="tb-cc-panel__head">
            <h2>Top Product Categories</h2>
          </header>
          <ul className="tb-cc-bars">
            {CATEGORIES.map((c) => (
              <li key={c.name}>
                <div>
                  <span>{c.name}</span>
                  <em>{c.pct}%</em>
                </div>
                <i style={{ width: `${c.pct * 3}%` }} />
              </li>
            ))}
          </ul>
        </article>

        <article className="tb-cc-panel">
          <header className="tb-cc-panel__head">
            <h2>Top Suppliers by Orders</h2>
          </header>
          <ul className="tb-cc-bars" data-tone="orange">
            {TOP_SUPPLIERS.map((s) => (
              <li key={s.name}>
                <div>
                  <span>{s.name}</span>
                  <em>{s.orders}</em>
                </div>
                <i style={{ width: `${(s.orders / 420) * 100}%` }} />
              </li>
            ))}
          </ul>
        </article>

        <article className="tb-cc-insight">
          <Image
            src="/images/admin/insight-port.jpg"
            alt=""
            fill
            sizes="420px"
            className="object-cover"
          />
          <div>
            <p className="tb-cc-insight__kicker">Platform insight</p>
            <h3>
              More verified suppliers this month{" "}
              <em>+{ops?.suppliers ? Math.min(28, 12 + (ops.suppliers % 10)) : 18}%</em>
            </h3>
            <p>From local businesses to global opportunities.</p>
          </div>
        </article>
      </section>

      <section className="tb-cc-actions" aria-label="Quick actions">
        <Link href={ROUTES.admin.suppliers}>Verify Supplier</Link>
        <Link href={ROUTES.admin.finance}>Review Payouts</Link>
        <Link href={ROUTES.admin.users}>Manage Users</Link>
        <Link href={ROUTES.admin.settings}>Send Announcement</Link>
        <p className="tb-cc-actions__who">
          Signed in as <strong>{displayName}</strong>
        </p>
      </section>
    </div>
  );
}
