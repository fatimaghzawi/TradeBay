"use client";

import { cn } from "@/lib/utils";
import {
  type ClipboardEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
} from "react";

type OtpInputProps = {
  length?: number;
  value: string[];
  onChange: (next: string[]) => void;
  onComplete?: (code: string) => void;
  disabled?: boolean;
  error?: boolean;
  autoFocus?: boolean;
};

export function OtpInput({
  length = 6,
  value,
  onChange,
  onComplete,
  disabled = false,
  error = false,
  autoFocus = true,
}: OtpInputProps) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    if (autoFocus && !disabled) {
      refs.current[0]?.focus();
    }
  }, [autoFocus, disabled]);

  function setDigit(index: number, raw: string) {
    const char = raw.replace(/\D/g, "").slice(-1);
    const next = [...value];
    while (next.length < length) next.push("");
    next[index] = char;
    const trimmed = next.slice(0, length);
    onChange(trimmed);
    if (char && index < length - 1) {
      refs.current[index + 1]?.focus();
    }
    if (char && index === length - 1 && trimmed.every(Boolean)) {
      onComplete?.(trimmed.join(""));
    }
  }

  function onKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !value[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
    if (e.key === "ArrowLeft" && index > 0) {
      refs.current[index - 1]?.focus();
    }
    if (e.key === "ArrowRight" && index < length - 1) {
      refs.current[index + 1]?.focus();
    }
  }

  function onPaste(e: ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData("text").replace(/\s/g, "");
    if (!text) return;
    e.preventDefault();
    if (/^\d+$/.test(text)) {
      const next = Array.from({ length }, (_, i) => text[i] ?? "");
      onChange(next);
      const focusAt = Math.min(text.length, length - 1);
      refs.current[focusAt]?.focus();
      if (text.length >= length) {
        onComplete?.(text.slice(0, length));
      }
    }
  }

  return (
    <div className="tb-otp-row" role="group" aria-label="Verification code">
      {Array.from({ length }, (_, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          autoCorrect="off"
          autoCapitalize="none"
          spellCheck={false}
          pattern="[0-9]*"
          size={1}
          maxLength={1}
          value={value[i] ?? ""}
          disabled={disabled}
          onChange={(e) => setDigit(i, e.target.value)}
          onKeyDown={(e) => onKeyDown(i, e)}
          onPaste={onPaste}
          aria-label={`Digit ${i + 1}`}
          className={cn("tb-otp", error && "tb-field-error", disabled && "cursor-not-allowed opacity-50")}
        />
      ))}
    </div>
  );
}
