"use client";

import { identityApi, type Permission, type Role } from "@/lib/api/identityApi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useEffect, useState } from "react";

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = () => {
    void identityApi.listRoles().then((rows) => setRoles(Array.isArray(rows) ? rows : []));
    void identityApi.listPermissions().then((rows) => setCatalog(Array.isArray(rows) ? rows : []));
  };

  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold text-primary">Roles</h1>
      <p className="text-sm text-muted-foreground">
        Authorization uses resource.action permission codes resolved from the role. System roles cannot be deleted.
        You can only assign permissions you already hold.
      </p>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Card className="space-y-3 p-4">
        <h2 className="font-medium">Create custom role</h2>
        <Input label="Name" name="role_name" value={name} onChange={(e) => setName(e.target.value)} />
        <div className="grid max-h-64 grid-cols-1 gap-1 overflow-auto text-sm md:grid-cols-2">
          {catalog.map((permission) => (
            <label key={permission.code} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selected.includes(permission.code)}
                onChange={(e) => {
                  setSelected((current) =>
                    e.target.checked
                      ? [...current, permission.code]
                      : current.filter((code) => code !== permission.code),
                  );
                }}
              />
              <span>{permission.code}</span>
            </label>
          ))}
        </div>
        <Button
          type="button"
          disabled={!name || selected.length === 0}
          onClick={() => {
            setError(null);
            void identityApi
              .createRole(name, selected)
              .then(() => {
                setName("");
                setSelected([]);
                reload();
              })
              .catch(() => setError("Role was not created. You can only grant permissions you already have."));
          }}
        >
          Create role
        </Button>
      </Card>
      <Card>
        <ul className="divide-y divide-border text-sm">
          {roles.map((role) => (
            <li key={role.id} className="flex items-start justify-between gap-4 py-3">
              <div>
                <p className="font-medium">
                  {role.name} {role.is_system_role ? "(system)" : ""}
                </p>
                <p className="text-muted-foreground">{role.permissions.join(", ") || "No permissions"}</p>
              </div>
              {role.is_system_role ? null : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    void identityApi
                      .deleteRole(role.id)
                      .then(() => reload())
                      .catch(() => setError("System roles and roles in use cannot be deleted."));
                  }}
                >
                  Delete
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
