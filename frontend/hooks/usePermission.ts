"use client";
import { useAuth } from "@/providers/AuthProvider";

export function usePermission(code: string) {
  return useAuth().hasPermission(code);
}
