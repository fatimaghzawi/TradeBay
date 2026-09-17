"use client";

import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold text-primary">
        Create account
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Start with catalog, procurement, and finance in one shell.
      </p>
      <div className="mt-6">
        <RegisterForm />
      </div>
    </div>
  );
}
