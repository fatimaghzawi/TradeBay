"use client";

import { ModulePermissionPicker } from "@/components/roles/ModulePermissionPicker";
import type { Permission } from "@/lib/api/identityApi";

type PermissionPickerProps = {
  catalog: Permission[];
  selected: string[];
  onChange: (codes: string[]) => void;
  
  grantable: Set<string> | string[];
  readOnly?: boolean;
};

export function PermissionPicker(props: PermissionPickerProps) {
  return <ModulePermissionPicker {...props} compact />;
}
