"use client";

import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { BusyText, LoadingEntity } from "@/components/ui/LoadingState";
import { buttonClass } from "@/components/ui/Button";
import { useEffect, useRef, useState } from "react";

type StripeAppearance = {
  theme: "stripe" | "night" | "flat";
  variables: Record<string, string>;
  rules?: Record<string, Record<string, string>>;
};

type StripePaymentElement = { mount: (el: HTMLElement) => void; destroy: () => void };

type StripeElements = {
  create: (type: "payment", options?: Record<string, unknown>) => StripePaymentElement;
  update: (options: { appearance: StripeAppearance }) => void;
};

type StripeInstance = {
  elements: (options: { clientSecret: string; appearance: StripeAppearance }) => StripeElements;
  confirmPayment: (options: {
    elements: StripeElements;
    confirmParams: { return_url: string };
    redirect: "if_required";
  }) => Promise<{ error?: { message?: string; type?: string } }>;
};

declare global {
  interface Window {
    Stripe?: (key: string) => StripeInstance;
  }
}

const STRIPE_JS = "https://js.stripe.com/v3/";
let stripeScript: Promise<void> | null = null;

function loadStripeJs(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.Stripe) return Promise.resolve();
  if (stripeScript) return stripeScript;
  stripeScript = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = STRIPE_JS;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      stripeScript = null;
      reject(new Error("Card form failed to load"));
    };
    document.head.appendChild(script);
  });
  return stripeScript;
}

function tokenColor(token: string, fallback: string): string {
  const probe = document.createElement("span");
  probe.style.color = `var(${token})`;
  probe.style.display = "none";
  document.body.appendChild(probe);
  const value = getComputedStyle(probe).color;
  probe.remove();
  return value || fallback;
}

function tokenValue(token: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  return v || fallback;
}

function tradebayAppearance(): StripeAppearance {
  const dark = document.documentElement.classList.contains("dark");
  const font = getComputedStyle(document.body).fontFamily;
  return {
    theme: dark ? "night" : "stripe",
    variables: {
      colorPrimary: tokenColor("--tb-primary", "#1f4d3a"),
      colorBackground: tokenColor("--tb-field-bg", dark ? "#1b2230" : "#ffffff"),
      colorText: tokenColor("--tb-ink", dark ? "#e6e9ef" : "#1a1f2b"),
      colorTextSecondary: tokenColor("--tb-muted-fg", "#6b7280"),
      colorTextPlaceholder: tokenColor("--tb-subtle-fg", "#9aa1ad"),
      colorDanger: tokenColor("--tb-danger", "#b42318"),
      fontFamily: font,
      borderRadius: tokenValue("--tb-radius-field", "10px"),
      spacingUnit: "4px",
    },
    rules: {
      ".Input": {
        border: `1px solid ${tokenColor("--tb-field-line", "#d6dae1")}`,
        boxShadow: "none",
      },
      ".Input:focus": {
        borderColor: tokenColor("--tb-primary", "#1f4d3a"),
        boxShadow: `0 0 0 3px ${tokenColor("--tb-secondary-soft", "rgba(31,77,58,0.15)")}`,
      },
      ".Tab": {
        border: `1px solid ${tokenColor("--tb-line", "#e3e6ea")}`,
        backgroundColor: tokenColor("--tb-surface-muted", "#f6f7f9"),
      },
      ".Tab--selected": {
        borderColor: tokenColor("--tb-primary", "#1f4d3a"),
        backgroundColor: tokenColor("--tb-surface", "#ffffff"),
      },
      ".Label": {
        color: tokenColor("--tb-ink-soft", "#3b4252"),
        fontWeight: "600",
      },
    },
  };
}

export function CardPaymentForm({
  clientSecret,
  publishableKey,
  amountLabel,
  returnUrl,
  onSubmitted,
}: {
  clientSecret: string;
  publishableKey: string;
  amountLabel: string;
  returnUrl: string;
  onSubmitted: () => Promise<void> | void;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const stripeRef = useRef<StripeInstance | null>(null);
  const elementsRef = useRef<StripeElements | null>(null);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let element: StripePaymentElement | null = null;
    let cancelled = false;
    setReady(false);
    setLoadError(null);
    void loadStripeJs()
      .then(() => {
        if (cancelled || !hostRef.current || !window.Stripe) return;
        const stripe = window.Stripe(publishableKey);
        const elements = stripe.elements({ clientSecret, appearance: tradebayAppearance() });
        element = elements.create("payment", { layout: "tabs" });
        element.mount(hostRef.current);
        stripeRef.current = stripe;
        elementsRef.current = elements;
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) setLoadError("The card form couldn't load. Check your connection and try again.");
      });
    return () => {
      cancelled = true;
      element?.destroy();
      elementsRef.current = null;
    };
  }, [clientSecret, publishableKey]);

  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      elementsRef.current?.update({ appearance: tradebayAppearance() });
    });
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  async function pay() {
    const stripe = stripeRef.current;
    const elements = elementsRef.current;
    if (!stripe || !elements) return;
    setBusy(true);
    setCardError(null);
    try {
      const { error } = await stripe.confirmPayment({
        elements,
        confirmParams: { return_url: returnUrl },
        redirect: "if_required",
      });
      if (error) {
        setCardError(error.message || "Your card couldn't be charged. Try another card.");
        return;
      }
      await onSubmitted();
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <FeedbackBanner tone="error" title="Card form unavailable">
        {loadError}
      </FeedbackBanner>
    );
  }

  return (
    <div className="grid gap-3">
      {!ready ? <LoadingEntity entity="secure card form" compact /> : null}
      <div ref={hostRef} className="tb-co-card-host" hidden={!ready} />
      {cardError ? (
        <FeedbackBanner tone="error" title="Payment not completed">
          {cardError}
        </FeedbackBanner>
      ) : null}
      <button
        type="button"
        className={buttonClass({ variant: "primary", className: "w-full" })}
        disabled={!ready || busy}
        aria-busy={busy || undefined}
        onClick={() => void pay()}
      >
        <BusyText busy={busy}>Pay {amountLabel}</BusyText>
      </button>
      <p className="tb-co-note">Card details go straight to our payment processor. TradeBay never sees or stores them.</p>
    </div>
  );
}
