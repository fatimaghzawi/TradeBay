"use client";

import { issuesToFieldMap } from "@/lib/validation/common";
import { useMemo, useState } from "react";
import type { z } from "zod";

export function useLiveFields<T extends Record<string, unknown>>(
  schema: z.ZodType,
  values: T,
) {
  const [touched, setTouched] = useState<Partial<Record<keyof T, boolean>>>({});
  const [submitted, setSubmitted] = useState(false);

  const all = useMemo(() => {
    const parsed = schema.safeParse(values);
    if (parsed.success) return {} as Partial<Record<keyof T, string>>;
    return issuesToFieldMap(parsed.error.issues) as Partial<Record<keyof T, string>>;
  }, [schema, values]);

  const errors = useMemo(() => {
    const next: Partial<Record<keyof T, string>> = {};
    for (const key of Object.keys(all) as (keyof T)[]) {
      if (submitted || touched[key]) next[key] = all[key];
    }
    return next;
  }, [all, submitted, touched]);

  function touch(key: keyof T) {
    setTouched((prev) => (prev[key] ? prev : { ...prev, [key]: true }));
  }

  function finish(): boolean {
    setSubmitted(true);
    setTouched((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(values) as (keyof T)[]) next[key] = true;
      return next;
    });
    return Object.keys(all).length === 0;
  }

  function reset() {
    setTouched({});
    setSubmitted(false);
  }

  return {
    errors,
    all,
    valid: Object.keys(all).length === 0,
    touch,
    finish,
    reset,
    submitted,
  };
}

export function fieldHandlers<T extends Record<string, unknown>>(
  live: ReturnType<typeof useLiveFields<T>>,
  key: keyof T,
) {
  return {
    onBlur: () => live.touch(key),
    error: live.errors[key],
  };
}
