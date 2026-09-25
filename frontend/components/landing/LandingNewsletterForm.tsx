"use client";

import { LP } from "@/lib/landingLinks";
import { ROUTES } from "@/lib/constants";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function LandingNewsletterForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");

  return (
    <form
      className="tb-lp-footer__news"
      onSubmit={(e) => {
        e.preventDefault();
        const trimmed = email.trim();
        const params = new URLSearchParams();
        if (trimmed) params.set("email", trimmed);
        params.set("next", ROUTES.marketplace);
        const qs = params.toString();
        router.push(qs ? `${LP.register}?${qs}` : LP.register);
      }}
    >
      <h4>Subscribe to our newsletter</h4>
      <label className="tb-lp-footer__field">
        <span className="sr-only">Email</span>
        <input
          type="email"
          name="email"
          placeholder="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <button type="submit" aria-label="Subscribe">
          →
        </button>
      </label>
      <p className="tb-lp-footer__news-hint">
        We&apos;ll open your TradeBay account signup with this email.
      </p>
    </form>
  );
}
