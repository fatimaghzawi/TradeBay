/** Stub — platform-money domain not implemented. */
function notImplemented(): never {
  throw new Error("platformMoneyApi: not implemented");
}

export const platformMoneyApi = {
  health: notImplemented,
};
