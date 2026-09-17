/** Stub — AI domain not implemented. */
function notImplemented(): never {
  throw new Error("aiApi: not implemented");
}

export const aiApi = {
  health: notImplemented,
};
