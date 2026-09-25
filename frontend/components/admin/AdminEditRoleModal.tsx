"use client";

import { ModulePermissionPicker } from "@/components/roles/ModulePermissionPicker";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Permission, type Role } from "@/lib/api/identityApi";
import {
  isTradingPermissionCode,
  tradingPermissionCodes,
} from "@/lib/identity/tradingPermissions";
import { useAuth } from "@/providers/AuthProvider";
import { useEffect, useMemo, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

type AdminEditRoleModalProps = {
  open: boolean;
  businessId: string;
  role: Role | null;
  onClose: () => void;
  onSaved: () => void;
};

export function AdminEditRoleModal({
  open,
  businessId,
  role,
  onClose,
  onSaved,
}: AdminEditRoleModalProps) {
  const { permissions } = useAuth();
  const { success, error: toastError } = useToast();
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const grantable = useMemo(
    () => new Set(tradingPermissionCodes(permissions)),
    [permissions],
  );

  const tradingCatalog = useMemo(
    () => catalog.filter((p) => isTradingPermissionCode(p.code)),
    [catalog],
  );

  useEffect(() => {
    if (!open || !role) return;
    setSelected(tradingPermissionCodes(role.permissions));
    setError(null);
    void identityApi
      .listPermissions()
      .then((rows) => setCatalog(Array.isArray(rows) ? rows : []))
      .catch(() => setCatalog([]));
  }, [open, role]);

  return (
    <Modal
      open={open && Boolean(role)}
      onClose={onClose}
      mark="lock"
      kicker="Platform control"
      title={role ? `Edit ${role.name}` : "Edit role"}
      asideTitle="Full access"
      asideBody="Platform staff can grant any trading permission, including on Business Admin."
      footer={
        <>
          <button type="button" className="tb-btn tb-btn--outline" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="tb-btn tb-btn--primary"
            disabled={!role || selected.length === 0 || pending}
            aria-busy={pending || undefined}
            onClick={() => {
              if (pending || !role) return;
              if (selected.length === 0) {
                setError("Keep at least one permission.");
                return;
              }
              setError(null);
              setPending(true);
              void identityApi
                .updatePlatformBusinessRole(businessId, role.id, selected)
                .then(() => {
                  success("Role updated", `${role.name} permissions saved.`);
                  onSaved();
                  onClose();
                })
                .catch((err) => {
                  const message =
                    err instanceof ApiError
                      ? err.message
                      : "Couldn't update this role.";
                  setError(message);
                  toastError("Couldn't save", message);
                })
                .finally(() => setPending(false));
            }}
          >
            <BusyText busy={pending}>{pending ? "Saving…" : "Save permissions"}</BusyText>
          </button>
        </>
      }
    >
      {role ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {selected.length} selected · {grantable.size} grantable trading permissions
          </p>
          <ModulePermissionPicker
            catalog={tradingCatalog}
            selected={selected}
            onChange={setSelected}
            grantable={grantable}
          />
          {error ? <p className="tb-form-alert">{error}</p> : null}
        </div>
      ) : null}
    </Modal>
  );
}
