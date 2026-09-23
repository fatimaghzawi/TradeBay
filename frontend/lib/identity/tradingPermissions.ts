/** Platform-only codes — never assignable on buyer/supplier roles. */
export const PLATFORM_ONLY_PERMISSION_CODES = new Set([
  "suppliers.verify",
  "disputes.resolve",
  "settlements.approve",
  "settings.manage",
  "categories.manage",
]);

export function isTradingPermissionCode(code: string): boolean {
  return !PLATFORM_ONLY_PERMISSION_CODES.has(code);
}

export function tradingPermissionCodes(codes: Iterable<string>): string[] {
  return [...codes].filter(isTradingPermissionCode);
}
