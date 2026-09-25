"use client";

import {
  LEBANON_PHONE_LOCAL_LENGTH,
  LEBANON_PHONE_PREFIX,
  formatLebanonPhone,
  lebanonLocalDigits,
} from "@/lib/phone";
import { cn } from "@/lib/utils";

type LebanesePhoneFieldProps = {
  label?: string;
  value: string;
  onChange: (fullPhone: string) => void;
  required?: boolean;
  disabled?: boolean;
  error?: string | null;
  id?: string;
  className?: string;
  onBlur?: () => void;
};

export function LebanesePhoneField({
  label = "Phone number",
  value,
  onChange,
  required,
  disabled,
  error,
  id = "lebanon-phone",
  className,
  onBlur,
}: LebanesePhoneFieldProps) {
  const local = lebanonLocalDigits(value);

  return (
    <label className={cn("block", className)}>
      <span className="tb-field-label mb-1.5 block text-sm font-semibold">
        {label}
        {required ? <span className="text-accent-text"> *</span> : null}
      </span>
      <div className="tb-phone" data-state={error ? "error" : undefined}>
        <span className="tb-phone-code" aria-hidden>
          🇱🇧 {LEBANON_PHONE_PREFIX}
        </span>
        <input
          id={id}
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          required={required}
          disabled={disabled}
          maxLength={LEBANON_PHONE_LOCAL_LENGTH}
          pattern={`\\d{${LEBANON_PHONE_LOCAL_LENGTH}}`}
          title={`Enter ${LEBANON_PHONE_LOCAL_LENGTH} digits after ${LEBANON_PHONE_PREFIX}`}
          placeholder="71123456"
          value={local}
          onBlur={onBlur}
          onChange={(e) => {
            const next = e.target.value.replace(/\D/g, "").slice(0, LEBANON_PHONE_LOCAL_LENGTH);
            onChange(formatLebanonPhone(next));
          }}
          aria-label={`${label}, Lebanon country code ${LEBANON_PHONE_PREFIX}`}
        />
      </div>
      <p className="tb-hint">
        Lebanon · {LEBANON_PHONE_PREFIX} + {LEBANON_PHONE_LOCAL_LENGTH} digits
      </p>
      {error ? (
        <p className="tb-hint" data-tone="error">
          {error}
        </p>
      ) : null}
    </label>
  );
}
