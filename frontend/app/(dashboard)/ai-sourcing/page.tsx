"use client";

import { AISourcingExperience } from "@/components/ai-sourcing/AISourcingExperience";
import { PermissionGate } from "@/components/auth/PermissionGate";

export default function AISourcingPage() {
  return (
    <PermissionGate
      permission="sourcing.create"
      fallbackTitle="AI Sourcing is unavailable"
      fallbackDescription="Ask a Business Admin to enable AI sourcing for your role."
    >
      <AISourcingExperience />
    </PermissionGate>
  );
}
