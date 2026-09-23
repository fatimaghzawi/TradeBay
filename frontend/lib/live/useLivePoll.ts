"use client";

import { LIVE_BUMP_EVENT, type LiveBumpDetail } from "@/lib/live/bus";
import { useCallback, useEffect, useRef } from "react";

type LivePollOptions = {
  /** Poll interval while the tab is visible. Default 5s. */
  intervalMs?: number;
  /** When false, polling pauses. Default true. */
  enabled?: boolean;
  /** Extra pause (e.g. while a form mutation is in flight). */
  paused?: boolean;
  /** Run immediately on mount / when enabled flips on. Default true. */
  immediate?: boolean;
};

/**
 * Visibility-aware poller for live screens.
 * Also refreshes on tab focus and on `tradebay:live-bump` events.
 */
export function useLivePoll(
  tick: () => void | Promise<void>,
  {
    intervalMs = 5000,
    enabled = true,
    paused = false,
    immediate = true,
  }: LivePollOptions = {},
) {
  const tickRef = useRef(tick);
  tickRef.current = tick;
  const inFlight = useRef(false);

  const run = useCallback(async () => {
    if (inFlight.current) return;
    if (typeof document !== "undefined" && document.visibilityState === "hidden") {
      return;
    }
    inFlight.current = true;
    try {
      await tickRef.current();
    } catch {
      /* callers handle their own errors; keep the loop alive */
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    if (!enabled || paused) return;

    if (immediate) void run();

    const id = window.setInterval(() => {
      void run();
    }, Math.max(1500, intervalMs));

    const onVisible = () => {
      if (document.visibilityState === "visible") void run();
    };
    const onBump = () => {
      void run();
    };

    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    window.addEventListener(LIVE_BUMP_EVENT, onBump);

    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
      window.removeEventListener(LIVE_BUMP_EVENT, onBump);
    };
  }, [enabled, paused, intervalMs, immediate, run]);
}

/** Subscribe to live bumps without polling. */
export function useLiveBump(handler: (detail: LiveBumpDetail) => void) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const listener = (event: Event) => {
      const custom = event as CustomEvent<LiveBumpDetail>;
      handlerRef.current(custom.detail ?? {});
    };
    window.addEventListener(LIVE_BUMP_EVENT, listener);
    return () => window.removeEventListener(LIVE_BUMP_EVENT, listener);
  }, []);
}
