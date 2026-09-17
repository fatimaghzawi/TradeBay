"use client";

import { identityApi, type Member, type Role } from "@/lib/api/identityApi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useEffect, useState } from "react";

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = () => {
    void identityApi.listMembers().then((rows) => setMembers(Array.isArray(rows) ? rows : []));
    void identityApi.listRoles().then((rows) => setRoles(Array.isArray(rows) ? rows : []));
  };

  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold text-primary">Members</h1>
      <p className="text-sm text-muted-foreground">
        Roles come from the active business membership. Authorization uses resource.action codes on the server.
      </p>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Card>
        <ul className="divide-y divide-border">
          {members.map((member) => (
            <li key={member.id} className="flex flex-col gap-2 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
              <span>
                {member.email ?? member.user_id}{" "}
                <span className="text-muted-foreground">({member.status})</span>
              </span>
              <div className="flex items-center gap-2">
                <select
                  className="rounded-md border border-border bg-surface px-2 py-1"
                  value={member.role_id}
                  onChange={(e) => {
                    setError(null);
                    void identityApi
                      .updateMemberRole(member.id, e.target.value)
                      .then(() => reload())
                      .catch(() => setError("Role change rejected. Last admin cannot be demoted, and grants must be a subset of yours."));
                  }}
                >
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    void identityApi
                      .removeMember(member.id)
                      .then(() => reload())
                      .catch(() => setError("Member could not be removed. The last Business Admin is protected."));
                  }}
                >
                  Remove
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
