"use client";

import { useEffect, useMemo, useState } from "react";

export type StoryChapter = {
  id: string;
  label: string;
};

type Props = {
  chapters: StoryChapter[];
};

/** Visual connector between landing chapters — the “road” linking sections. */
export function StoryBridge({ from, to }: { from: string; to: string }) {
  return (
    <div className="tb-lp-bridge" aria-hidden>
      <div className="tb-lp-bridge__route">
        <span className="tb-lp-bridge__from">{from}</span>
        <div className="tb-lp-bridge__line">
          <i />
          <b />
          <i />
        </div>
        <span className="tb-lp-bridge__to">{to}</span>
      </div>
    </div>
  );
}

/**
 * Continuous story chrome: top progress, left trade-route spine,
 * and scroll-triggered reveals for chapters + bridges.
 */
export function LandingStoryChrome({ chapters }: Props) {
  const [progress, setProgress] = useState(0);
  const [activeIndex, setActiveIndex] = useState(0);

  const ids = useMemo(() => chapters.map((c) => c.id), [chapters]);

  useEffect(() => {
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const onScroll = () => {
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      const p = max > 0 ? Math.min(1, window.scrollY / max) : 0;
      setProgress(p);

      let active = 0;
      for (let i = 0; i < ids.length; i++) {
        const el = document.getElementById(ids[i]!);
        if (!el) continue;
        const top = el.getBoundingClientRect().top;
        if (top <= window.innerHeight * 0.35) active = i;
      }
      setActiveIndex(active);
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });

    const nodes = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => Boolean(el));

    nodes.forEach((el) => el.classList.add("tb-lp-chapter"));

    const bridges = Array.from(
      document.querySelectorAll<HTMLElement>(".tb-lp-bridge"),
    );

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          entry.target.classList.toggle("is-inview", entry.isIntersecting);
          if (entry.isIntersecting && !reduceMotion) {
            entry.target.classList.add("has-played");
          }
        });
      },
      { threshold: [0.12, 0.28, 0.45], rootMargin: "-8% 0px -12% 0px" },
    );

    nodes.forEach((el) => io.observe(el));
    bridges.forEach((el) => io.observe(el));

    document
      .getElementById(ids[0] ?? "")
      ?.classList.add("has-played", "is-inview");

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      io.disconnect();
    };
  }, [ids]);

  return (
    <>
      <div className="tb-lp-progress" aria-hidden>
        <span style={{ transform: `scaleX(${progress})` }} />
      </div>

      <aside className="tb-lp-spine" aria-hidden>
        <div className="tb-lp-spine__track">
          <div
            className="tb-lp-spine__fill"
            style={{ transform: `scaleY(${progress})` }}
          />
          <div
            className="tb-lp-spine__traveler"
            style={{ top: `${progress * 100}%` }}
          />
        </div>
        <ol className="tb-lp-spine__nodes">
          {chapters.map((chapter, i) => (
            <li
              key={chapter.id}
              className={
                i < activeIndex
                  ? "is-passed"
                  : i === activeIndex
                    ? "is-active"
                    : undefined
              }
              title={chapter.label}
            >
              <span />
            </li>
          ))}
        </ol>
      </aside>
    </>
  );
}
