"use client";

import { BusinessAsideCard } from "@/components/business/BusinessAsideCard";
import { BusinessStepper } from "@/components/business/BusinessStepper";
import { DocumentUploadCard } from "@/components/business/DocumentUploadCard";
import { ApiError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identityApi";
import { loadBusinessDraft, saveBusinessDraft } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";
import { BackLink } from "@/components/ui/BackLink";

type DocKey = "commercial" | "tax" | "address";

const DOC_TYPES: Record<DocKey, string> = {
  commercial: "commercial_registration",
  tax: "tax_certificate",
  address: "address_proof",
};

export default function VerifyBusinessPage() {
  const router = useRouter();
  const { business, refreshSession } = useAuth();
  const [files, setFiles] = useState<Record<DocKey, File | null>>({
    commercial: null,
    tax: null,
    address: null,
  });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [ready, setReady] = useState(false);
  const [businessId, setBusinessId] = useState<string | null>(null);

  useEffect(() => {
    const draft = loadBusinessDraft();
    const supplierId =
      draft?.type === "supplier"
        ? draft.businessId
        : business?.type === "supplier"
          ? business.id
          : null;

    if (!supplierId) {
      router.replace(ROUTES.businesses);
      return;
    }
    if (business?.verification_status === "verified") {
      router.replace(ROUTES.businesses);
      return;
    }
    setBusinessId(supplierId);
    if (!draft?.businessId && business?.type === "supplier") {
      saveBusinessDraft({
        legal_name: business.legal_name ?? business.name,
        name: business.name,
        type: "supplier",
        tax_number: business.tax_number ?? "",
        contact_person: "",
        contact_phone: business.contact_phone ?? "",
        contact_email: business.contact_email ?? "",
        email_domain: business.email_domain ?? "",
        street: business.address?.street ?? "",
        street2: "",
        city: business.address?.city ?? "",
        governorate: business.address?.governorate ?? "Beirut",
        postal_code: business.address?.postal_code ?? "",
        businessId: business.id,
      });
    }
    setReady(true);
  }, [business, router]);

  if (!ready) {
    return (
      <p className="py-10 text-sm text-muted-foreground">Preparing verification…</p>
    );
  }

  const canSubmit = Boolean(files.commercial && files.tax && files.address);

  async function submitForReview() {
    setError(null);
    if (!canSubmit || !businessId) {
      setError("Upload all three documents to continue.");
      return;
    }
    setPending(true);
    try {
      const documents = [];
      for (const key of ["commercial", "tax", "address"] as const) {
        const file = files[key]!;
        const uploaded = await identityApi.uploadVerificationDocument(
          businessId,
          DOC_TYPES[key],
          file,
        );
        documents.push({
          document_type: DOC_TYPES[key],
          file_name: file.name,
          url: uploaded.url,
        });
      }
      await identityApi.submitSupplierVerification(businessId, documents);
      void refreshSession();
      router.push(ROUTES.businessesComplete);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't submit verification. Try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <BackLink href={ROUTES.businesses}>Back</BackLink>
          <h1 className="mt-2 font-[family-name:var(--font-outfit)] text-2xl font-bold text-heading sm:text-3xl">
            Verify your supplier business
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Required only for suppliers. Upload documents — TradeBay staff must
            approve before you can sell. Buyers never complete this step.
          </p>
        </div>
        <BusinessStepper active={2} variant="supplier" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.9fr)]">
        <div className="space-y-3 border border-input bg-card p-5 sm:p-6">
          <h2 className="font-[family-name:var(--font-outfit)] text-base font-bold text-heading">
            Required documents
          </h2>
          <DocumentUploadCard
            title="Commercial registration"
            fileName={files.commercial?.name}
            onSelect={(file) =>
              setFiles((prev) => ({ ...prev, commercial: file }))
            }
          />
          <DocumentUploadCard
            title="Tax certificate"
            fileName={files.tax?.name}
            onSelect={(file) => setFiles((prev) => ({ ...prev, tax: file }))}
          />
          <DocumentUploadCard
            title="Business address proof"
            fileName={files.address?.name}
            onSelect={(file) =>
              setFiles((prev) => ({ ...prev, address: file }))
            }
          />

          {error ? (
            <p role="alert" className="tb-alert tb-alert--error">
              {error}
            </p>
          ) : null}

          <button
            type="button"
            disabled={pending}
            onClick={() => void submitForReview()}
            className="tb-btn tb-btn--accent tb-btn--lg tb-btn--block lg:hidden"
          >
            <BusyText busy={pending}>{pending ? "Submitting…" : "Submit for verification"}</BusyText>
          </button>
        </div>

        <BusinessAsideCard
          illustration="docs"
          title="Verification builds buyer trust"
          points={[
            "Verified companies rank higher in sourcing",
            "Documents stay private to platform review",
            "Selling stays locked until an admin approves",
          ]}
          action={
            <button
              type="button"
              disabled={pending}
              onClick={() => void submitForReview()}
              className="hidden h-12 w-full items-center justify-center rounded-xl bg-accent text-sm font-bold text-accent-foreground disabled:opacity-60 lg:inline-flex"
            >
              <BusyText busy={pending}>{pending ? "Submitting…" : "Submit for verification"}</BusyText>
            </button>
          }
        />
      </div>
    </div>
  );
}
