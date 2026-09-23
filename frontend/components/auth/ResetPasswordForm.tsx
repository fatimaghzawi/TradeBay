"use client";

import { AuthField, AuthSubmitButton } from "@/components/auth/AuthField";
import { OtpInput } from "@/components/auth/OtpInput";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { passwordSchema } from "@/lib/validation/common";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

const CODE_LEN = 6;

export function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const emailHint = params.get("email") ?? "";
  const prefill = params.get("otp") ?? params.get("code") ?? "";

  const [digits, setDigits] = useState<string[]>(() => {
    if (/^\d{6}$/.test(prefill)) return prefill.split("");
    return Array(CODE_LEN).fill("");
  });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [codeError, setCodeError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const code = useMemo(() => digits.join(""), [digits]);

  const checks = useMemo(
    () => ({
      length: password.length >= 8,
      number: /[0-9]/.test(password),
      letter: /[A-Za-z]/.test(password),
      match: password.length > 0 && password === confirm,
    }),
    [password, confirm],
  );

  const canSubmit =
    /^\d{6}$/.test(code) &&
    checks.length &&
    checks.number &&
    checks.letter &&
    checks.match;

  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        setPasswordError(null);
        setConfirmError(null);
        setCodeError(null);

        if (!/^\d{6}$/.test(code)) {
          setCodeError("Enter the 6-digit code from your email.");
          setError("Enter the 6-digit code from your email.");
          return;
        }
        const parsedPassword = passwordSchema.safeParse(password);
        if (!parsedPassword.success) {
          setPasswordError(parsedPassword.error.issues[0]?.message ?? "Invalid password");
          return;
        }
        if (password !== confirm) {
          setConfirmError("Passwords do not match");
          return;
        }

        setPending(true);
        void authApi
          .resetPassword(code, password)
          .then(() => {
            router.replace(ROUTES.resetPasswordSuccess);
          })
          .catch((err) => {
            const message =
              err instanceof ApiError ? err.message : "Reset failed.";
            const lower = message.toLowerCase();
            if (
              err instanceof ApiError &&
              (err.code === "INVALID_CREDENTIALS" ||
                lower.includes("expired") ||
                lower.includes("invalid") ||
                err.status === 401)
            ) {
              setError(
                "This code is invalid or has expired. Request a new one.",
              );
            } else {
              setError(message);
            }
          })
          .finally(() => setPending(false));
      }}
    >
      <ResetStepper active="reset" />

      <div>
        <h1 className="auth-display text-[1.95rem] sm:text-[2.25rem]">
          Set a new password
        </h1>
        <p className="auth-lede mt-2">
          Enter the 6-digit code we emailed you
          {emailHint ? (
            <>
              {" "}
              at <span className="font-semibold text-[#0d3b2a]">{emailHint}</span>
            </>
          ) : null}
          , then choose a new password.
        </p>
      </div>

      {error ? (
        <p className="rounded-xl bg-[#fef3f2] px-3.5 py-2.5 text-sm text-[#b42318] ring-1 ring-[#fecdca]">
          {error}
        </p>
      ) : null}

      <div>
        <p className="mb-2 text-sm font-semibold text-[#0d3b2a]">Reset code</p>
        <OtpInput
          length={CODE_LEN}
          value={digits}
          onChange={(next) => {
            setDigits(next);
            setError(null);
            setCodeError(null);
          }}
          disabled={pending}
        />
        {codeError ? (
          <p className="tb-hint mt-1.5" data-tone="error">
            {codeError}
          </p>
        ) : null}
      </div>

      <AuthField
        label="New password"
        name="password"
        type="password"
        icon="lock"
        autoComplete="new-password"
        placeholder="••••••••"
        value={password}
        onChange={(e) => {
          setPassword(e.target.value);
          const parsed = passwordSchema.safeParse(e.target.value);
          setPasswordError(
            e.target.value.length === 0
              ? null
              : parsed.success
                ? null
                : parsed.error.issues[0]?.message ?? null,
          );
        }}
        error={passwordError ?? undefined}
      />
      <AuthField
        label="Confirm new password"
        name="confirm"
        type="password"
        icon="lock"
        autoComplete="new-password"
        placeholder="••••••••"
        value={confirm}
        onChange={(e) => {
          setConfirm(e.target.value);
          setConfirmError(
            e.target.value.length === 0
              ? null
              : e.target.value === password
                ? null
                : "Passwords do not match",
          );
        }}
        error={confirmError ?? undefined}
      />

      <div>
        <p className="text-[0.8rem] font-semibold text-[#0d3b2a]">
          Password must:
        </p>
        <ul className="mt-2 space-y-1.5">
          <Req ok={checks.length} label="Be at least 8 characters" />
          <Req ok={checks.number} label="Include a number" />
          <Req ok={checks.letter} label="Include a letter" />
          <Req ok={checks.match} label="Passwords match" />
        </ul>
      </div>

      <AuthSubmitButton pending={pending} tone="orange" disabled={!canSubmit}>
        {pending ? "Saving…" : "Reset password"}
      </AuthSubmitButton>

      <p className="text-center text-sm text-[#5a6a62]">
        Need a new code?{" "}
        <Link
          href={ROUTES.forgotPassword}
          className="font-semibold text-[#0d3b2a] hover:underline"
        >
          Request again
        </Link>
        {" · "}
        <Link
          href={ROUTES.login}
          className="font-semibold text-[#0d3b2a] hover:underline"
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}

function Req({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2 text-sm text-[#5a6a62]">
      <span
        className={cn(
          "flex h-4 w-4 items-center justify-center rounded-full border transition",
          ok
            ? "border-[#1a6b4f] bg-[#1a6b4f] text-white shadow-[0_0_10px_-2px_rgba(26,107,79,0.7)]"
            : "border-[#c5d0c9] bg-white",
        )}
      >
        {ok ? (
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden>
            <path
              d="M2 5.2 4 7l4-4.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        ) : null}
      </span>
      {label}
    </li>
  );
}

export function ResetStepper({
  active,
}: {
  active: "request" | "verify" | "reset";
}) {
  const steps = [
    { id: "request", label: "Request" },
    { id: "verify", label: "Verify" },
    { id: "reset", label: "Reset" },
  ] as const;
  const order = { request: 0, verify: 1, reset: 2 };
  const activeIdx = order[active];

  return (
    <ol className="mb-1 flex items-start">
      {steps.map((step, i) => {
        const done = i < activeIdx;
        const current = i === activeIdx;
        return (
          <li key={step.id} className="relative flex flex-1 flex-col items-center">
            {i < steps.length - 1 ? (
              <span
                aria-hidden
                className={cn(
                  "absolute left-[calc(50%+14px)] right-[calc(-50%+14px)] top-3.5 h-0.5",
                  i < activeIdx ? "bg-[#1a6b4f]" : "bg-[#e2e8e4]",
                )}
              />
            ) : null}
            <span
              className={cn(
                "relative z-[1] flex h-7 w-7 items-center justify-center rounded-full text-[0.65rem] font-bold",
                done && "bg-[#1a6b4f] text-white",
                current && "bg-[#e86f2a] text-white",
                !done && !current && "bg-[#e8eeea] text-[#6a726c]",
              )}
            >
              {done ? (
                "✓"
              ) : current ? (
                <span className="text-sm leading-none">×</span>
              ) : (
                i + 1
              )}
            </span>
            <span
              className={cn(
                "mt-1.5 text-[0.65rem] font-semibold",
                current
                  ? "text-[#e86f2a]"
                  : done
                    ? "text-[#1a6b4f]"
                    : "text-[#8a9690]",
              )}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
