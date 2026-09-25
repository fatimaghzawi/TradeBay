import Link from "next/link";
import type { ReactNode } from "react";

type Props = {
  href?: string;
  children?: ReactNode;
  onClick?: () => void;
  className?: string;
  "aria-label"?: string;
};

export function BackLink({ href, children, onClick, className, ...rest }: Props) {
  const iconOnly = children == null || children === "";
  const cls = ["tb-back", iconOnly ? "tb-back--icon" : "", className].filter(Boolean).join(" ");
  const body = (
    <>
      <span className="tb-back__arrow" aria-hidden>
        <i />
      </span>
      {children ? <span className="tb-back__label">{children}</span> : null}
    </>
  );
  if (href) {
    return (
      <Link href={href} className={cls} aria-label={rest["aria-label"]} onClick={onClick}>
        {body}
      </Link>
    );
  }
  return (
    <button type="button" className={cls} onClick={onClick} aria-label={rest["aria-label"]}>
      {body}
    </button>
  );
}
