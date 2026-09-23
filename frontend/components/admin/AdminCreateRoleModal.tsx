"use client";

import { ModulePermissionPicker } from "@/components/roles/ModulePermissionPicker";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { identityApi, type Permission } from "@/lib/api/identityApi";
import {
  isTradingPermissionCode,
  tradingPermissionCodes,
} from "@/lib/identity/tradingPermissions";
import { useAuth } from "@/providers/AuthProvider";
import { useEffect, useMemo, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

type AdminCreateRoleModalProps = {
  open: boolean;
  businessId: string;
  onClose: () => void;
  onCreated: () => void;
};

export function AdminCreateRoleModal({
  open,
  businessId,
  onClose,
  onCreated,
}: AdminCreateRoleModalProps) {
  const { permissions } = useAuth();
  const { success, error: toastError } = useToast();
  const [name, setName] = useState("");
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
    if (!open) return;
    setName("");
    setSelected([]);
    setError(null);
    void identityApi
      .listPermissions()
      .then((rows) => setCatalog(Array.isArray(rows) ? rows : []))
      .catch(() => setCatalog([]));
  }, [open]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      mark="lock"
      kicker="Platform control"
      title="Create company role"
      asideTitle="Custom access"
      asideBody="Build a role from trading permissions only. Platform-only codes stay on TradeBay staff."
      footer={
        <>
          <button type="button" className="tb-split-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="tb-split-btn"
            disabled={!name.trim() || selected.length === 0 || pending}
            aria-busy={pending || undefined}
            onClick={() => {
              if (pending) return;
              const trimmed = name.trim();
              if (!trimmed) {
                setError("Name is required.");
                return;
              }
              if (selected.length === 0) {
                setError("Pick at least one permission.");
                return;
              }
              setError(null);
              setPending(true);
              void identityApi
                .createPlatformBusinessRole(businessId, trimmed, selected)
                .then(() => {
                  success("Role created", `${trimmed} is ready to assign.`);
                  onCreated();
                  onClose();
                })
                .catch((err) => {
                  const message =
                    err instanceof ApiError
                      ? err.message
                      : "Couldn't create this role.";
                  setError(message);
                  toastError("Couldn't create", message);
                })
                .finally(() => setPending(false));
            }}
          >
            <BusyText busy={pending}>{pending ? "Creating…" : "Create role"}</BusyText>
          </button>
        </>
      }
    >
      <div className="tb-form-stack">
        <label className="tb-form-block">
          <span className="tb-form-label">Role name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-10 w-full rounded-lg border border-[#d4e0da] px-3 text-sm outline-none focus:border-[#e86f2a]"
            placeholder="e.g. Procurement Lead"
            maxLength={80}
          />
        </label>
        <ModulePermissionPicker
          catalog={tradingCatalog}
          selected={selected}
          onChange={setSelected}
          grantable={grantable}
        />
        {error ? <p className="tb-form-alert">{error}</p> : null}
      </div>
    </Modal>
  );
}
