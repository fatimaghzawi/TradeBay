"use client";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useRegisterForm } from "@/features/auth/useRegisterForm";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useState } from "react";

export function RegisterForm() {
  const { submit, errors, formError, pending } = useRegisterForm();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [businessName, setBusinessName] = useState("");

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void submit({
          first_name: firstName,
          last_name: lastName,
          email,
          password,
          confirmPassword,
          business_name: businessName,
        });
      }}
    >
      {formError ? <Alert variant="error">{formError}</Alert> : null}
      <Input
        label="First name"
        name="first_name"
        value={firstName}
        onChange={(e) => setFirstName(e.target.value)}
        error={errors.first_name}
      />
      <Input
        label="Last name"
        name="last_name"
        value={lastName}
        onChange={(e) => setLastName(e.target.value)}
        error={errors.last_name}
      />
      <Input
        label="Company name (optional)"
        name="business_name"
        value={businessName}
        onChange={(e) => setBusinessName(e.target.value)}
        error={errors.business_name}
      />
      <Input
        label="Email"
        name="email"
        type="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
      />
      <Input
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
      />
      <Input
        label="Confirm password"
        name="confirmPassword"
        type="password"
        autoComplete="new-password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        error={errors.confirmPassword}
      />
      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? "Creating account…" : "Create account"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href={ROUTES.login} className="font-medium text-secondary hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
