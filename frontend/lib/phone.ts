/** Lebanese mobile / landline entry: fixed +961 + 8 national digits. */

export const LEBANON_PHONE_PREFIX = "+961";
export const LEBANON_PHONE_LOCAL_LENGTH = 8;

/** Digits only from a stored or typed phone (strips +961 / leading 0). */
export function lebanonLocalDigits(value: string | null | undefined): string {
  const digits = (value ?? "").replace(/\D/g, "");
  if (digits.startsWith("961")) {
    return digits.slice(3, 3 + LEBANON_PHONE_LOCAL_LENGTH);
  }
  if (digits.startsWith("0")) {
    return digits.slice(1, 1 + LEBANON_PHONE_LOCAL_LENGTH);
  }
  return digits.slice(0, LEBANON_PHONE_LOCAL_LENGTH);
}

/** Full E.164-style value stored in the API, or empty if incomplete. */
export function formatLebanonPhone(localDigits: string): string {
  const local = localDigits.replace(/\D/g, "").slice(0, LEBANON_PHONE_LOCAL_LENGTH);
  if (!local) return "";
  return `${LEBANON_PHONE_PREFIX}${local}`;
}

export function isValidLebanonPhone(value: string | null | undefined): boolean {
  const local = lebanonLocalDigits(value);
  return local.length === LEBANON_PHONE_LOCAL_LENGTH;
}
