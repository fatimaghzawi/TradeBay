import { Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { DASHBOARD_DOMAINS, ROUTES } from "@/lib/constants";
import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#1a6b4f22,_transparent_55%),var(--tb-surface-muted)]">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        <div className="flex items-center gap-3">
          <Link href={ROUTES.login}>
            <Button variant="ghost">Sign in</Button>
          </Link>
          <Link href={ROUTES.register}>
            <Button variant="accent">Get started</Button>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-16 pt-8">
        <section className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-secondary">
              TradeBay platform
            </p>
            <h1 className="font-display mt-4 text-4xl font-semibold leading-tight text-primary md:text-5xl">
              Run B2B trade across catalog, procurement, finance, and trust.
            </h1>
            <p className="mt-5 max-w-xl text-base text-muted-foreground">
              One workspace for buyers and suppliers — with platform money,
              dispute resolution, and AI-assisted workflows built in.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href={ROUTES.register}>
                <Button size="lg" variant="primary">
                  Create account
                </Button>
              </Link>
              <Link href={ROUTES.dashboard}>
                <Button size="lg" variant="outline">
                  Open dashboard
                </Button>
              </Link>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
            <p className="text-sm font-medium text-muted-foreground">
              Six connected domains
            </p>
            <ul className="mt-4 space-y-3">
              {DASHBOARD_DOMAINS.map((domain) => (
                <li
                  key={domain.key}
                  className="rounded-lg border border-border bg-surface-muted px-4 py-3"
                >
                  <p className="font-medium text-primary">{domain.title}</p>
                  <p className="text-sm text-muted-foreground">
                    {domain.description}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mt-16 rounded-2xl border border-border bg-surface p-8">
          <p className="text-sm font-semibold uppercase tracking-[0.15em] text-secondary">
            Business Planner
          </p>
          <h2 className="font-display mt-3 text-2xl font-semibold text-primary md:text-3xl">
            Planning to open a business?
          </h2>
          <p className="mt-3 max-w-2xl text-muted-foreground">
            Let TradeBay help you plan what you need — then find suppliers when
            you are ready.
          </p>
          <div className="mt-6">
            <Link href={ROUTES.businessPlanner}>
              <Button size="lg" variant="accent">
                Plan My Business
              </Button>
            </Link>
          </div>
        </section>

        <section className="mt-16 grid gap-4 md:grid-cols-3">
          {[
            {
              title: "Business context",
              body: "Switch between businesses without losing domain navigation.",
            },
            {
              title: "Authoritative backend",
              body: "Permissions and settlements are enforced server-side.",
            },
            {
              title: "Operational clarity",
              body: "Finance, trust, and procurement share one shell.",
            },
          ].map((item) => (
            <Card key={item.title}>
              <CardTitle>{item.title}</CardTitle>
              <CardDescription>{item.body}</CardDescription>
            </Card>
          ))}
        </section>
      </main>
    </div>
  );
}
