"use client";

import { AuthSubmitButton } from "@/components/auth/AuthField";
import { OtpInput } from "@/components/auth/OtpInput";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

const CODE_LEN = 6;
/** Matches backend EMAIL_VERIFY_TTL_MINUTES */
const OTP_WINDOW_SECONDS = 15 * 60;
const RESEND_COOLDOWN_SECONDS = 45;
/** Matches backend AUTH_TOKEN_MAX_ATTEMPTS */
const MAX_ATTEMPTS = 5;

function formatClock(total: number) {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function remainingFromError(err: unknown): number | null {
  if (!(err instanceof ApiError) || !err.details || typeof err.details !== "object") {
    return null;
  }
  const remaining = (err.details as { remaining_attempts?: unknown }).remaining_attempts;
  return typeof remaining === "number" ? remaining : null;
}

export function VerifyEmailForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { success, error: toastError } = useToast();
  const emailHint = params.get("email") ?? "";
  const prefill = params.get("otp") ?? params.get("code") ?? "";

  const [digits, setDigits] = useState<string[]>(() => {
    if (/^\d{6}$/.test(prefill)) return prefill.split("");
    return Array(CODE_LEN).fill("");
  });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [expired, setExpired] = useState(false);
  const [locked, setLocked] = useState(false);
  const [attemptsLeft, setAttemptsLeft] = useState(MAX_ATTEMPTS);
  const [secondsLeft, setSecondsLeft] = useState(OTP_WINDOW_SECONDS);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resentFlash, setResentFlash] = useState(false);
  const [resending, setResending] = useState(false);

  const code = useMemo(() => digits.join(""), [digits]);
  const canResend = resendCooldown === 0 && !resending;
  const inputBlocked = expired || locked || pending;

  const restartWindow = useCallback(() => {
    setSecondsLeft(OTP_WINDOW_SECONDS);
    setExpired(false);
    setLocked(false);
    setAttemptsLeft(MAX_ATTEMPTS);
    setError(null);
    setDigits(Array(CODE_LEN).fill(""));
  }, []);

  useEffect(() => {
    if (expired || locked || secondsLeft <= 0) return;
    const id = window.setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          setExpired(true);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [expired, locked, secondsLeft]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const id = window.setInterval(() => {
      setResendCooldown((s) => Math.max(0, s - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [resendCooldown]);

  const goSuccess = useCallback(
    (email?: string) => {
      const q = email ? `?email=${encodeURIComponent(email)}` : "";
      router.replace(`${ROUTES.verifyEmailSuccess}${q}`);
    },
    [router],
  );

  const verify = useCallback(
    async (value: string) => {
      if (!/^\d{6}$/.test(value)) {
        setError("Enter the 6-digit code from your email.");
        return;
      }
      if (expired) {
        setError("This code has expired. Resend a new code to continue.");
        return;
      }
      if (locked) {
        setError("Too many incorrect codes. Resend a new code to continue.");
        return;
      }
      setError(null);
      setPending(true);
      try {
        const result = await authApi.verifyEmail(value, emailHint || undefined);
        success("Email verified", "Your account is ready to use.");
        goSuccess(result.user.email || emailHint || undefined);
      } catch (err) {
        if (err instanceof ApiError && err.code === "OTP_ATTEMPTS_EXCEEDED") {
          setLocked(true);
          setAttemptsLeft(0);
          const message =
            err.message ||
            "Too many incorrect codes. Resend a new code to continue.";
          setError(message);
          toastError("Too many attempts", message);
        } else if (err instanceof ApiError && err.code === "OTP_INVALID") {
          const remaining = remainingFromError(err);
          if (remaining !== null) {
            setAttemptsLeft(remaining);
            setError(
              remaining > 0
                ? `Incorrect code. ${remaining} of ${MAX_ATTEMPTS} attempts remaining.`
                : err.message,
            );
          } else {
            setAttemptsLeft((n) => Math.max(0, n - 1));
            setError(err.message || "Incorrect verification code. Try again.");
          }
          setDigits(Array(CODE_LEN).fill(""));
        } else if (
          err instanceof ApiError &&
          (err.message.toLowerCase().includes("expired") ||
            err.code === "INVALID_CREDENTIALS")
        ) {
          // Only lock the UI for true expiry / exhausted challenge — not a single typo.
          const msg = err.message.toLowerCase();
          if (msg.includes("expired") || msg.includes("too many")) {
            setExpired(true);
            setError("This code has expired. Resend a new code to continue.");
          } else {
            setAttemptsLeft((n) => Math.max(0, n - 1));
            setError("Incorrect verification code. Try again.");
            setDigits(Array(CODE_LEN).fill(""));
          }
        } else {
          setError(
            err instanceof ApiError ? err.message : "Verification failed.",
          );
        }
      } finally {
        setPending(false);
      }
    },
    [emailHint, expired, goSuccess, locked, success, toastError],
  );

  async function handleResend() {
    if (!canResend) return;
    if (!emailHint) {
      setError(
        "We need your email to resend a code. Register again or open this page from the link after signup.",
      );
      return;
    }
    setResending(true);
    setError(null);
    setResentFlash(false);
    try {
      await authApi.resendVerificationEmail(emailHint);
      restartWindow();
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
      setResentFlash(true);
      success("Code sent", `Check ${emailHint} for a new verification code.`);
    } catch (err) {
      try {
        await authApi.resendVerification();
        restartWindow();
        setResendCooldown(RESEND_COOLDOWN_SECONDS);
        setResentFlash(true);
        success("Code sent", "Check your inbox for a new verification code.");
      } catch {
        const message =
          err instanceof ApiError
            ? err.message
            : "Couldn't resend. Check your email address and try again.";
        setError(message);
        toastError("Resend failed", message);
      }
    } finally {
      setResending(false);
    }
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void verify(code);
      }}
    >
      <div>
        <h1 className="auth-display text-[1.95rem] sm:text-[2.25rem]">
          Verify your email
        </h1>
        <p className="auth-lede mt-2">
          We&apos;ve sent a verification code to{" "}
          <span className="font-semibold text-[#0d3b2a]">
            {emailHint || "your email"}
          </span>
          . Enter the code below to verify your email.
        </p>
      </div>

      <div
        className={cn(
          "flex items-center justify-between rounded-xl px-3.5 py-2.5 text-sm",
          expired || locked
            ? "bg-[#fef3f2] text-[#b42318] ring-1 ring-[#fecdca]"
            : "bg-[#eef6f2] text-[#0d3b2a] ring-1 ring-[#d4e0da]",
        )}
        role="status"
      >
        {locked ? (
          <span className="font-medium">Attempts used up</span>
        ) : expired ? (
          <span className="font-medium">Code expired</span>
        ) : (
          <span>
            Code expires in{" "}
            <span className="font-semibold tabular-nums">
              {formatClock(secondsLeft)}
            </span>
          </span>
        )}
        {locked || expired ? (
          <span className="text-xs font-semibold">Resend required</span>
        ) : (
          <span className="text-xs font-medium text-[#5a6a62]">
            {attemptsLeft} of {MAX_ATTEMPTS} attempts left
          </span>
        )}
      </div>

      {resentFlash ? (
        <p className="rounded-xl bg-[#eef6f2] px-3.5 py-2.5 text-sm text-[#0d3b2a] ring-1 ring-[#d4e0da]">
          A new code was sent{emailHint ? ` to ${emailHint}` : ""}. Check your
          inbox. You have {MAX_ATTEMPTS} attempts again.
        </p>
      ) : null}

      {error ? (
        <p className="rounded-xl bg-[#fef3f2] px-3.5 py-2.5 text-sm text-[#b42318] ring-1 ring-[#fecdca]">
          {error}
        </p>
      ) : null}

      <OtpInput
        length={CODE_LEN}
        value={digits}
        onChange={(next) => {
          setDigits(next);
          setError(null);
        }}
        onComplete={(full) => {
          if (!inputBlocked) void verify(full);
        }}
        disabled={inputBlocked}
        error={Boolean(error) || expired || locked}
      />

      <p className="text-sm text-[#5a6a62]">
        Didn&apos;t receive the code?{" "}
        <button
          type="button"
          disabled={!canResend || !emailHint}
          onClick={() => void handleResend()}
          className={cn(
            "font-semibold underline-offset-2",
            canResend && emailHint
              ? "text-[#0d3b2a] hover:underline"
              : "cursor-not-allowed text-[#5a6a62]",
          )}
        >
          {resending
            ? "Sending…"
            : resendCooldown > 0
              ? `Resend in ${resendCooldown}s`
              : "Resend code"}
        </button>
      </p>

      {!emailHint ? (
        <p className="text-xs text-[#5a6a62]">
          After registering you&apos;ll land here with your email. You can also
          resend once we know which address to use.
        </p>
      ) : null}

      <AuthSubmitButton
        pending={pending}
        tone="orange"
        disabled={inputBlocked || code.length < CODE_LEN}
      >
        {pending ? "Verifying…" : "Verify"}
      </AuthSubmitButton>

      {expired || locked ? (
        <button
          type="button"
          onClick={() => void handleResend()}
          disabled={!canResend || !emailHint}
          className="inline-flex h-11 w-full items-center justify-center rounded-[0.7rem] border border-[#d4e0da] bg-white text-sm font-semibold text-[#0d3b2a] transition hover:bg-[#eef6f2] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {resending ? "Sending new code…" : "Send a new code"}
        </button>
      ) : null}

      <p className="text-center text-sm">
        <Link
          href={ROUTES.login}
          className="font-semibold text-[#0d3b2a] hover:underline"
        >
          Back to sign in
        </Link>
      </p>
    </form>
  );
}
