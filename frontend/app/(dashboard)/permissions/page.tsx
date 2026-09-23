"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { identityApi, type Permission } from "@/lib/api/identityApi";
import {
  groupPermissionsByModule,
  moduleLabel,
  moduleQuestion,
  permissionTitle,
} from "@/lib/identity/permissionCopy";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { LoadingState } from "@/components/ui/LoadingState";

function PermissionsPageInner() {
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeResource, setActiveResource] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    void identityApi
      .listPermissions()
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : [];
        setCatalog(list);
        setError(null);
      })
      .catch(() => {
        setCatalog([]);
        setError("Couldn't load access settings.");
      })
      .finally(() => setLoading(false));
  }, []);

  const filteredCatalog = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter((permission) => {
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
  }, [catalog, query]);

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
    <IdentityPageShell
      crumb="Company Identity / Permissions"
      title="Permissions"
      lede={
        <>
          Browse access by module. Assign them when you{" "}
          <Link
            href={ROUTES.roles}
            className="font-semibold text-[var(--tb-secondary)] underline-offset-2 hover:underline"
          >
            create or edit roles
          </Link>
          .
        </>
      }
      banner={{
        icon: "⛨",
        title: "Know what each action unlocks.",
        body: "Permissions are assigned through roles — use this catalog to plan access before you invite.",
      }}
      stats={[
        { icon: "◈", tone: "orange", value: catalog.length, label: "In Catalog" },
        { icon: "☰", tone: "teal", value: grouped.length, label: "Modules" },
        {
          icon: "◎",
          tone: "green",
          value: activeItems.length,
          label: "In View",
        },
      ]}
      search={query}
      searchPlaceholder="Search modules or actions…"
      onSearchChange={setQuery}
      quote="“Clear permissions keep every desk honest.”"
    >
      {error ? (
        <div className="mt-2">
          <FeedbackBanner
            tone="error"
            title="Couldn’t load permissions"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {loading ? (
        <LoadingState variant="section" title="Loading permissions" message="Loading permissions…" />
      ) : grouped.length === 0 ? (
        <div className="tb-empty">
          <h3>No permissions match</h3>
          <p>Try a different search.</p>
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
                <span className="tb-perm-module-name">
                  {moduleLabel(resource)}
                </span>
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
                      <span className="tb-perm-item-verb">
                        {permission.action}
                      </span>
                      <span className="tb-perm-item-title">
                        {permissionTitle(permission)}
                      </span>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </IdentityPageShell>
  );
}

export default function PermissionsPage() {
  return (
    <PermissionGate permission="roles.read">
      <PermissionsPageInner />
    </PermissionGate>
  );
}
