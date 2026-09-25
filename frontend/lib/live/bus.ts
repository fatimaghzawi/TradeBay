

export const LIVE_BUMP_EVENT = "tradebay:live-bump";

export type LiveBumpDetail = {
  source?: string;
  referenceType?: string | null;
  referenceId?: string | null;
};

export function bumpLive(detail: LiveBumpDetail = {}) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(LIVE_BUMP_EVENT, { detail }));
}

export function onLiveBump(handler: (detail: LiveBumpDetail) => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const listener = (event: Event) => {
    const custom = event as CustomEvent<LiveBumpDetail>;
    handler(custom.detail ?? {});
  };
  window.addEventListener(LIVE_BUMP_EVENT, listener);
  return () => window.removeEventListener(LIVE_BUMP_EVENT, listener);
}
