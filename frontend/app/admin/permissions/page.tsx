"use client";

import { AdminIdentityNav } from "@/components/admin/AdminIdentityNav";
import { AdminAct, AdminPage } from "@/components/admin/AdminUi";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { identityApi, type Permission } from "@/lib/api/identityApi";
import {
  groupPermissionsByModule,
  moduleLabel,
  moduleQuestion,
  permissionTitle,
} from "@/lib/identity/permissionCopy";
import { PLATFORM_ONLY_PERMISSION_CODES } from "@/lib/identity/tradingPermissions";
import { ROUTES } from "@/lib/constants";
import { useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

function AdminPermissionsPageInner() {
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeResource, setActiveResource] = useState("");
  const [query, setQuery] = useState("");
  const [layer, setLayer] = useState<"all" | "trading" | "platform">("all");

  useEffect(() => {
    void identityApi
      .listPermissions()
      .then((rows) => {
        setCatalog(Array.isArray(rows) ? rows : []);
        setError(null);
      })
      .catch(() => {
        setCatalog([]);
        setError("Couldn't load access settings.");
      })
      .finally(() => setLoading(false));
  }, []);

  const scopedCatalog = useMemo(() => {
    if (layer === "trading") {
      return catalog.filter((p) => !PLATFORM_ONLY_PERMISSION_CODES.has(p.code));
    }
    if (layer === "platform") {
      return catalog.filter((p) => PLATFORM_ONLY_PERMISSION_CODES.has(p.code));
    }
    return catalog;
  }, [catalog, layer]);

  const filteredCatalog = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return scopedCatalog;
    return scopedCatalog.filter((permission) => {
      const haystack = [
        permission.code,
        permission.action,
        permission.resource,
        permission.description ?? "",
        permissionTitle(permission),
        moduleLabel(permission.resource),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [scopedCatalog, query]);

  const grouped = useMemo(
    () => groupPermissionsByModule(filteredCatalog),
    [filteredCatalog],
  );

  useEffect(() => {
    if (grouped.length === 0) {
      setActiveResource("");
      return;
    }
    if (!grouped.some(([resource]) => resource === activeResource)) {
      setActiveResource(grouped[0]?.[0] ?? "");
    }
  }, [activeResource, grouped]);

  const activeItems = useMemo(() => {
    const found = grouped.find(([resource]) => resource === activeResource);
    return found ? found[1] : [];
  }, [grouped, activeResource]);

  return (
    <AdminPage>
      <AdminIdentityNav />
      <DirectoryMast
        title="Permissions"
        mark="Platform"
        size="page"
        actions={
          <AdminAct href={ROUTES.admin.roles} tone="go" arrow>
            Edit roles
          </AdminAct>
        }
      />

      <div className="tb-summary">
        {[
          { label: "In catalog", value: catalog.length },
          { label: "Modules", value: grouped.length },
          { label: "In view", value: activeItems.length },
        ].map((stat) => (
          <div key={stat.label} className="tb-summary-item">
            <p className="tb-summary-label">{stat.label}</p>
            <p className="tb-summary-value tb-num">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="tb-toolbar flex-wrap gap-y-2">
        {(
          [
            ["all", "All"],
            ["trading", "Trading"],
            ["platform", "Platform-only"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className="tb-filter"
            data-active={layer === key}
            onClick={() => setLayer(key)}
          >
            {label}
          </button>
        ))}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search modules or actions…"
          className="h-9 w-full max-w-xs rounded-lg border border-input px-3 text-sm outline-none focus:border-ring"
        />
      </div>

      {error ? (
        <FeedbackBanner tone="error" title="Couldn’t load permissions" onDismiss={() => setError(null)}>
          {error}
        </FeedbackBanner>
      ) : null}

      {loading ? (
        <LoadingEntity entity="permissions" className="py-12 justify-center" />
      ) : grouped.length === 0 ? (
        <div className="tb-empty">
          <h3>No permissions match</h3>
          <p>Try a different search or filter.</p>
        </div>
      ) : (
        <div className="tb-perm-picker-body mt-2" data-compact="true">
          <nav className="tb-perm-modules" aria-label="Permission modules">
            {grouped.map(([resource, items]) => (
              <button
                key={resource}
                type="button"
                className="tb-perm-module"
                data-active={activeResource === resource}
                onClick={() => setActiveResource(resource)}
              >
                <span className="tb-perm-module-name">{moduleLabel(resource)}</span>
                <span className="tb-perm-module-count">{items.length}</span>
              </button>
            ))}
          </nav>
          <div className="tb-perm-panel">
            <div className="tb-perm-panel-head">
              <div>
                <h3>{moduleLabel(activeResource)}</h3>
                <p>{moduleQuestion(activeResource)}</p>
              </div>
            </div>
            <ul className="tb-perm-list" data-layout="chips">
              {activeItems.map((permission) => (
                <li key={permission.code}>
                  <div
                    className="tb-perm-item is-readonly is-on"
                    title={`${permission.description ?? permissionTitle(permission)} · ${permission.code}`}
                  >
                    <span className="tb-perm-item-copy">
                      <span className="tb-perm-item-verb">{permission.action}</span>
                      <span className="tb-perm-item-title">
                        {permissionTitle(permission)}
                        {PLATFORM_ONLY_PERMISSION_CODES.has(permission.code) ? (
                          <em className="ml-1 text-[11px] not-italic text-accent-text">
                            · platform
                          </em>
                        ) : null}
                      </span>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </AdminPage>
  );
}

export default function AdminPermissionsPage() {
  return (
    <PermissionGate
      permission="roles.read"
      fallbackTitle="Permissions locked"
      fallbackDescription="Platform staff access is required to browse permissions."
    >
      <AdminPermissionsPageInner />
    </PermissionGate>
  );
}
