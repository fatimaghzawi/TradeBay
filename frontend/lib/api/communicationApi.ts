/** Stub — communication domain not implemented. */
function notImplemented(): never {
  throw new Error("communicationApi: not implemented");
}

export const communicationApi = {
  listConversations: notImplemented,
  getConversation: notImplemented,
  listMessages: notImplemented,
};
