"use client";

import {
  AuthCheckbox,
  AuthField,
  AuthSelect,
  AuthSubmitButton,
} from "@/components/auth/AuthField";
import { Alert } from "@/components/ui/Alert";
import { useRegisterForm } from "@/features/auth/useRegisterForm";
import { ApiError } from "@/lib/api/client";
import { registerSchema } from "@/lib/validation/auth";
import { useLiveFields } from "@/lib/validation/live";
import { identityApi, type InvitationPreview } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

const BUSINESS_TYPES = [
  { value: "buyer", label: "Buyer" },
  { value: "supplier", label: "Supplier" },
];

export function RegisterForm() {
  const { submit, errors: submitErrors, formError, pending, inviteToken, isInviteSignup } =
    useRegisterForm();
  const searchParams = useSearchParams();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [termsError, setTermsError] = useState<string | null>(null);
  const [invitePreview, setInvitePreview] = useState<InvitationPreview | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const live = useLiveFields(registerSchema, {
    first_name: firstName,
    last_name: lastName,
    email,
    password,
    confirmPassword,
    business_name: isInviteSignup ? undefined : businessName,
    business_type: isInviteSignup ? undefined : (businessType as "buyer" | "supplier" | undefined),
    invitation_token: inviteToken || undefined,
  });
  const errors = { ...submitErrors, ...live.errors };

  useEffect(() => {
    const fromQuery = searchParams.get("email")?.trim();
    if (fromQuery && !inviteToken) {
      setEmail(fromQuery);
    }
  }, [searchParams, inviteToken]);

  useEffect(() => {
    if (!inviteToken) {
      setInvitePreview(null);
      setInviteError(null);
      return;
    }
    void identityApi
      .previewInvitation(inviteToken)
      .then((preview) => {
        setInvitePreview(preview);
        setInviteError(null);
        if (preview.invited_email) {
          setEmail(preview.invited_email);
        }
      })
      .catch((err) => {
        setInvitePreview(null);
        setInviteError(
          err instanceof ApiError
            ? err.message
            : "This invitation link is invalid or expired.",
        );
      });
  }, [inviteToken]);

  const loginHref = useMemo(() => {
    const acceptNext = inviteToken
      ? `${ROUTES.acceptInvitation}?token=${encodeURIComponent(inviteToken)}`
      : "";
    const params = new URLSearchParams();
    if (acceptNext) params.set("next", acceptNext);
    if (email) params.set("email", email);
    const qs = params.toString();
    return qs ? `${ROUTES.login}?${qs}` : ROUTES.login;
  }, [email, inviteToken]);

  return (
    <form
      className="space-y-1.5 sm:space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!accepted) {
          setTermsError("Please accept the Terms & Privacy Policy.");
          return;
        }
        setTermsError(null);
        if (!live.finish()) return;
        void submit({
          first_name: firstName,
          last_name: lastName,
          email,
          password,
          confirmPassword,
          business_name: isInviteSignup ? undefined : businessName,
          business_type: isInviteSignup
            ? undefined
            : (businessType as "buyer" | "supplier" | undefined),
          invitation_token: inviteToken || undefined,
        });
      }}
    >
      <div>
        <p className="auth-kicker">
          {isInviteSignup ? "Invitation" : "Get started"}
        </p>
        <h1 className="auth-display mt-1 text-[1.45rem] leading-tight sm:mt-1.5 sm:text-[1.95rem]">
          {isInviteSignup ? "Join your team" : "Create your account"}
        </h1>
        {isInviteSignup ? (
          <p className="auth-lede mt-1.5 text-[0.85rem]">
            Create your company login, then accept the invitation. Your role is already set.
          </p>
        ) : null}
      </div>

      {isInviteSignup && invitePreview ? (
        <div className="rounded-xl border border-input bg-muted px-3 py-2.5 text-[0.8rem] text-muted-foreground">
          Joining{" "}
          <span className="font-[family-name:var(--font-syne)] font-bold text-heading">
            {invitePreview.business_name ?? "a TradeBay business"}
          </span>
          {invitePreview.role_name ? (
            <>
              {" "}
              as{" "}
              <span className="font-semibold text-link">
                {invitePreview.role_name}
              </span>
            </>
          ) : null}
          .
        </div>
      ) : null}

      {inviteError ? <Alert variant="error">{inviteError}</Alert> : null}
      {formError ? <Alert variant="error">{formError}</Alert> : null}

      <div className="grid gap-2.5 sm:grid-cols-2">
        <AuthField
          size="sm"
          label="First name"
          name="first_name"
          icon="user"
          autoComplete="given-name"
          placeholder="Sara"
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          onBlur={() => live.touch("first_name")}
          error={errors.first_name}
        />
        <AuthField
          size="sm"
          label="Last name"
          name="last_name"
          icon="user"
          autoComplete="family-name"
          placeholder="Ahmad"
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          onBlur={() => live.touch("last_name")}
          error={errors.last_name}
        />
      </div>

      <AuthField
        size="sm"
        label={isInviteSignup ? "Company login email" : "Personal email"}
        name="email"
        type="email"
        icon="mail"
        autoComplete="email"
        placeholder={isInviteSignup ? "you@company.com" : "you@gmail.com"}
        value={email}
        onChange={(e) => {
          if (!isInviteSignup) setEmail(e.target.value);
        }}
        onBlur={() => live.touch("email")}
        error={errors.email}
        readOnly={isInviteSignup}
      />
      {isInviteSignup ? (
        <p className="-mt-1 text-[0.72rem] leading-snug text-muted-foreground">
          This is the company login from the invitation — not your Gmail. Set a password;
          no verification code is needed.
        </p>
      ) : null}

      <div className="grid gap-2.5 sm:grid-cols-2">
        <AuthField
          size="sm"
          label="Password"
          name="password"
          type="password"
          icon="lock"
          autoComplete="new-password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => live.touch("password")}
          error={errors.password}
        />
        <AuthField
          size="sm"
          label="Confirm password"
          name="confirmPassword"
          type="password"
          icon="lock"
          autoComplete="new-password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          onBlur={() => live.touch("confirmPassword")}
          error={errors.confirmPassword}
        />
      </div>

      {!isInviteSignup ? (
        <div className="grid gap-2.5 sm:grid-cols-2">
          <AuthField
            size="sm"
            label="Business name"
            name="business_name"
            icon="briefcase"
            placeholder="Your company"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            onBlur={() => live.touch("business_name")}
            error={errors.business_name}
          />
          <AuthSelect
            size="sm"
            label="I want to"
            name="business_type"
            value={businessType}
            onChange={(e) => setBusinessType(e.target.value)}
            onBlur={() => live.touch("business_type")}
            options={BUSINESS_TYPES}
            placeholder="Select buyer or supplier"
            error={errors.business_type}
          />
        </div>
      ) : null}

      <div className="pt-0.5">
        <AuthCheckbox
          id="terms"
          checked={accepted}
          onChange={(v) => {
            setAccepted(v);
            if (v) setTermsError(null);
          }}
          label={
            <span className="text-[0.78rem] leading-snug text-muted-foreground">
              I have read and agree to the TradeBay{" "}
              <Link
                href={ROUTES.terms}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="font-semibold text-heading underline decoration-heading/35 underline-offset-[3px] transition hover:decoration-heading"
              >
                Terms &amp; Conditions
              </Link>{" "}
              and{" "}
              <Link
                href={ROUTES.privacy}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="font-semibold text-heading underline decoration-heading/35 underline-offset-[3px] transition hover:decoration-heading"
              >
                Privacy Policy
              </Link>
              .
            </span>
          }
        />
        {termsError ? (
          <p className="mt-1 text-xs text-destructive">{termsError}</p>
        ) : null}
      </div>

      <AuthSubmitButton
        pending={pending || Boolean(inviteToken && !invitePreview && !inviteError)}
        tone="orange"
        size="sm"
      >
        {pending
          ? "Creating account…"
          : isInviteSignup
            ? "Create account & continue"
            : "Create account"}
      </AuthSubmitButton>

      <p className="text-center text-[0.8rem] text-muted-foreground">
        Already have an account?{" "}
        <Link href={loginHref} className="font-semibold text-heading hover:underline">
          Log in
        </Link>
      </p>
    </form>
  );
}
