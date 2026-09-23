"use client";

import { Modal } from "@/components/ui/Modal";
import { BusyText } from "@/components/ui/LoadingState";
import { useState } from "react";

type SuspendAccountModalProps = {
  open: boolean;
  title?: string;
  subjectLabel: string;
  confirmLabel?: string;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void> | void;
};

export function SuspendAccountModal({
  open,
  title = "Suspend account",
  subjectLabel,
  confirmLabel = "Suspend",
  onClose,
  onConfirm,
}: SuspendAccountModalProps) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <Modal
      open={open}
      onClose={onClose}
      tone="danger"
      mark="lock"
      kicker="Security action"
      title={title}
      asideTitle="This locks the account"
      asideBody="They lose access immediately. A reason is required and stored in the audit log."
      footer={
        <>
          <button type="button" className="tb-split-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="tb-split-btn-danger"
            disabled={pending || !reason.trim()}
            aria-busy={pending || undefined}
            onClick={() => {
              if (pending) return;
              const cleaned = reason.trim();
              if (!cleaned) {
                setError("Enter a suspension reason.");
                return;
              }
              setError(null);
              setPending(true);
              void Promise.resolve(onConfirm(cleaned))
                .then(() => {
                  setReason("");
                  onClose();
                })
                .catch((err: unknown) =>
                  setError(err instanceof Error ? err.message : "Suspension failed."),
                )
                .finally(() => setPending(false));
            }}
          >
            <BusyText busy={pending}>{pending ? "Suspending…" : confirmLabel}</BusyText>
          </button>
        </>
      }
    >
      <div className="tb-form-stack">
        <div className="tb-form-preview" data-tone="danger">
          <p className="tb-form-preview-kicker">Suspending</p>
          <ul>
            <li>
              <span>Account</span>
              <strong>{subjectLabel}</strong>
            </li>
          </ul>
        </div>
        <div className="tb-form-block" data-tone="danger">
          <div className="tb-form-block-head">
            <span className="tb-form-index">!</span>
            <div>
              <p className="tb-form-label">Reason</p>
              <p className="tb-form-hint">Shown in audit history — be specific</p>
            </div>
          </div>
          <label className="tb-form-shell" data-state={!reason.trim() && error ? "error" : undefined}>
            <span className="sr-only">Suspension reason</span>
            <textarea
              required
              rows={4}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError(null);
              }}
              placeholder="e.g. Left the company · policy breach · temporary hold…"
            />
          </label>
          {error && !reason.trim() ? (
            <p className="tb-hint" data-tone="error">
              {error}
            </p>
          ) : error ? (
            <p className="tb-form-alert">{error}</p>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}
