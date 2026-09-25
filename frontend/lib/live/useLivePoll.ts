"use client";

import { LIVE_BUMP_EVENT, type LiveBumpDetail } from "@/lib/live/bus";
import { useCallback, useEffect, useRef } from "react";

type LivePollOptions = {
  
  intervalMs?: number;
  
  enabled?: boolean;
  
  paused?: boolean;
  
  immediate?: boolean;
};

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
