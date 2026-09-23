"use client";

import {
  blockNonNumericKeys,
  sanitizeNumericInput,
  type NumericKind,
} from "@/lib/numericInput";
import { cn } from "@/lib/utils";
import type { ChangeEvent, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function FieldError({ error }: { error?: string | null }) {
  if (!error) return null;
  return (
    <p className="tb-hint" data-tone="error">
      {error}
    </p>
  );
}

type FormFieldProps = {
  label?: string;
  htmlFor?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
  boxed?: boolean;
};

export function FormField({
  label,
  htmlFor,
  error,
  hint,
  required,
  children,
  className,
  boxed = true,
}: FormFieldProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label ? (
        <label htmlFor={htmlFor} className="tb-field-label">
          {label}
          {required ? <span className="tb-req">*</span> : null}
        </label>
      ) : null}
      {boxed ? (
        <div className="tb-form-shell" data-state={error ? "error" : undefined}>
          {children}
        </div>
      ) : (
        children
      )}
      {error ? (
        <FieldError error={error} />
      ) : hint ? (
        <p className="tb-form-hint">{hint}</p>
      ) : null}
    </div>
  );
}

type NativeInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "size"> & {
  label?: string;
  error?: string;
  hint?: string;
  inputClassName?: string;
};

export function TextField({
  label,
  error,
  hint,
  id,
  name,
  required,
  className,
  inputClassName,
  ...props
}: NativeInputProps) {
  const inputId = id ?? name;
  return (
    <FormField
      label={label}
      htmlFor={inputId}
      error={error}
      hint={hint}
      required={required}
      className={className}
    >
      <input id={inputId} name={name} required={required} className={inputClassName} {...props} />
    </FormField>
  );
}

type NumberInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "inputMode"> & {
  kind?: NumericKind;
  maxDecimals?: number;
};

/** Text input that only accepts digits (and one decimal for prices). */
export function NumberInput({
  kind = "decimal",
  maxDecimals = 2,
  onChange,
  onKeyDown,
  onPaste,
  className,
  ...props
}: NumberInputProps) {
  return (
    <input
      {...props}
      type="text"
      inputMode={kind === "integer" ? "numeric" : "decimal"}
      autoComplete="off"
      spellCheck={false}
      className={className}
      onKeyDown={(event) => {
        blockNonNumericKeys(event, kind);
        onKeyDown?.(event);
      }}
      onPaste={(event) => {
        const pasted = event.clipboardData.getData("text");
        const cleaned = sanitizeNumericInput(pasted, kind, maxDecimals);
        if (cleaned !== pasted) {
          event.preventDefault();
          const target = event.currentTarget;
          const start = target.selectionStart ?? target.value.length;
          const end = target.selectionEnd ?? target.value.length;
          const next = sanitizeNumericInput(
            target.value.slice(0, start) + cleaned + target.value.slice(end),
            kind,
            maxDecimals,
          );
          target.value = next;
          onChange?.({
            ...event,
            target,
            currentTarget: target,
          } as unknown as ChangeEvent<HTMLInputElement>);
        }
        onPaste?.(event);
      }}
      onChange={(event) => {
        const cleaned = sanitizeNumericInput(event.target.value, kind, maxDecimals);
        if (cleaned !== event.target.value) event.target.value = cleaned;
        onChange?.(event);
      }}
    />
  );
}

export function TextAreaField({
  label,
  error,
  hint,
  id,
  name,
  required,
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  error?: string;
  hint?: string;
}) {
  const inputId = id ?? name;
  return (
    <FormField
      label={label}
      htmlFor={inputId}
      error={error}
      hint={hint}
      required={required}
      className={className}
    >
      <textarea id={inputId} name={name} required={required} {...props} />
    </FormField>
  );
}

export function SelectField({
  label,
  error,
  hint,
  id,
  name,
  required,
  className,
  options,
  placeholder,
  ...props
}: Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> & {
  label?: string;
  error?: string;
  hint?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
}) {
  const inputId = id ?? name;
  return (
    <FormField
      label={label}
      htmlFor={inputId}
      error={error}
      hint={hint}
      required={required}
      className={className}
    >
      <select id={inputId} name={name} required={required} {...props}>
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </FormField>
  );
}
