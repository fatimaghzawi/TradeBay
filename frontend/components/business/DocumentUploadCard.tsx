"use client";

import { cn } from "@/lib/utils";
import { validateUpload } from "@/lib/validation/common";
import { useState } from "react";

export function DocumentUploadCard({
  title,
  hint = "PDF, JPG, or PNG · Max 10 MB",
  fileName,
  error,
  onSelect,
}: {
  title: string;
  hint?: string;
  fileName?: string | null;
  error?: string | null;
  onSelect: (file: File | null) => void;
}) {
  const [localError, setLocalError] = useState<string | null>(null);
  const shown = error || localError;

  return (
    <label className="tb-drop cursor-pointer" data-state={shown ? "error" : undefined}>
      <span className="mb-1 text-[#8a9690]" aria-hidden>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <path
            d="M7 18a4.5 4.5 0 0 1-.4-9 5.5 5.5 0 0 1 10.7-1.4A4 4 0 0 1 17 18H7Z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path
            d="M12 15V9M12 9l-2.2 2.2M12 9l2.2 2.2"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="text-sm font-semibold text-[var(--tb-field-fg)]">{title}</span>
      <span className="text-xs">{hint}</span>
      {fileName ? (
        <span className="tb-hint" data-tone="ok">
          Selected: {fileName}
        </span>
      ) : (
        <span className="text-xs">Drag & drop files here or click to browse</span>
      )}
      {shown ? (
        <span className="tb-hint" data-tone="error">
          {shown}
        </span>
      ) : null}
      <span
        className={cn(
          "mt-1 inline-flex h-8 items-center rounded-[0.5rem] px-3 text-xs font-semibold",
          fileName ? "bg-[#e8f6ef] text-[#157347]" : "bg-[#f2f4f3] text-[#344054]",
        )}
      >
        {fileName ? "Replace file" : "Upload file"}
      </span>
      <input
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png,image/webp"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0] ?? null;
          const message = validateUpload(file, { kinds: "document", label: title });
          setLocalError(message);
          onSelect(message ? null : file);
          e.target.value = "";
        }}
      />
    </label>
  );
}
