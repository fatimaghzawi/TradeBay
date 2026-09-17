"use client";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { useLoginForm } from "@/features/auth/useLoginForm";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useState } from "react";

export function LoginForm() {
  const { submit, errors, formError, pending } = useLoginForm();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void submit({ email, password });
      }}
    >
      {formError ? <Alert variant="error">{formError}</Alert> : null}
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
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
      />
      <div className="flex items-center justify-between text-sm">
        <Link href={ROUTES.forgotPassword} className="text-secondary hover:underline">
          Forgot password?
        </Link>
      </div>
      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? "Signing in…" : "Sign in"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        No account?{" "}
        <Link href={ROUTES.register} className="font-medium text-secondary hover:underline">
          Register
        </Link>
      </p>
    </form>
  );
}
