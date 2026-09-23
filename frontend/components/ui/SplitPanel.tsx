import { cn } from "@/lib/utils";
import type { FormEventHandler, ReactNode } from "react";

export type SplitTone = "brand" | "danger";
export type SplitMark = "shield" | "lock" | "trash" | "user" | "mail" | "check";
export type SplitVariant = "split" | "sheet";

export function SplitMarkIcon({ mark }: { mark: SplitMark }) {
  const path =
    mark === "lock"
      ? "M8 10V7a4 4 0 1 1 8 0v3M7 10h10v10H7V10Z"
      : mark === "trash"
        ? "M5 7h14M9 7V5h6v2M8 7l1 12h6l1-12"
        : mark === "user"
          ? "M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Zm0 2c-4 0-7 2-7 4v1h14v-1c0-2-3-4-7-4Z"
          : mark === "mail"
            ? "M4 7h16v10H4V7Zm0 0 8 6 8-6"
            : mark === "check"
              ? "M6 12.5 10 16.5 18 8"
              : "M12 3 4 7v6c0 5 3.4 7.7 8 9 4.6-1.3 8-4 8-9V7Z";

  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d={path} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SplitSteps({
  steps,
  step,
}: {
  steps: string[];
  step: number;
}) {
  return (
    <ol className="tb-split-steps" aria-label="Progress">
      {steps.map((label, index) => (
        <li key={label} className="tb-split-step" data-active={index === step} data-done={index < step}>
          <span className="tb-split-step-dot">{index < step ? "✓" : index + 1}</span>
          <span>{label}</span>
        </li>
      ))}
    </ol>
  );
}

export function SplitPanel({
  tone = "brand",
  mark = "shield",
  variant = "split",
  asideTitle,
  asideBody,
  title,
  kicker = "Workspace",
  steps,
  step = 0,
  onClose,
  children,
  footer,
  className,
  as: Tag = "div",
  onSubmit,
}: {
  tone?: SplitTone;
  mark?: SplitMark;
  variant?: SplitVariant;
  asideTitle?: string;
  asideBody?: ReactNode;
  title: string;
  kicker?: string;
  steps?: string[];
  step?: number;
  onClose?: () => void;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  as?: "div" | "section" | "form";
  onSubmit?: FormEventHandler<HTMLFormElement>;
}) {
  const sheet = variant === "sheet";
  const shellClass = cn("tb-split", sheet && "tb-split-sheet", className);

  const body = (
    <>
      {!sheet ? (
        <aside className="tb-split-aside">
          <div className="tb-split-aside-glow" aria-hidden />
          <div className="tb-split-aside-grid" aria-hidden />
          <span className="tb-split-mark">
            <SplitMarkIcon mark={mark} />
          </span>
          <p className="tb-split-aside-kicker">TradeBay</p>
          {asideTitle ? <p className="tb-split-aside-title">{asideTitle}</p> : null}
          {asideBody ? <div className="tb-split-aside-body">{asideBody}</div> : null}
        </aside>
      ) : null}

      <div className="tb-split-main">
        <header className="tb-split-head">
          <div className="tb-split-head-copy min-w-0">
            <div className="tb-split-head-row">
              <span className="tb-split-mark-inline" aria-hidden>
                <SplitMarkIcon mark={mark} />
              </span>
              <p className="tb-split-kicker">{kicker}</p>
            </div>
            <h2 className="tb-split-title">{title}</h2>
            {sheet && (asideBody || asideTitle) ? (
              <p className="tb-split-lede">
                {asideBody ?? asideTitle}
              </p>
            ) : null}
          </div>
          {onClose ? (
            <button type="button" aria-label="Close" className="tb-split-close" onClick={onClose}>
              ×
            </button>
          ) : null}
        </header>
        {steps?.length ? <SplitSteps steps={steps} step={step} /> : null}
        <div className="tb-split-body">{children}</div>
        {footer ? <footer className="tb-split-foot">{footer}</footer> : null}
      </div>
    </>
  );

  if (Tag === "form") {
    return (
      <form
        className={shellClass}
        data-tone={tone}
        data-variant={variant}
        onSubmit={onSubmit}
      >
        {body}
      </form>
    );
  }

  if (Tag === "section") {
    return (
      <section className={shellClass} data-tone={tone} data-variant={variant}>
        {body}
      </section>
    );
  }

  return (
    <div className={shellClass} data-tone={tone} data-variant={variant}>
      {body}
    </div>
  );
}
