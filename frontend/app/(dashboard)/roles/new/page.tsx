"use client";

import { ModulePermissionPicker } from "@/components/roles/ModulePermissionPicker";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Permission, type Role } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { permissionTitle } from "@/lib/identity/permissionCopy";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";
import { BackLink } from "@/components/ui/BackLink";

const STEPS = [
  { id: 0, label: "Role Details" },
  { id: 1, label: "Permissions" },
  { id: 2, label: "Review" },
] as const;

const DESC_MAX = 200;

export default function CreateRolePage() {
  const router = useRouter();
  const { hasPermission, permissions } = useAuth();
  const { success, error: toastError } = useToast();
  const [step, setStep] = useState(0);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [templates, setTemplates] = useState<Role[]>([]);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const canManage = hasPermission("roles.manage");
  const grantable = useMemo(() => new Set(permissions), [permissions]);
  const catalogByCode = useMemo(() => {
    const map = new Map<string, Permission>();
    for (const p of catalog) map.set(p.code, p);
    return map;
  }, [catalog]);

  useEffect(() => {
    void identityApi
      .listPermissions()
      .then((rows) => setCatalog(Array.isArray(rows) ? rows : []))
      .catch(() => setCatalog([]));
    void identityApi
      .listRoles({ page_size: 100 })
      .then((result) => setTemplates(result.data))
      .catch(() => setTemplates([]));
  }, []);

  if (!canManage) {
    return (
      <div className="space-y-3">
        <BackLink href={ROUTES.roles}>Back to roles</BackLink>
        <FeedbackBanner tone="warning" title="Access restricted">
          You don&apos;t have access to create custom roles. Ask a Business Admin if you
          need a new role.
        </FeedbackBanner>
      </div>
    );
  }

  function create() {
    if (!name.trim()) {
      setError("Enter a role name.");
      setStep(0);
      return;
    }
    if (selected.length === 0) {
      setError("Select at least one permission.");
      setStep(1);
      return;
    }
    setError(null);
    setPending(true);
    void identityApi
      .createRole(name.trim(), selected)
      .then((role) => {
        success("Role created", `${role.name} is ready to assign.`);
        router.replace(`${ROUTES.roles}/${role.id}`);
      })
      .catch((err) => {
        const message =
          err instanceof ApiError
            ? err.message
            : "Role was not created. You can only assign access you already have.";
        setError(message);
        toastError("Couldn't create", message);
      })
      .finally(() => setPending(false));
  }

  return (
    <div className="tb-role-create">
      <p className="tb-ov-crumb">
        Company Identity <span>/</span>{" "}
        <Link href={ROUTES.roles} className="hover:underline">
          Roles
        </Link>{" "}
        <span>/</span> Create Role
      </p>

      <DirectoryMast
        title="Create a Role"
        size="page"
        lede="Define what this role is responsible for and give it the right permissions."
        actions={
          <ol className="tb-role-stepper">
            {STEPS.map((item) => (
              <li
                key={item.id}
                data-active={step === item.id}
                data-done={step > item.id}
              >
                <span>{item.id + 1}</span>
                {item.label}
              </li>
            ))}
          </ol>
        }
      />

      {error ? (
        <p role="alert" className="tb-alert tb-alert--error">
          {error}
        </p>
      ) : null}

      {step === 0 ? (
        <section className="tb-role-card">
          <div className="tb-role-card-head">
            <span className="tb-role-card-icon" aria-hidden>
              ☺
            </span>
            <div>
              <h2>Role Information</h2>
              <p>Start with the basics. Give this role a clear identity.</p>
            </div>
          </div>

          <div className="tb-role-fields">
            <label className="tb-role-field">
              <span>
                Role Name <em>*</em>
              </span>
              <input
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (error === "Enter a role name.") setError(null);
                }}
                placeholder="e.g. Sales Manager"
                maxLength={100}
              />
              {!name.trim() && error === "Enter a role name." ? (
                <p className="tb-hint" data-tone="error">
                  Role name is required
                </p>
              ) : null}
            </label>
            <label className="tb-role-field">
              <span>Role Type</span>
              <select disabled value="custom">
                <option value="custom">Custom Role</option>
              </select>
            </label>
            <label className="tb-role-field tb-role-field-full">
              <span>
                Description <em>*</em>
              </span>
              <textarea
                rows={4}
                value={note}
                maxLength={DESC_MAX}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Manages sales activities, quotations, RFQs and customer-facing operations."
              />
              <span className="tb-role-counter">
                {note.length}/{DESC_MAX}
              </span>
            </label>
          </div>

          <div className="tb-role-tip">
            <span aria-hidden>✦</span>
            <p>
              <strong>Tip:</strong> Write a clear description like a job
              responsibility. This will help your team understand the role.
            </p>
          </div>
        </section>
      ) : null}

      {step === 1 ? (
        <section className="tb-role-card">
          <div className="tb-role-card-head">
            <span className="tb-role-card-icon" aria-hidden>
              🔒
            </span>
            <div>
              <h2>Permissions</h2>
              <p>
                Select what this role can do. Permissions are organized by
                business modules.
              </p>
            </div>
          </div>
          <ModulePermissionPicker
            catalog={catalog}
            selected={selected}
            onChange={setSelected}
            grantable={grantable}
            templates={templates.map((r) => ({
              id: r.id,
              name: r.name,
              permissions: r.permissions ?? [],
            }))}
          />
        </section>
      ) : null}

      {step === 2 ? (
        <section className="tb-role-card">
          <div className="tb-role-card-head">
            <span className="tb-role-card-icon" aria-hidden>
              ✓
            </span>
            <div>
              <h2>Review</h2>
              <p>Confirm this responsibility before creating it.</p>
            </div>
          </div>
          <dl className="tb-role-review">
            <div>
              <dt>Role name</dt>
              <dd>{name || "—"}</dd>
            </div>
            <div>
              <dt>Type</dt>
              <dd>Custom Role</dd>
            </div>
            <div>
              <dt>Description</dt>
              <dd>{note || "No description added"}</dd>
            </div>
            <div>
              <dt>Permissions</dt>
              <dd>{selected.length} selected</dd>
            </div>
          </dl>
          <ul className="tb-role-review-perms">
            {selected.slice(0, 16).map((code) => {
              const perm = catalogByCode.get(code);
              return (
                <li key={code}>
                  <strong>{perm ? permissionTitle(perm) : code}</strong>
                  <code>{code}</code>
                </li>
              );
            })}
            {selected.length > 16 ? (
              <li className="tb-meta">+{selected.length - 16} more</li>
            ) : null}
          </ul>
        </section>
      ) : null}

      <footer className="tb-role-create-foot">
        {step === 0 ? (
          <>
            <Link href={ROUTES.roles} className="tb-btn tb-btn--outline">
              Cancel
            </Link>
            <button
              type="button"
              className="tb-btn tb-btn--primary"
              disabled={!name.trim() || !note.trim()}
              onClick={() => {
                setError(null);
                setStep(1);
              }}
            >
              Next Step →
            </button>
          </>
        ) : step === 1 ? (
          <>
            <button
              type="button"
              className="tb-btn tb-btn--outline"
              onClick={() => setStep(0)}
            >
              Back
            </button>
            <button
              type="button"
              className="tb-btn tb-btn--primary"
              disabled={selected.length === 0}
              onClick={() => {
                setError(null);
                setStep(2);
              }}
            >
              Next Step →
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="tb-btn tb-btn--outline"
              onClick={() => setStep(1)}
            >
              Back
            </button>
            <button
              type="button"
              className="tb-btn tb-btn--primary"
              disabled={pending}
              onClick={create}
             aria-busy={pending || undefined}>
              <BusyText busy={pending}>{pending ? "Creating…" : "Create Role →"}</BusyText>
            </button>
          </>
        )}
      </footer>
    </div>
  );
}
