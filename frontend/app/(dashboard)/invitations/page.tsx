"use client";

import { identityApi, type Invitation, type Role } from "@/lib/api/identityApi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useEffect, useState } from "react";

export default function InvitationsPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = () => {
    void identityApi.listRoles().then((rows) => setRoles(Array.isArray(rows) ? rows : []));
    void identityApi.listInvitations().then((rows) => setInvites(Array.isArray(rows) ? rows : []));
  };

  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold text-primary">Invitations</h1>
      <p className="text-sm text-muted-foreground">
        Invitations carry a role, never individual permissions. The invitee cannot change the role or business.
      </p>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Card>
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            void identityApi
              .invite(email, roleId)
              .then(() => {
                setEmail("");
                reload();
              })
              .catch(() => setError("Invite failed. Check that you hold every permission on that role."));
          }}
        >
          <Input label="Email" name="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <label className="flex flex-1 flex-col gap-1 text-sm">
            Role
            <select
              className="rounded-md border border-border bg-surface px-3 py-2"
              value={roleId}
              onChange={(e) => setRoleId(e.target.value)}
            >
              <option value="">Select role</option>
              {roles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name}
                </option>
              ))}
            </select>
          </label>
          <Button type="submit" disabled={!email || !roleId}>
            Invite
          </Button>
        </form>
      </Card>
      <Card>
        <ul className="divide-y divide-border text-sm">
          {invites.map((invite) => (
            <li key={invite.id} className="flex items-center justify-between py-3">
              <span>
                {invite.invited_email}{" "}
                <span className="text-muted-foreground">({invite.status})</span>
              </span>
              {invite.status === "pending" ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    void identityApi.revokeInvitation(invite.id).then(() => reload());
                  }}
                >
                  Revoke
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
