"use client";

import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { TextField } from "@/components/ui/FormField";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { changePasswordSchema } from "@/lib/validation/auth";
import { useLiveFields } from "@/lib/validation/live";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

export default function ChangePasswordPage() {
  const { logout } = useAuth();
  const { success, error: toastError } = useToast();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const live = useLiveFields(changePasswordSchema, {
    current_password: currentPassword,
    new_password: newPassword,
    confirmPassword,
  });

  return (
    <IdentityPageShell
      crumb="Account / Password"
      title="Change Password"
      lede="Enter your current password and choose a new one. All sessions are revoked after a successful change."
      banner={{
        icon: "⛨",
        title: "A fresh lock for the quay.",
        body: "You’ll be signed out everywhere so only the new password can get back in.",
      }}
      quote="“Strong passwords keep every shipment honest.”"
    >
      <p className="mb-2">
        <Link
          href={ROUTES.settings}
          className="text-sm font-semibold text-[var(--tb-accent)] hover:underline"
        >
          ← Account settings
        </Link>
      </p>

      <form
        className="mx-auto max-w-lg space-y-4 rounded-[1rem] border border-[var(--tb-line)] bg-[var(--tb-surface)] p-5"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          if (!live.finish()) return;
          const parsed = changePasswordSchema.safeParse({
            current_password: currentPassword,
            new_password: newPassword,
            confirmPassword,
          });
          if (!parsed.success) {
            return;
          }
          setPending(true);
          void authApi
            .changePassword(
              parsed.data.current_password,
              parsed.data.new_password,
            )
            .then(() => {
              success(
                "Password updated",
                "You’ll be signed out so you can log in with the new password.",
              );
              void logout();
            })
            .catch((err) => {
              const message =
                err instanceof ApiError
                  ? err.message
                  : "Couldn't change password.";
              setError(message);
              toastError("Couldn't save", message);
            })
            .finally(() => setPending(false));
        }}
      >
        <TextField
          label="Current password"
          name="current_password"
          type="password"
          autoComplete="current-password"
          required
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          onBlur={() => live.touch("current_password")}
          error={live.errors.current_password}
        />
        <TextField
          label="New password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          required
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          onBlur={() => live.touch("new_password")}
          error={live.errors.new_password}
        />
        <TextField
          label="Confirm new password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          onBlur={() => live.touch("confirmPassword")}
          error={live.errors.confirmPassword}
        />
        {error ? (
          <p className="rounded-xl bg-[#fef3f2] px-3 py-2 text-sm text-[#b42318]">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={pending}
          className="tb-ov-btn-primary w-full disabled:opacity-60"
         aria-busy={pending || undefined}>
          <BusyText busy={pending}>{pending ? "Updating…" : "Update password"}</BusyText>
        </button>
      </form>
    </IdentityPageShell>
  );
}
