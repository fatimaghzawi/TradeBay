"use client";

import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { AUTH_QUERY_KEY } from "@/lib/auth/session";
import { registerSchema, type RegisterFormValues } from "@/lib/validation/auth";
import { savePreferredBusinessType } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import { useToast } from "@/components/ui/Toast";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

function safeNextPath(raw: string | null): string | null {
  if (!raw) return null;
  if (!raw.startsWith("/") || raw.startsWith("//")) return null;
  return raw;
}

export function useRegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToast();
  const [errors, setErrors] = useState<
    Partial<Record<keyof RegisterFormValues, string>>
  >({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const inviteToken = searchParams.get("invite")?.trim() || "";
  const nextPath =
    safeNextPath(searchParams.get("next")) ||
    (inviteToken
      ? `${ROUTES.acceptInvitation}?token=${encodeURIComponent(inviteToken)}`
      : null);

  async function submit(values: RegisterFormValues) {
    setFormError(null);
    const parsed = registerSchema.safeParse({
      ...values,
      invitation_token: inviteToken || values.invitation_token || undefined,
    });
    if (!parsed.success) {
      const fieldErrors: Partial<Record<keyof RegisterFormValues, string>> = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0];
        if (typeof key === "string") {
          fieldErrors[key as keyof RegisterFormValues] = issue.message;
        }
      }
      setErrors(fieldErrors);
      return;
    }
    setErrors({});
    setPending(true);
    try {
      const { confirmPassword, ...payload } = parsed.data;
      void confirmPassword;
      const isInvite = Boolean(payload.invitation_token);
      await authApi.register({
        email: payload.email,
        password: payload.password,
        first_name: payload.first_name,
        last_name: payload.last_name,
        business_name: isInvite ? undefined : payload.business_name || undefined,
        business_type: isInvite ? undefined : payload.business_type,
        invitation_token: payload.invitation_token || undefined,
      });
      if (!isInvite && payload.business_type) {
        savePreferredBusinessType(payload.business_type);
      }
      void queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      if (isInvite) {
        success(
          "Account ready",
          "Your company login is verified. Accept the invitation to join your team.",
        );
      } else {
        success("Account created", "Enter the verification code we sent to your email.");
      }
      if (nextPath) {
        router.replace(nextPath);
        return;
      }
      router.replace(`/verify-email?email=${encodeURIComponent(payload.email)}`);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Couldn't create your account. Try again.";
      setFormError(message);
      toastError("Registration failed", message);
      setPending(false);
    }
  }

  return {
    submit,
    errors,
    formError,
    pending,
    inviteToken,
    isInviteSignup: Boolean(inviteToken),
  };
}
