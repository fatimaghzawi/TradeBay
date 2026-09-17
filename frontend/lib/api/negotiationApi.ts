/** Stub — negotiation domain not implemented. */
function notImplemented(): never {
  throw new Error("negotiationApi: not implemented");
}

export const negotiationApi = {
  list: notImplemented,
  get: notImplemented,
  listOffers: notImplemented,
};
