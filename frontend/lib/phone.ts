

export const LEBANON_PHONE_PREFIX = "+961";
export const LEBANON_PHONE_LOCAL_LENGTH = 8;

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

export function formatLebanonPhone(localDigits: string): string {
  const local = localDigits.replace(/\D/g, "").slice(0, LEBANON_PHONE_LOCAL_LENGTH);
  if (!local) return "";
  return `${LEBANON_PHONE_PREFIX}${local}`;
}

export function isValidLebanonPhone(value: string | null | undefined): boolean {
  const local = lebanonLocalDigits(value);
  return local.length === LEBANON_PHONE_LOCAL_LENGTH;
}
