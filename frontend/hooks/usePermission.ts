"use client";
import { useAuth } from "@/providers/AuthProvider";
/** UX-only. Backend authorization remains authoritative. */
export function usePermission(code: string) {
  return useAuth().hasPermission(code);
}
