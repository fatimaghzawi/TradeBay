"use client";

import type { Permission } from "@/lib/api/identityApi";
import {
  groupPermissionsByModule,
  moduleLabel,
  moduleQuestion,
  permissionTitle,
} from "@/lib/identity/permissionCopy";
import { cn } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";

type ModulePermissionPickerProps = {
  catalog: Permission[];
  selected: string[];
  onChange: (codes: string[]) => void;
  grantable: Set<string> | string[];
  readOnly?: boolean;
  
  templates?: { id: string; name: string; permissions: string[] }[];
  
  compact?: boolean;
};

function actionVerb(action: string): string {
  return action.replace(/_/g, " ");
}

export function ModulePermissionPicker({
  catalog,
  selected,
  onChange,
  grantable,
  readOnly = false,
  templates = [],
  compact = true,
}: ModulePermissionPickerProps) {
  const allowed = useMemo(
    () => (grantable instanceof Set ? grantable : new Set(grantable)),
    [grantable],
  );

  const grouped = useMemo(() => groupPermissionsByModule(catalog), [catalog]);
  const [activeResource, setActiveResource] = useState<string>("");
  const [query, setQuery] = useState("");

  const filteredGrouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return grouped;
    return grouped
      .map(([resource, items]) => {
        const next = items.filter((permission) => {
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
        return [resource, next] as [string, typeof items];
      })
      .filter(([, items]) => items.length > 0);
  }, [grouped, query]);

  useEffect(() => {
    if (filteredGrouped.length === 0) {
      setActiveResource("");
      return;
    }
    if (!filteredGrouped.some(([resource]) => resource === activeResource)) {
      setActiveResource(filteredGrouped[0]?.[0] ?? "");
    }
  }, [activeResource, filteredGrouped]);

  const activeItems = useMemo(() => {
    const found = filteredGrouped.find(([resource]) => resource === activeResource);
    return found ? found[1] : [];
  }, [filteredGrouped, activeResource]);

  const selectedTotal = useMemo(
    () => selected.filter((code) => catalog.some((p) => p.code === code)).length,
    [catalog, selected],
  );

  function toggle(code: string, checked: boolean) {
    if (readOnly || !allowed.has(code)) return;
    onChange(
      checked
        ? Array.from(new Set([...selected, code]))
        : selected.filter((item) => item !== code),
    );
  }

  function toggleAll(checked: boolean) {
    if (readOnly) return;
    const codes = activeItems
      .map((p) => p.code)
      .filter((code) => allowed.has(code));
    if (checked) {
      onChange(Array.from(new Set([...selected, ...codes])));
    } else {
      const drop = new Set(codes);
      onChange(selected.filter((code) => !drop.has(code)));
    }
  }

  function applyTemplate(roleId: string) {
    const template = templates.find((t) => t.id === roleId);
    if (!template || readOnly) return;
    const next = template.permissions.filter((code) => allowed.has(code));
    onChange(next);
  }

  if (grouped.length === 0) {
    return (
      <p className="rounded-xl bg-interactive px-3.5 py-3 text-sm text-muted-foreground">
        No permissions available to assign.
      </p>
    );
  }

  const grantableActive = activeItems.filter((p) => allowed.has(p.code));
  const selectedActive = grantableActive.filter((p) => selected.includes(p.code));
  const allChecked =
    grantableActive.length > 0 && selectedActive.length === grantableActive.length;
  const someChecked = selectedActive.length > 0 && !allChecked;

  return (
    <div className="tb-perm-picker" data-compact={compact}>
      <div className="tb-perm-picker-toolbar">
        {templates.length > 0 && !readOnly ? (
          <label className="tb-perm-template">
            <span>Template</span>
            <select
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) applyTemplate(e.target.value);
                e.target.value = "";
              }}
            >
              <option value="" disabled>
                Copy from a role…
              </option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <p className="tb-perm-summary">
          <strong>{selectedTotal}</strong> selected
        </p>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter…"
          className="tb-roles-search ml-auto"
          aria-label="Filter permissions"
        />
      </div>

      {filteredGrouped.length === 0 ? (
        <p className="rounded-xl bg-interactive px-3.5 py-3 text-sm text-muted-foreground">
          No permissions match your search.
        </p>
      ) : (
        <div className="tb-perm-picker-body">
          <nav className="tb-perm-modules" aria-label="Permission modules">
            {filteredGrouped.map(([resource, items]) => {
              const count = items.filter((p) => selected.includes(p.code)).length;
              return (
                <button
                  key={resource}
                  type="button"
                  className="tb-perm-module"
                  data-active={activeResource === resource}
                  onClick={() => setActiveResource(resource)}
                >
                  <span className="tb-perm-module-name">{moduleLabel(resource)}</span>
                  <span className="tb-perm-module-count">
                    {count}/{items.length}
                  </span>
                </button>
              );
            })}
          </nav>

          <div className="tb-perm-panel">
            <div className="tb-perm-panel-head">
              <div>
                <h3>{moduleLabel(activeResource)}</h3>
                <p>{moduleQuestion(activeResource)}</p>
              </div>
              {!readOnly ? (
                <label className="tb-perm-select-all">
                  <input
                    type="checkbox"
                    checked={allChecked}
                    ref={(el) => {
                      if (el) el.indeterminate = someChecked;
                    }}
                    disabled={grantableActive.length === 0}
                    onChange={(e) => toggleAll(e.target.checked)}
                  />
                  All in module
                </label>
              ) : null}
            </div>

            <ul className="tb-perm-list" data-layout={compact ? "chips" : "rows"}>
              {activeItems.map((permission) => {
                const canGrant = allowed.has(permission.code);
                const checked = selected.includes(permission.code);
                return (
                  <li key={permission.code}>
                    <label
                      className={cn(
                        "tb-perm-item",
                        checked && "is-on",
                        (!canGrant || readOnly) && "is-disabled",
                      )}
                      title={
                        permission.description
                          ? `${permission.description} (${permission.code})`
                          : permission.code
                      }
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={readOnly || !canGrant}
                        onChange={(e) => toggle(permission.code, e.target.checked)}
                      />
                      <span className="tb-perm-item-copy">
                        <span className="tb-perm-item-verb">
                          {actionVerb(permission.action)}
                        </span>
                        <span className="tb-perm-item-title">
                          {permissionTitle(permission)}
                        </span>
                        {!compact ? (
                          <>
                            <span className="tb-perm-item-desc">
                              {permission.description ||
                                `${permission.action} access for ${moduleLabel(permission.resource).toLowerCase()}`}
                            </span>
                          </>
                        ) : null}
                        {!canGrant && !readOnly ? (
                          <span className="tb-perm-item-warn">Can&apos;t grant</span>
                        ) : null}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
