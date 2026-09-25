"use client";

import { Logo } from "@/components/layout/Logo";
import { StatusBadge } from "@/components/team/StatusBadge";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import {
  identityApi,
  type InvitationPreview,
} from "@/lib/api/identityApi";
import { AUTH_QUERY_KEY, BUSINESSES_QUERY_KEY } from "@/lib/auth/session";
import { BackLink } from "@/components/ui/BackLink";
import { ROUTES } from "@/lib/constants";
import { roleBlurb } from "@/lib/team";
import { useAuth } from "@/providers/AuthProvider";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

function AcceptInvitationContent() {
  const params = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated, isLoading, user } = useAuth();
  const { success, error: toastError, warning } = useToast();
  const token = params.get("token") ?? "";
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<"accepted" | "declined" | null>(null);
  const [pending, setPending] = useState(false);
  const [declineOpen, setDeclineOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("This invitation link is missing a token.");
      return;
    }
    void identityApi
      .previewInvitation(token)
      .then(setPreview)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Invitation could not be loaded.",
        ),
      );
  }, [token]);

  const emailMismatch =
    Boolean(user?.email && preview?.invited_email) &&
    user!.email.toLowerCase() !== preview!.invited_email.toLowerCase();

  const businessName = preview?.business_name ?? "a TradeBay business";

  async function switchAccount() {
    setSwitching(true);
    try {
      await authApi.logout();
      queryClient.setQueryData(AUTH_QUERY_KEY, null);
      await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      warning("Signed out", "Sign in with the company login on this invitation.");
      const email = preview?.invited_email
        ? `&email=${encodeURIComponent(preview.invited_email)}`
        : "";
      router.replace(
        `${ROUTES.login}?next=${encodeURIComponent(`/accept-invitation?token=${token}`)}${email}`,
      );
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not switch accounts.";
      toastError("Switch failed", message);
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div className="flex min-h-svh flex-col lg:grid lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <section className="relative flex flex-1 flex-col bg-muted px-6 py-8 sm:px-10 lg:px-14 lg:py-10">
        <Logo href="/" compact />

        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <p className="text-[0.7rem] font-bold uppercase tracking-[0.28em] text-accent-text">
            Invitation
          </p>
          <h1 className="mt-3 font-[family-name:var(--font-outfit)] text-[2rem] leading-tight tracking-tight text-heading sm:text-[2.35rem]">
            You&apos;ve been invited!
          </h1>
          <p className="mt-3 text-[1.02rem] leading-relaxed text-muted-foreground">
            Join{" "}
            <span className="font-semibold text-heading">{businessName}</span>{" "}
            on TradeBay.
          </p>

          {done === "accepted" ? (
            <div className="mt-8 space-y-4">
              <FeedbackBanner tone="success" title="Invitation accepted">
                <p>
                  Your membership is active and your company login is verified — no email code
                  needed. Open the dashboard when you&apos;re ready.
                </p>
              </FeedbackBanner>
              <Link
                href={ROUTES.dashboard}
                className="inline-flex h-12 w-full items-center justify-center rounded-xl bg-primary text-sm font-semibold text-primary-foreground"
              >
                Go to dashboard →
              </Link>
            </div>
          ) : null}

          {done === "declined" ? (
            <div className="mt-8 space-y-4">
              <FeedbackBanner tone="info" title="Invitation declined">
                <p>No membership was created. You can close this page.</p>
              </FeedbackBanner>
              <BackLink href={ROUTES.home}>Back to TradeBay</BackLink>
            </div>
          ) : null}

          {!done && preview ? (
            <div className="mt-8 overflow-hidden rounded-2xl border border-border bg-card shadow-[0_12px_40px_rgba(13,59,42,0.06)]">
              <div className="flex items-center justify-between border-b border-border bg-muted px-5 py-3">
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Dossier
                </span>
                <StatusBadge status={preview.status} />
              </div>
              <div className="space-y-5 px-5 py-5">
                <div>
                  <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-subtle-foreground">
                    Role
                  </p>
                  <p className="mt-1 text-lg font-semibold text-heading">
                    {preview.role_name ?? "—"}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {roleBlurb(preview.role_name)}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4 border-t border-border pt-4">
                  <div>
                    <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-subtle-foreground">
                      Company login
                    </p>
                    <p className="mt-1 font-semibold text-foreground">
                      {preview.invited_email}
                    </p>
                  </div>
                  <div>
                    <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-subtle-foreground">
                      Invited by
                    </p>
                    <p className="mt-1 font-semibold text-foreground">
                      {preview.inviter_name ?? "A teammate"}
                    </p>
                  </div>
                </div>
                <p className="text-xs text-subtle-foreground">
                  Invitation delivered to{" "}
                  {preview.delivery_email ?? preview.invited_email}. Sign in with{" "}
                  <strong>{preview.invited_email}</strong> to accept.
                </p>
              </div>
            </div>
          ) : null}

          {error ? (
            <div className="mt-6">
              <FeedbackBanner
                tone="error"
                title="Invitation problem"
                onDismiss={() => setError(null)}
              >
                {error}
              </FeedbackBanner>
            </div>
          ) : null}

          {preview && preview.status !== "pending" && !done ? (
            <div className="mt-6">
              <FeedbackBanner tone="warning" title={`This invite is ${preview.status}`}>
                Ask an admin to send a fresh invite if you still need access.
              </FeedbackBanner>
            </div>
          ) : null}

          {isLoading ? (
            <p className="mt-6 text-sm text-muted-foreground">Checking your session…</p>
          ) : null}

          {!isLoading && !isAuthenticated && !done ? (
            <div className="mt-8 space-y-3">
              <p className="text-sm text-muted-foreground">
                Register or sign in with the{" "}
                <strong>company login</strong>
                {preview?.invited_email ? (
                  <>
                    {" "}
                    <strong>{preview.invited_email}</strong>
                  </>
                ) : null}
                — not the personal inbox this invite was emailed to. No verification code.
              </p>
              <Link
                href={`${ROUTES.login}?next=${encodeURIComponent(`/accept-invitation?token=${token}`)}${
                  preview?.invited_email
                    ? `&email=${encodeURIComponent(preview.invited_email)}`
                    : ""
                }`}
                className="inline-flex h-12 w-full items-center justify-center rounded-xl bg-primary text-sm font-semibold text-primary-foreground"
              >
                Sign in to continue →
              </Link>
              <Link
                href={`${ROUTES.register}?invite=${encodeURIComponent(token)}&next=${encodeURIComponent(`/accept-invitation?token=${token}`)}`}
                className="inline-flex h-12 w-full items-center justify-center rounded-xl border border-border bg-card text-sm font-semibold text-heading hover:bg-muted"
              >
                Create account
              </Link>
            </div>
          ) : null}

          {!isLoading && isAuthenticated && !done && preview?.status === "pending" ? (
            <div className="mt-8 space-y-3">
              {emailMismatch ? (
                <>
                  <FeedbackBanner tone="warning" title="Wrong account">
                    You&apos;re signed in as {user?.email}. This invite requires the
                    company login <strong>{preview.invited_email}</strong>
                    {preview.delivery_email &&
                    preview.delivery_email !== preview.invited_email
                      ? ` (invitation was delivered to ${preview.delivery_email})`
                      : ""}
                    .
                  </FeedbackBanner>
                  <button
                    type="button"
                    disabled={switching}
                    className="flex h-12 w-full items-center justify-center rounded-xl bg-primary text-sm font-semibold text-primary-foreground disabled:opacity-60"
                    onClick={() => void switchAccount()}
                  >
                    {switching ? "Signing out…" : "Switch account →"}
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    disabled={pending || !token}
                    className="flex h-12 w-full items-center justify-center rounded-xl bg-primary text-sm font-semibold text-primary-foreground disabled:opacity-60"
                    onClick={() => {
                      setPending(true);
                      setError(null);
                      void identityApi
                        .acceptInvitation(token)
                        .then(async (result) => {
                          setDone("accepted");
                          success(
                            result?.already_accepted
                              ? "Already a member"
                              : "Welcome aboard",
                            result?.role_name
                              ? `You're in as ${result.role_name}.`
                              : "Your membership is now active.",
                          );
                          const me = await authApi.me();
                          queryClient.setQueryData(AUTH_QUERY_KEY, me);
                          await queryClient.invalidateQueries({
                            queryKey: BUSINESSES_QUERY_KEY,
                          });
                          router.refresh();
                        })
                        .catch((err) => {
                          const message =
                            err instanceof ApiError
                              ? err.message
                              : "Invitation could not be accepted.";
                          setError(message);
                          toastError("Accept failed", message);
                        })
                        .finally(() => setPending(false));
                    }}
                  >
                    <BusyText busy={pending}>{pending ? "Working…" : "Accept and continue →"}</BusyText>
                  </button>
                  <button
                    type="button"
                    disabled={pending || !token}
                    className="flex h-12 w-full items-center justify-center rounded-xl border border-border text-sm font-semibold text-muted-foreground hover:bg-card disabled:opacity-60"
                    onClick={() => setDeclineOpen(true)}
                  >
                    Decline
                  </button>
                </>
              )}
            </div>
          ) : null}
        </div>
      </section>

      <aside className="relative hidden min-h-[40vh] overflow-hidden bg-[#04140f] lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(90%_80%_at_70%_40%,#1a6b4f_0%,#0d3b2a_55%,#071a13_100%)]" />
        <div className="absolute inset-0 opacity-35 mix-blend-soft-light bg-[linear-gradient(115deg,transparent_40%,#e86f2a_100%)]" />
        <div
          aria-hidden
          className="absolute inset-0 opacity-25"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
        <div className="relative z-10 flex h-full flex-col justify-end px-12 pb-16 pt-12">
          <p className="font-[family-name:var(--font-outfit)] text-4xl font-extrabold leading-[1.05] tracking-tight text-white xl:text-5xl">
            Local businesses.
            <br />
            <span className="text-accent-text">Greater opportunities.</span>
          </p>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/65">
            Join your team on Lebanon&apos;s B2B marketplace — source, connect,
            and grow together.
          </p>
        </div>
      </aside>

      <ConfirmModal
        open={declineOpen}
        onClose={() => setDeclineOpen(false)}
        title="Decline this invitation?"
        asideTitle="You can be re-invited"
        asideBody="Declining closes this invite link. An admin can send a new one later if needed."
        confirmLabel="Decline invitation"
        pendingLabel="Declining…"
        onConfirm={async () => {
          setPending(true);
          setError(null);
          try {
            await identityApi.declineInvitation(token);
            setDone("declined");
            setDeclineOpen(false);
            success("Invitation declined", "No membership was created.");
          } catch (err) {
            const message =
              err instanceof ApiError
                ? err.message
                : "Invitation could not be declined.";
            setError(message);
            toastError("Decline failed", message);
            throw err;
          } finally {
            setPending(false);
          }
        }}
      >
        <p className="text-sm text-muted-foreground">
          Decline joining <strong>{businessName}</strong> as{" "}
          <strong>{preview?.role_name ?? "a teammate"}</strong>?
        </p>
      </ConfirmModal>
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-svh items-center justify-center bg-muted text-sm text-muted-foreground">
          Loading invitation…
        </div>
      }
    >
      <AcceptInvitationContent />
    </Suspense>
  );
}
