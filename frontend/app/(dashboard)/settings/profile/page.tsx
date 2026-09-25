"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";
import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { TextField } from "@/components/ui/FormField";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { identityApi } from "@/lib/api/identityApi";
import { profileSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";
import { BackLink } from "@/components/ui/BackLink";

export default function ProfilePage() {
  const { user, business, refreshSession } = useAuth();
  const { success, error: toastError } = useToast();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const live = useLiveFields(profileSchema, {
    first_name: firstName,
    last_name: lastName,
  });

  useEffect(() => {
    setFirstName(user?.first_name ?? "");
    setLastName(user?.last_name ?? "");
  }, [user]);

  const verified = Boolean(user?.email_verified_at);
  const logoSrc = mediaUrl(business?.logo_url || user?.avatar_url);
  const displayName =
    `${user?.first_name ?? ""} ${user?.last_name ?? ""}`.trim() || user?.email || "You";

  return (
    <IdentityPageShell
      crumb="Account / Profile"
      title="My Profile"
      lede="Your profile image is your company logo. Update your name and check whether your email is verified."
      banner={{
        icon: verified ? "✓" : "!",
        title: verified ? "Email verified." : "Email still needs verification.",
        body: verified
          ? "Your account is ready for trading features your role allows."
          : "Resend a code below, then enter it on the verification screen.",
      }}
      stats={[
        {
          icon: "✉",
          tone: "teal",
          value: user?.email ?? "—",
          label: "Email",
        },
        {
          icon: verified ? "✓" : "!",
          tone: verified ? "green" : "rose",
          value: verified ? "Verified" : "Unverified",
          label: "Status",
        },
        {
          icon: "☺",
          tone: "orange",
          value: user?.status ?? "—",
          label: "Account",
        },
      ]}
      quote="“Your name on the quay should match the person behind the desk.”"
    >
      <p className="mb-2">
        <BackLink href={ROUTES.settings}>Account settings</BackLink>
      </p>

      <ul className="tb-roles-list mb-3">
        <li className="tb-roles-row">
          <span
            className="tb-roles-glyph"
            data-tone="sales"
            data-logo={logoSrc ? "true" : undefined}
            aria-hidden
          >
            {logoSrc ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logoSrc} alt="" />
            ) : (
              displayName
                .split(/\s+/)
                .filter(Boolean)
                .slice(0, 2)
                .map((p) => p[0]?.toUpperCase() ?? "")
                .join("")
            )}
          </span>
          <div className="tb-roles-row-main min-w-0 flex-1">
            <p className="tb-roles-row-name">{displayName}</p>
            <p className="tb-roles-row-desc">
              {business?.name
                ? `Company logo · ${business.name}`
                : "Company logo appears once you join a business"}
            </p>
          </div>
          <StatusBadge status="profile" tone="info" />
        </li>
      </ul>

      {error ? (
        <div className="mt-2">
          <FeedbackBanner
            tone="error"
            title="Couldn’t save profile"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {verifyError ? (
        <div className="mt-2">
          <FeedbackBanner
            tone="error"
            title="Verification failed"
            onDismiss={() => setVerifyError(null)}
          >
            {verifyError}
          </FeedbackBanner>
        </div>
      ) : null}

      <ul className="tb-roles-list">
        <li className="tb-roles-row">
          <span className="tb-roles-glyph" data-tone="finance" aria-hidden>
            ✉
          </span>
          <div className="tb-roles-row-main min-w-0 flex-1">
            <p className="tb-roles-row-name">{user?.email}</p>
            <p className="tb-roles-row-desc">Primary sign-in email</p>
          </div>
          <StatusBadge
            status={verified ? "verified" : "pending"}
            label={verified ? "Verified" : "Unverified"}
          />
          {!verified ? (
            <button
              type="button"
              className="text-sm font-bold text-accent hover:underline"
              onClick={() => {
                setVerifyError(null);
                void authApi
                  .resendVerification()
                  .then(() => {
                    success(
                      "Verification sent",
                      "Check your inbox for a new verification code.",
                    );
                  })
                  .catch((err) => {
                    const message =
                      err instanceof ApiError
                        ? err.message
                        : "Couldn't resend.";
                    setVerifyError(message);
                    toastError("Resend failed", message);
                  });
              }}
            >
              Resend →
            </button>
          ) : null}
        </li>
      </ul>

      <form
        className="mt-4 space-y-4 rounded-[1rem] border border-border bg-card p-5"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          if (!live.finish()) return;
          setPending(true);
          void identityApi
            .updateProfile({
              first_name: firstName.trim(),
              last_name: lastName.trim(),
            })
            .then(async () => {
              success("Profile updated", "Your name was saved.");
              await refreshSession();
            })
            .catch((err) => {
              const message =
                err instanceof ApiError
                  ? err.message
                  : "Couldn't update profile.";
              setError(message);
              toastError("Couldn't save", message);
            })
            .finally(() => setPending(false));
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField
            label="First name"
            name="first_name"
            required
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            onBlur={() => live.touch("first_name")}
            error={live.errors.first_name}
          />
          <TextField
            label="Last name"
            name="last_name"
            required
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            onBlur={() => live.touch("last_name")}
            error={live.errors.last_name}
          />
        </div>
        <button
          type="submit"
          disabled={pending}
          className="tb-btn tb-btn--primary"
         aria-busy={pending || undefined}>
          <BusyText busy={pending}>{pending ? "Saving…" : "Save profile"}</BusyText>
        </button>
      </form>
    </IdentityPageShell>
  );
}
