/** Stub — trust domain not implemented. */
function notImplemented(): never {
  throw new Error("trustApi: not implemented");
}

export const trustApi = {
  health: notImplemented,
};
