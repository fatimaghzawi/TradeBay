"use client";

import { Modal } from "@/components/ui/Modal";
import { TextField } from "@/components/ui/FormField";
import { adminCreateUserSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useEffect, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

type AdminCreateUserModalProps = {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) => Promise<void>;
};

export function AdminCreateUserModal({
  open,
  onClose,
  onSubmit,
}: AdminCreateUserModalProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const live = useLiveFields(adminCreateUserSchema, {
    first_name: firstName,
    last_name: lastName,
    email,
    password,
  });

  useEffect(() => {
    if (!open) return;
    setEmail("");
    setPassword("");
    setFirstName("");
    setLastName("");
    setError(null);
    setPending(false);
    live.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset field state when the dialog opens
  }, [open]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      tone="brand"
      mark="shield"
      kicker="Platform"
      title="Add user"
      asideTitle="Create a login"
      asideBody="Active and verified immediately. Share the password securely — they can change it after sign-in."
      footer={
        <>
          <button type="button" className="tb-btn tb-btn--outline" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="tb-btn tb-btn--primary"
            disabled={pending}
            aria-busy={pending || undefined}
            onClick={() => {
              if (pending) return;
              if (!live.finish()) return;
              setError(null);
              setPending(true);
              void onSubmit({
                email: email.trim(),
                password,
                first_name: firstName.trim(),
                last_name: lastName.trim(),
              })
                .then(() => onClose())
                .catch((err: unknown) =>
                  setError(err instanceof Error ? err.message : "Could not create user."),
                )
                .finally(() => setPending(false));
            }}
          >
            <BusyText busy={pending}>{pending ? "Creating…" : "Create user"}</BusyText>
          </button>
        </>
      }
    >
      <div className="tb-form-stack">
        <div className="tb-form-block">
          <div className="tb-form-block-head">
            <span className="tb-form-index">1</span>
            <div>
              <p className="tb-form-label">Person</p>
              <p className="tb-form-hint">Name on the TradeBay account</p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField
              label="First name"
              name="first_name"
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              onBlur={() => live.touch("first_name")}
              error={live.errors.first_name}
              placeholder="First name"
              autoComplete="off"
            />
            <TextField
              label="Last name"
              name="last_name"
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              onBlur={() => live.touch("last_name")}
              error={live.errors.last_name}
              placeholder="Last name"
              autoComplete="off"
            />
          </div>
        </div>
        <div className="tb-form-block">
          <div className="tb-form-block-head">
            <span className="tb-form-index">2</span>
            <div>
              <p className="tb-form-label">Sign-in</p>
              <p className="tb-form-hint">Email + initial password</p>
            </div>
          </div>
          <div className="grid gap-3">
            <TextField
              label="Email"
              name="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => live.touch("email")}
              error={live.errors.email}
              placeholder="name@company.com"
              autoComplete="off"
            />
            <TextField
              label="Password"
              name="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => live.touch("password")}
              error={live.errors.password}
              placeholder="Initial password"
              autoComplete="new-password"
              hint="At least 8 characters, including a letter and a number"
            />
          </div>
        </div>
        {error ? <p className="tb-form-alert">{error}</p> : null}
      </div>
    </Modal>
  );
}
