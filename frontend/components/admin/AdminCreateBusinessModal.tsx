"use client";

import { Modal } from "@/components/ui/Modal";
import { TextField } from "@/components/ui/FormField";
import { adminCreateBusinessSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useEffect, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

type AccountType = "buyer" | "supplier";

type AdminCreateBusinessModalProps = {
  open: boolean;
  accountType: AccountType;
  onClose: () => void;
  onSubmit: (payload: {
    account_type: AccountType;
    business_name: string;
    owner_email: string;
    owner_password: string;
    owner_first_name: string;
    owner_last_name: string;
    email_domain?: string;
    legal_name?: string;
    tax_number?: string;
    contact_email?: string;
    verify_supplier?: boolean;
  }) => Promise<void>;
};

export function AdminCreateBusinessModal({
  open,
  accountType,
  onClose,
  onSubmit,
}: AdminCreateBusinessModalProps) {
  const isSupplier = accountType === "supplier";
  const label = isSupplier ? "supplier" : "buyer";

  const [businessName, setBusinessName] = useState("");
  const [emailDomain, setEmailDomain] = useState("");
  const [legalName, setLegalName] = useState("");
  const [taxNumber, setTaxNumber] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verifySupplier, setVerifySupplier] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const live = useLiveFields(adminCreateBusinessSchema, {
    business_name: businessName,
    email_domain: emailDomain,
    legal_name: legalName,
    tax_number: taxNumber,
    owner_first_name: firstName,
    owner_last_name: lastName,
    owner_email: ownerEmail,
    owner_password: password,
  });

  useEffect(() => {
    if (!open) return;
    setBusinessName("");
    setEmailDomain("");
    setLegalName("");
    setTaxNumber("");
    setFirstName("");
    setLastName("");
    setOwnerEmail("");
    setPassword("");
    setVerifySupplier(true);
    setError(null);
    setPending(false);
    live.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset only when the dialog opens
  }, [open, accountType]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      tone="brand"
      mark="shield"
      kicker="Platform"
      title={isSupplier ? "Add supplier" : "Add buyer"}
      asideTitle={`New ${label} company`}
      asideBody={
        isSupplier
          ? "Creates the company and owner admin. Leave verify on to unlock selling rights immediately."
          : "Creates the buyer company and owner admin — ready to trade."
      }
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
                account_type: accountType,
                business_name: businessName.trim(),
                owner_email: ownerEmail.trim(),
                owner_password: password,
                owner_first_name: firstName.trim(),
                owner_last_name: lastName.trim(),
                email_domain: emailDomain.trim() || undefined,
                legal_name: legalName.trim() || undefined,
                tax_number: taxNumber.trim() || undefined,
                contact_email: ownerEmail.trim(),
                verify_supplier: isSupplier ? verifySupplier : undefined,
              })
                .then(() => onClose())
                .catch((err: unknown) =>
                  setError(
                    err instanceof Error ? err.message : `Could not create ${label}.`,
                  ),
                )
                .finally(() => setPending(false));
            }}
          >
            <BusyText busy={pending}>{pending ? "Creating…" : `Create ${label}`}</BusyText>
          </button>
        </>
      }
    >
      <div className="tb-form-stack">
        <div className="tb-form-block">
          <div className="tb-form-block-head">
            <span className="tb-form-index">1</span>
            <div>
              <p className="tb-form-label">Company</p>
              <p className="tb-form-hint">Trading identity on TradeBay</p>
            </div>
          </div>
          <div className="grid gap-3">
            <TextField
              label="Company name"
              name="business_name"
              required
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              onBlur={() => live.touch("business_name")}
              error={live.errors.business_name}
              placeholder="Company name"
              autoComplete="off"
            />
            <TextField
              label="Email domain"
              name="email_domain"
              value={emailDomain}
              onChange={(e) => setEmailDomain(e.target.value)}
              onBlur={() => live.touch("email_domain")}
              error={live.errors.email_domain}
              placeholder="Company domain (e.g. safawi.com)"
              autoComplete="off"
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField
                label="Legal name"
                name="legal_name"
                value={legalName}
                onChange={(e) => setLegalName(e.target.value)}
                onBlur={() => live.touch("legal_name")}
                error={live.errors.legal_name}
                placeholder="Legal name (optional)"
                autoComplete="off"
              />
              <TextField
                label="Tax number"
                name="tax_number"
                value={taxNumber}
                onChange={(e) => setTaxNumber(e.target.value)}
                onBlur={() => live.touch("tax_number")}
                error={live.errors.tax_number}
                placeholder="Tax number (optional)"
                autoComplete="off"
              />
            </div>
          </div>
        </div>

        <div className="tb-form-block">
          <div className="tb-form-block-head">
            <span className="tb-form-index">2</span>
            <div>
              <p className="tb-form-label">Owner admin</p>
              <p className="tb-form-hint">Signs in with a company-domain email</p>
            </div>
          </div>
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField
                label="First name"
                name="owner_first_name"
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                onBlur={() => live.touch("owner_first_name")}
                error={live.errors.owner_first_name}
                placeholder="First name"
                autoComplete="off"
              />
              <TextField
                label="Last name"
                name="owner_last_name"
                required
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                onBlur={() => live.touch("owner_last_name")}
                error={live.errors.owner_last_name}
                placeholder="Last name"
                autoComplete="off"
              />
            </div>
            <TextField
              label="Owner email"
              name="owner_email"
              type="email"
              required
              value={ownerEmail}
              onChange={(e) => setOwnerEmail(e.target.value)}
              onBlur={() => live.touch("owner_email")}
              error={live.errors.owner_email}
              placeholder="admin@company.com"
              autoComplete="off"
            />
            <TextField
              label="Password"
              name="owner_password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => live.touch("owner_password")}
              error={live.errors.owner_password}
              placeholder="Initial password"
              autoComplete="new-password"
              hint="At least 8 characters, including a letter and a number"
            />
          </div>
        </div>

        {isSupplier ? (
          <label className="flex items-start gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              className="mt-1"
              checked={verifySupplier}
              onChange={(e) => setVerifySupplier(e.target.checked)}
            />
            <span>
              <strong className="font-semibold">Verify selling rights now</strong>
              <span className="mt-0.5 block text-muted-foreground">
                Skip the document review queue for this provisioned supplier.
              </span>
            </span>
          </label>
        ) : null}

        {error ? <p className="tb-form-alert">{error}</p> : null}
      </div>
    </Modal>
  );
}
