"use client";

import { Modal } from "@/components/ui/Modal";
import { BusyText } from "@/components/ui/LoadingState";
import type { ReactNode } from "react";
import { useState } from "react";

export function ConfirmModal({
  open,
  title,
  asideTitle,
  asideBody,
  children,
  confirmLabel = "Delete",
  pendingLabel = "Working…",
  onClose,
  onConfirm,
}: {
  open: boolean;
  title: string;
  asideTitle: string;
  asideBody?: ReactNode;
  children: ReactNode;
  confirmLabel?: string;
  pendingLabel?: string;
  onClose: () => void;
  onConfirm: () => Promise<void> | void;
}) {
  const [pending, setPending] = useState(false);

  return (
    <Modal
      open={open}
      onClose={onClose}
      tone="danger"
      mark="trash"
      title={title}
      asideTitle={asideTitle}
      asideBody={asideBody}
      footer={
        <>
          <button type="button" className="tb-btn tb-btn--outline" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="tb-btn tb-btn--destructive"
            disabled={pending}
            aria-busy={pending || undefined}
            onClick={() => {
              if (pending) return;
              setPending(true);
              void Promise.resolve(onConfirm())
                .then(() => onClose())
                .catch(() => undefined)
                .finally(() => setPending(false));
            }}
          >
            <BusyText busy={pending}>{pending ? pendingLabel : confirmLabel}</BusyText>
          </button>
        </>
      }
    >
      {children}
    </Modal>
  );
}
