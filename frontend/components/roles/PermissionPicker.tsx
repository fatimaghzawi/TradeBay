"use client";

import { ModulePermissionPicker } from "@/components/roles/ModulePermissionPicker";
import type { Permission } from "@/lib/api/identityApi";

type PermissionPickerProps = {
  catalog: Permission[];
  selected: string[];
  onChange: (codes: string[]) => void;
  /** Permission codes the actor may grant. Others render disabled. */
  grantable: Set<string> | string[];
  readOnly?: boolean;
};

/** Compact module-rail permission picker (keeps invite / legacy call sites short). */
export function PermissionPicker(props: PermissionPickerProps) {
  return <ModulePermissionPicker {...props} compact />;
}
