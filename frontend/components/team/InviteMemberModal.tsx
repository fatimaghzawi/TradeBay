"use client";

import { PermissionPicker } from "@/components/roles/PermissionPicker";
import { RoleCardPicker } from "@/components/team/RoleCardPicker";
import { Modal } from "@/components/ui/Modal";
import { FormField, TextField } from "@/components/ui/FormField";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Permission, type Role } from "@/lib/api/identityApi";
import { inviteMemberSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useAuth } from "@/providers/AuthProvider";
import { useEffect, useMemo, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

type InviteMemberModalProps = {
  open: boolean;
  onClose: () => void;
  onSent: () => void;
};

function localPart(email: string): string {
  const at = email.trim().toLowerCase().lastIndexOf("@");
  if (at <= 0) return "";
  return email
    .trim()
    .toLowerCase()
    .slice(0, at)
    .replace(/[^a-z0-9._+-]+/g, ".")
    .replace(/\.+/g, ".")
    .replace(/^\.|\.$/g, "")
    .slice(0, 64);
}

export function InviteMemberModal({ open, onClose, onSent }: InviteMemberModalProps) {
  const { success, error: toastError, warning } = useToast();
  const { permissions: actorPermissions, business } = useAuth();
  const [step, setStep] = useState(0);
  const [roles, setRoles] = useState<Role[]>([]);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [personalEmail, setPersonalEmail] = useState("");
  const [companyLocal, setCompanyLocal] = useState("");
  const [roleId, setRoleId] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const live = useLiveFields(inviteMemberSchema, {
    personal_email: personalEmail,
    company_local: companyLocal,
    role_id: roleId,
  });

  const companyDomain = business?.email_domain?.toLowerCase() ?? null;
  const companyName = business?.name ?? "your company";
  const companyEmail =
    companyDomain && companyLocal.trim()
      ? `${companyLocal.trim().toLowerCase()}@${companyDomain}`
      : "";

  useEffect(() => {
    if (!open) return;
    setError(null);
    setStep(0);
    setRoleId("");
    setSelectedPermissions([]);
    setPersonalEmail("");
    setCompanyLocal("");
    setLoadingRoles(true);
    void Promise.all([
      identityApi.listRoles({ page_size: 100 }),
      identityApi.listPermissions(),
    ])
      .then(([rolesResult, perms]) => {
        const list = rolesResult.data;
        const ordered = [...list].sort((a, b) => {
          if (a.name === "Business Admin") return 1;
          if (b.name === "Business Admin") return -1;
          return a.name.localeCompare(b.name);
        });
        setRoles(ordered);
        setCatalog(Array.isArray(perms) ? perms : []);
      })
      .catch((err) => {
        setRoles([]);
        setCatalog([]);
        setRoleId("");
        setError(
          err instanceof ApiError ? err.message : "Couldn't load roles for this company.",
        );
      })
      .finally(() => setLoadingRoles(false));
  }, [open]);

  const selected = roles.find((r) => r.id === roleId);
  const rolePermissionCodes = useMemo(
    () => (selected ? selected.permissions ?? [] : []),
    [selected],
  );
  const grantable = useMemo(() => {
    const actor = new Set(actorPermissions);
    return rolePermissionCodes.filter((code) => actor.has(code));
  }, [actorPermissions, rolePermissionCodes]);

  useEffect(() => {
    if (!selected) {
      setSelectedPermissions([]);
      return;
    }
    setSelectedPermissions(grantable);
  }, [grantable, selected]);

  function validateStep(): string | null {
    if (!companyDomain) {
      return "Set your company email domain on Company Profile before inviting teammates.";
    }
    if (!live.finish()) {
      return live.all.personal_email || live.all.company_local || live.all.role_id || "Check the highlighted fields.";
    }
    if (!companyEmail.endsWith(`@${companyDomain}`)) {
      return (
        `Company login must use the ${companyName} domain. ` +
        `Team members sign in with a @${companyDomain} email.`
      );
    }
    return null;
  }

  function send() {
    if (pending) return;
    if (!roleId) {
      setError("Select the role this person should have in your company.");
      return;
    }
    if (selectedPermissions.length === 0) {
      setError("Select at least one permission for this invitation.");
      return;
    }
    const validation = validateStep();
    if (validation) {
      setError(validation);
      return;
    }
    setError(null);
    setPending(true);
    void identityApi
      .invite(personalEmail.trim(), roleId, selectedPermissions, companyEmail)
      .then((result) => {
        setPersonalEmail("");
        setCompanyLocal("");
        setRoleId("");
        setSelectedPermissions([]);
        if (result.already_pending) {
          warning(
            "Invitation already pending",
            result.message ??
              `${companyEmail} already has an open invite. Resend it from Invitations if needed.`,
          );
        } else {
          success(
            "Invitation sent",
            `Sent to ${personalEmail.trim()}. They’ll sign in as ${result.invited_email}.`,
          );
        }
        onSent();
        onClose();
      })
      .catch((err) => {
        const message =
          err instanceof ApiError
            ? err.message
            : "Invite failed. Check that you hold every permission you selected.";
        const reason =
          err instanceof ApiError &&
          err.details &&
          typeof err.details === "object" &&
          "reason" in (err.details as object)
            ? String((err.details as { reason?: string }).reason)
            : null;
        if (reason === "already_member") {
          setError(message);
          warning("Already a member", message);
        } else if (reason === "company_domain_mismatch") {
          setError(message);
        } else {
          setError(message);
          toastError("Invitation not sent", message);
        }
      })
      .finally(() => setPending(false));
  }

  const readyForNext =
    Boolean(personalEmail.trim() && companyLocal.trim() && roleId) && !loadingRoles;

  return (
    <Modal
      open={open}
      onClose={onClose}
      mark="mail"
      kicker={step === 0 ? "Step 1 of 2" : "Step 2 of 2"}
      title={step === 0 ? "Who are you inviting?" : "What can they do?"}
      asideTitle={
        companyDomain
          ? `Join ${companyName}`
          : "Bring someone into your company"
      }
      asideBody={
        companyDomain
          ? `We email their personal inbox. They sign in with a @${companyDomain} login you assign.`
          : "Set your company email domain on Company Profile, then invite teammates."
      }
      steps={["Person & role", "Access"]}
      step={step}
      footer={
        step === 0 ? (
          <>
            <button type="button" className="tb-split-btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="tb-split-btn"
              disabled={!readyForNext}
              onClick={() => {
                const validation = validateStep();
                if (validation) {
                  setError(validation);
                  return;
                }
                setError(null);
                setStep(1);
              }}
            >
              Continue to access →
            </button>
          </>
        ) : (
          <>
            <button type="button" className="tb-split-btn-ghost" onClick={() => setStep(0)}>
              ← Back
            </button>
            <button
              type="button"
              className="tb-split-btn"
              disabled={selectedPermissions.length === 0 || pending}
              aria-busy={pending || undefined}
              onClick={send}
            >
              <BusyText busy={pending}>{pending ? "Sending…" : "Send invitation →"}</BusyText>
            </button>
          </>
        )
      }
    >
      {step === 0 ? (
        <div className="tb-form-stack">
          <div className="tb-form-block" data-tone="deliver">
            <div className="tb-form-block-head">
              <span className="tb-form-index">01</span>
              <div>
                <p className="tb-form-label">Personal inbox</p>
                <p className="tb-form-hint">Where we send the invitation link</p>
              </div>
            </div>
            <TextField
              label="Personal email"
              name="personal_email"
              required
              type="email"
              autoComplete="email"
              value={personalEmail}
              onChange={(e) => {
                const next = e.target.value;
                setPersonalEmail(next);
                setError(null);
                if (!companyLocal.trim()) {
                  setCompanyLocal(localPart(next));
                }
              }}
              onBlur={() => live.touch("personal_email")}
              error={live.errors.personal_email}
              placeholder="fatima@gmail.com"
            />
          </div>

          <div className="tb-form-block" data-tone="login">
            <div className="tb-form-block-head">
              <span className="tb-form-index">02</span>
              <div>
                <p className="tb-form-label">Company login</p>
                <p className="tb-form-hint">
                  How they sign in to {companyName}
                </p>
              </div>
            </div>
            <FormField
              label="Company login"
              error={live.errors.company_local}
              required
              boxed={false}
            >
              <div className="tb-form-affix" data-state={live.errors.company_local ? "error" : undefined}>
                <input
                  required
                  value={companyLocal}
                  onChange={(e) => {
                    setCompanyLocal(
                      e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9._+-]/g, "")
                        .slice(0, 64),
                    );
                    setError(null);
                  }}
                  onBlur={() => live.touch("company_local")}
                  placeholder="fatima"
                  aria-label="Company login local part"
                />
                <span className="tb-form-affix-chip">
                  @{companyDomain || "company.com"}
                </span>
              </div>
            </FormField>
          </div>

          <div className="tb-form-block" data-tone="role">
            <div className="tb-form-block-head">
              <span className="tb-form-index">03</span>
              <div>
                <p className="tb-form-label">Starting role</p>
                <p className="tb-form-hint">Tap a card — you can trim access next</p>
              </div>
            </div>
            <RoleCardPicker
              roles={roles}
              value={roleId}
              onChange={(id) => {
                setRoleId(id);
                live.touch("role_id");
                setError(null);
              }}
              loading={loadingRoles}
            />
            {live.errors.role_id ? (
              <p className="tb-hint" data-tone="error">
                {live.errors.role_id}
              </p>
            ) : null}
          </div>

          {(personalEmail.trim() || companyEmail || selected) && (
            <div className="tb-form-preview" aria-live="polite">
              <p className="tb-form-preview-kicker">Invite preview</p>
              <ul>
                <li>
                  <span>Send to</span>
                  <strong>{personalEmail.trim() || "—"}</strong>
                </li>
                <li>
                  <span>Sign in as</span>
                  <strong>{companyEmail || "—"}</strong>
                </li>
                <li>
                  <span>Role</span>
                  <strong>{selected?.name || "—"}</strong>
                </li>
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div className="tb-form-stack">
          <div className="tb-form-preview">
            <p className="tb-form-preview-kicker">Almost there</p>
            <ul>
              <li>
                <span>Invitee</span>
                <strong>{personalEmail.trim()}</strong>
              </li>
              <li>
                <span>Login</span>
                <strong>{companyEmail}</strong>
              </li>
              <li>
                <span>Role</span>
                <strong>{selected?.name}</strong>
              </li>
            </ul>
          </div>
          <p className="tb-form-hint !mt-0">
            Uncheck anything this person should not receive. You can only assign
            access you already have.
          </p>
          <PermissionPicker
            catalog={catalog.filter((p) => rolePermissionCodes.includes(p.code))}
            selected={selectedPermissions}
            onChange={setSelectedPermissions}
            grantable={grantable}
          />
        </div>
      )}
      {error ? <p className="tb-form-alert">{error}</p> : null}
    </Modal>
  );
}
