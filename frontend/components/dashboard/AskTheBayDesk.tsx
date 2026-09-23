"use client";

import { ROUTES } from "@/lib/constants";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

const EXAMPLES = [
  {
    label: "I want food products",
    prompt:
      "I want food products for my business in Lebanon. Looking for grocery and pantry suppliers who can deliver in bulk.",
  },
  {
    label: "I want construction products",
    prompt:
      "I want construction products and building materials in bulk. Prefer verified suppliers who deliver across Lebanon.",
  },
  {
    label: "I want cleaning supplies",
    prompt:
      "I want cleaning supplies and household cleaning products for monthly restocking from verified suppliers.",
  },
  {
    label: "I want beverages",
    prompt:
      "I want beverages and soft drinks for a supermarket. Looking for bulk suppliers who can deliver regularly.",
  },
  {
    label: "I want kitchen housewares",
    prompt:
      "I want kitchen housewares and food-service equipment for a restaurant kitchen in Beirut.",
  },
] as const;

type Props = {
  businessName?: string | null;
};

export function AskTheBayDesk({ businessName }: Props) {
  const router = useRouter();
  const inputId = useId();
  const [prompt, setPrompt] = useState("");
  const [sending, setSending] = useState(false);

  function go(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSending(true);
    router.push(`${ROUTES.aiSourcing}?prompt=${encodeURIComponent(trimmed)}`);
  }

  return (
    <section
      className="tb-desk-ask"
      aria-labelledby={`${inputId}-title`}
      data-busy={sending || undefined}
    >
      <div className="tb-desk-ask__orb" aria-hidden />
      <div className="tb-desk-ask__star" aria-hidden>
        <svg viewBox="0 0 64 64" width="72" height="72">
          <path
            d="M32 4 L36.5 24.5 L56 32 L36.5 39.5 L32 60 L27.5 39.5 L8 32 L27.5 24.5 Z"
            fill="currentColor"
          />
        </svg>
      </div>

      <p className="tb-desk-ask__pill">AI Assistant</p>
      <h2 id={`${inputId}-title`} className="tb-desk-ask__title">
        Ask the Bay
      </h2>
      <p className="tb-desk-ask__lede">
        {businessName
          ? `Ask the Bay about products and suppliers for ${businessName}.`
          : "Ask the Bay about products and suppliers."}
      </p>

      <form
        className="tb-desk-ask__compose"
        onSubmit={(e) => {
          e.preventDefault();
          go(prompt);
        }}
      >
        <label htmlFor={inputId} className="sr-only">
          Ask TradeBay
        </label>
        <input
          id={inputId}
          type="text"
          value={prompt}
          placeholder="Ask anything about products, suppliers, or sourcing…"
          onChange={(e) => setPrompt(e.target.value)}
        />
        <button
          type="submit"
          className="tb-desk-ask__go"
          disabled={sending || !prompt.trim()}
          aria-label="Ask TradeBay"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
            <path
              d="M5 12h12M13 6l6 6-6 6"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </form>

      <ul className="tb-desk-ask__suggestions" aria-label="Example prompts">
        {EXAMPLES.map((example) => (
          <li key={example.label}>
            <button
              type="button"
              disabled={sending}
              onClick={() => go(example.prompt)}
            >
              {example.label}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
