"use client";

import { SplitPanel, type SplitMark, type SplitTone } from "@/components/ui/SplitPanel";
import { cn } from "@/lib/utils";
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  /** Optional helper line under the title (replaces the old left panel). */
  asideTitle?: string;
  asideBody?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  tone?: SplitTone;
  mark?: SplitMark;
  steps?: string[];
  step?: number;
  kicker?: string;
};

export function Modal({
  open,
  onClose,
  title,
  asideTitle,
  asideBody,
  children,
  footer,
  className,
  tone = "brand",
  mark = "shield",
  steps,
  step,
  kicker,
}: ModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open || !mounted) return null;

  return createPortal(
    <div className="tb-modal-root" role="presentation">
      <button
        type="button"
        aria-label="Close overlay"
        className="tb-modal-scrim"
        onClick={onClose}
      />
      <div className="tb-modal-stage" role="dialog" aria-modal="true" aria-label={title}>
        <SplitPanel
          variant="sheet"
          tone={tone}
          mark={mark}
          asideTitle={asideTitle}
          asideBody={asideBody}
          title={title}
          kicker={kicker}
          steps={steps}
          step={step}
          onClose={onClose}
          footer={footer}
          className={cn("tb-modal-panel", className)}
        >
          {children}
        </SplitPanel>
      </div>
    </div>,
    document.body,
  );
}
