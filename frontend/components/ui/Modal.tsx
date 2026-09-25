"use client";

import { SplitPanel, type SplitMark, type SplitTone } from "@/components/ui/SplitPanel";
import { cn } from "@/lib/utils";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  
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
  const stageRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusables = () =>
      Array.from(stageRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter(
        (el) => !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true",
      );
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    const raf = requestAnimationFrame(() => {
      const stage = stageRef.current;
      if (!stage || stage.contains(document.activeElement)) return;
      const field = stage.querySelector<HTMLElement>("input:not([type=hidden]), select, textarea");
      (field ?? focusables()[0] ?? stage).focus();
    });
    return () => {
      cancelAnimationFrame(raf);
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [open]);

  if (!open || !mounted) return null;

  return createPortal(
    <div className="tb-modal-root" role="presentation">
      <button
        type="button"
        aria-label="Close overlay"
        className="tb-modal-scrim"
        onClick={onClose}
      />
      <div
        ref={stageRef}
        className="tb-modal-stage"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
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
