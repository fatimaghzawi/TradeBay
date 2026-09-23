import { LP } from "@/lib/landingLinks";

export const LANDING_NAV = [
  { label: "Products", href: LP.marketplace },
  { label: "Suppliers", href: LP.suppliers },
  { label: "For Suppliers", href: LP.section.suppliers },
  { label: "How it works", href: LP.section.paths },
] as const;

export const LANDING_PATHS = [
  {
    id: "buyers",
    kicker: "For Buyers",
    title: "Find. Compare. Source with Confidence.",
    body: "Access verified suppliers, compare offers, and get the best products for your business.",
    cta: "Start Buying",
    href: LP.marketplace,
    tone: "green" as const,
    icon: "buyers" as const,
  },
  {
    id: "suppliers",
    kicker: "For Suppliers",
    title: "Grow Your Business",
    body: "Showcase your products, reach new customers, and be part of a growing network.",
    cta: "Become a Supplier",
    href: LP.becomeSupplier,
    tone: "sand" as const,
    icon: "suppliers" as const,
  },
  {
    id: "planner",
    kicker: "AI Business Planner",
    title: "Turn Your Idea Into a Real Business",
    body: "Not sure where to start? Let our AI guide you with market insights, supplier recommendations, and cost estimates.",
    cta: "Try the AI Planner",
    href: LP.planner,
    tone: "mist" as const,
    icon: "planner" as const,
  },
] as const;

export const LANDING_PROOF_STATS = [
  { value: "Verified", label: "Suppliers you can trust" },
  { value: "Smart", label: "AI plans before you buy" },
  { value: "Direct", label: "RFQ straight to the deal" },
] as const;

export const LANDING_FOOTER = {
  marketplace: [
    { label: "Products", href: LP.marketplace },
    { label: "Suppliers", href: LP.suppliers },
    { label: "Start an RFQ", href: LP.procurement },
  ],
  businesses: [
    { label: "For Buyers", href: LP.marketplace },
    { label: "For Suppliers", href: LP.becomeSupplier },
    { label: "AI Planner", href: LP.planner },
    { label: "AI Sourcing", href: LP.aiSourcing },
  ],
  social: [
    { label: "Find suppliers", href: LP.suppliers, short: "in" },
    { label: "Browse products", href: LP.marketplace, short: "ig" },
    { label: "Try AI Planner", href: LP.planner, short: "yt" },
    { label: "Create account", href: LP.register, short: "fb" },
  ],
  resources: [
    { label: "How it works", href: LP.section.paths },
    { label: "Privacy Policy", href: LP.privacy },
    { label: "Terms of Service", href: LP.terms },
  ],
} as const;
