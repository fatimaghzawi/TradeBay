"use client";

import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import { useTheme } from "@/providers/ThemeProvider";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export function UserMenu({ company }: { company?: string | null }) {
  const { user, business, logout, roleName } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const name = user
    ? `${user.first_name} ${user.last_name}`.trim() || user.email
    : "Account";
  const initials = user
    ? `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase() ||
      user.email.slice(0, 2).toUpperCase()
    : "TB";
  const logoSrc = mediaUrl(business?.logo_url || user?.avatar_url);
  const verified = Boolean(user?.email_verified_at);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  function go(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "tb-account-trigger",
          open && "is-open",
        )}
      >
        <span className="tb-account-trigger__avatar">
          {logoSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoSrc} alt="" />
          ) : (
            initials
          )}
          <span
            className={cn(
              "tb-account-trigger__dot",
              verified ? "is-ok" : "is-warn",
            )}
          />
        </span>
        <span className="tb-account-trigger__copy">
          <span className="tb-account-trigger__name">{name}</span>
          <span className="tb-account-trigger__role">{roleName || "Member"}</span>
        </span>
        <svg
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden
          className={cn("tb-nav-fly-chevron", open && "is-open")}
        >
          <path
            d="M2.5 4.5 6 8l3.5-3.5"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open ? (
        <div className="tb-nav-fly tb-account-fly" role="menu" aria-label="Account menu">
          <div className="tb-nav-fly__bloom" aria-hidden />
          <header className="tb-account-fly__head">
            <span className="tb-account-fly__avatar" aria-hidden>
              {logoSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logoSrc} alt="" />
              ) : (
                initials
              )}
            </span>
            <div className="min-w-0">
              <p className="tb-account-fly__name">{name}</p>
              <p className="tb-account-fly__meta">{user?.email}</p>
              <p className="tb-account-fly__badge">{roleName || "Member"}</p>
            </div>
          </header>

          <div className="tb-nav-fly__list">
            <p className="tb-nav-fly__group-label">Account</p>
            <MenuRow
              label="Company"
              title={company || "Active business"}
              onClick={() => go(ROUTES.businesses)}
            />
            <MenuRow
              label="Profile"
              title={verified ? "Email verified" : "Verify your email"}
              onClick={() => go(ROUTES.settings)}
            />
            <MenuRow
              label="Sessions"
              title="Devices signed in"
              onClick={() => go(ROUTES.sessions)}
            />
            <MenuRow
              label={theme === "dark" ? "Light mode" : "Dark mode"}
              title="Toggle theme"
              onClick={() => toggleTheme()}
            />
          </div>

          <button
            type="button"
            className="tb-account-fly__out"
            onClick={() => {
              setOpen(false);
              void logout();
            }}
          >
            Sign out
            <span aria-hidden>→</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}

function MenuRow({
  label,
  title,
  onClick,
}: {
  label: string;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      title={title}
      onClick={onClick}
      className="tb-nav-fly__link tb-account-fly__row"
    >
      <span className="tb-nav-fly__label">{label}</span>
      <span className="tb-nav-fly__go" aria-hidden>
        →
      </span>
    </button>
  );
}
