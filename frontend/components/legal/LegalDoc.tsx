import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { BackLink } from "@/components/ui/BackLink";
import { ROUTES } from "@/lib/constants";

const AUTH_LOGO = "/images/TradeBay-logo-light.png";

type LegalDocProps = {
  title: string;
  effectiveDate: string;
  children: ReactNode;
};

export function LegalDoc({ title, effectiveDate, children }: LegalDocProps) {
  return (
    <div className="min-h-svh bg-muted text-foreground">
      <header className="border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link href={ROUTES.home} aria-label="TradeBay home">
            <Image
              src={AUTH_LOGO}
              alt="TradeBay"
              width={160}
              height={42}
              className="h-9 w-auto object-contain object-left"
            />
          </Link>
          <BackLink href={ROUTES.register}>Back to register</BackLink>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-subtle-foreground">
          Legal
        </p>
        <h1 className="mt-2 font-[family-name:var(--font-syne)] text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Effective date: <span className="font-medium text-foreground">{effectiveDate}</span>
          {" · "}
          TradeBay Platform — Lebanon B2B marketplace
        </p>

        <div className="prose-legal mt-10 space-y-8 text-[0.95rem] leading-relaxed text-ink-soft">
          {children}
        </div>

        <p className="mt-12 border-t border-border pt-6 text-xs text-subtle-foreground">
          © {new Date().getFullYear()} TradeBay. These documents are provided for platform use.
          For questions, contact{" "}
          <a
            href="mailto:legal@tradebay.app"
            className="font-semibold text-heading underline-offset-2 hover:underline"
          >
            legal@tradebay.app
          </a>
          .
        </p>
      </main>
    </div>
  );
}

export function LegalSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="font-[family-name:var(--font-syne)] text-lg font-bold text-heading">
        {title}
      </h2>
      <div className="mt-2 space-y-3">{children}</div>
    </section>
  );
}
