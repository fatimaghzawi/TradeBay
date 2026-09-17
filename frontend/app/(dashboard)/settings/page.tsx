"use client";

import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { identityApi } from "@/lib/api/identityApi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { changePasswordSchema } from "@/lib/validation/auth";
import { useAuth } from "@/providers/AuthProvider";
import { useState } from "react";

export default function SettingsPage() {
  const { user, refreshSession, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [taxNumber, setTaxNumber] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [businessError, setBusinessError] = useState<string | null>(null);
  const [businessMessage, setBusinessMessage] = useState<string | null>(null);
  const [verifyMessage, setVerifyMessage] = useState<string | null>(null);

  const verified = Boolean(user?.email_verified_at);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-primary">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Identity settings for this account. Permission checks stay on the server.
        </p>
      </div>

      <Card className="space-y-3 p-4">
        <h2 className="text-lg font-medium">Email verification</h2>
        {verified ? (
          <Alert variant="success">Email verified. Commercial writes are allowed when you also hold the required permission.</Alert>
        ) : (
          <>
            <Alert variant="warning">
              Your email is not verified. You can sign in, but commercial writes are blocked until you verify.
            </Alert>
            {verifyMessage ? <Alert variant="success">{verifyMessage}</Alert> : null}
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                void authApi
                  .resendVerification()
                  .then(() => setVerifyMessage("A new verification token was sent."))
                  .catch((err) =>
                    setVerifyMessage(err instanceof ApiError ? err.message : "Unable to resend."),
                  );
              }}
            >
              Resend verification
            </Button>
          </>
        )}
      </Card>

      <Card className="space-y-3 p-4">
        <h2 className="text-lg font-medium">Change password</h2>
        {passwordError ? <Alert variant="error">{passwordError}</Alert> : null}
        {passwordMessage ? <Alert variant="success">{passwordMessage}</Alert> : null}
        <form
          className="grid max-w-md gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setPasswordError(null);
            setPasswordMessage(null);
            const parsed = changePasswordSchema.safeParse({
              current_password: currentPassword,
              new_password: newPassword,
              confirmPassword,
            });
            if (!parsed.success) {
              setPasswordError(parsed.error.issues[0]?.message ?? "Invalid password");
              return;
            }
            void authApi
              .changePassword(parsed.data.current_password, parsed.data.new_password)
              .then(() => {
                setPasswordMessage("Password updated. Sign in again.");
                void logout();
              })
              .catch((err) =>
                setPasswordError(err instanceof ApiError ? err.message : "Unable to change password."),
              );
          }}
        >
          <Input
            label="Current password"
            name="current_password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
          <Input
            label="New password"
            name="new_password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <Input
            label="Confirm new password"
            name="confirm_password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
          <Button type="submit">Update password</Button>
        </form>
      </Card>

      <Card className="space-y-3 p-4">
        <h2 className="text-lg font-medium">Create another business</h2>
        <p className="text-sm text-muted-foreground">
          Requires a verified email. You become Business Admin of the new company. Roles stay isolated per business.
        </p>
        {businessError ? <Alert variant="error">{businessError}</Alert> : null}
        {businessMessage ? <Alert variant="success">{businessMessage}</Alert> : null}
        <form
          className="grid max-w-md gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setBusinessError(null);
            setBusinessMessage(null);
            void identityApi
              .createBusiness({
                name: businessName,
                legal_name: legalName || undefined,
                tax_number: taxNumber || undefined,
                contact_email: contactEmail || undefined,
              })
              .then((business) => {
                setBusinessMessage(`Created ${business.name}. Switch to it from the top bar.`);
                setBusinessName("");
                void refreshSession();
              })
              .catch((err) =>
                setBusinessError(
                  err instanceof ApiError ? err.message : "Unable to create business.",
                ),
              );
          }}
        >
          <Input
            label="Display name"
            name="business_name"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
          />
          <Input
            label="Legal name"
            name="legal_name"
            value={legalName}
            onChange={(e) => setLegalName(e.target.value)}
          />
          <Input
            label="Tax number"
            name="tax_number"
            value={taxNumber}
            onChange={(e) => setTaxNumber(e.target.value)}
          />
          <Input
            label="Contact email"
            name="contact_email"
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
          />
          <Button type="submit" disabled={!businessName}>
            Create business
          </Button>
        </form>
      </Card>
    </div>
  );
}
