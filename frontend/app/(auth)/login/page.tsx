"use client";

import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold text-primary">
        Sign in
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Access your TradeBay workspace.
      </p>
      <div className="mt-6">
        <LoginForm />
      </div>
    </div>
  );
}
