"use client";

import { AdminAct, AdminPage } from "@/components/admin/AdminUi";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { DirectoryMast } from "@/components/shared/DirectoryMast";
import { BackLink } from "@/components/ui/BackLink";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  systemSettingsApi,
  type BusinessSettings,
  type PlatformSettings,
  type TaxSettings,
} from "@/lib/api/systemSettingsApi";
import { ROUTES } from "@/lib/constants";
import {
  letterheadSettingsSchema,
  platformSettingsSchema,
  taxSettingsSchema,
} from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useCallback, useEffect, useState } from "react";

function SettingsInner() {
  const { success, error: toastError } = useToast();
  const [platform, setPlatform] = useState<PlatformSettings | null>(null);
  const [tax, setTax] = useState<TaxSettings | null>(null);
  const [business, setBusiness] = useState<BusinessSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [pName, setPName] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [commission, setCommission] = useState("0.05");
  const [minOrder, setMinOrder] = useState("0");
  const [provider, setProvider] = useState("");

  const [taxName, setTaxName] = useState("VAT");
  const [taxRate, setTaxRate] = useState("0.11");

  const [bName, setBName] = useState("");
  const [bEmail, setBEmail] = useState("");
  const [bPhone, setBPhone] = useState("");
  const [trn, setTrn] = useState("");
  const [prefix, setPrefix] = useState("TB-INV");
  const platformLive = useLiveFields(platformSettingsSchema, {
    platform_name: pName,
    commission_rate: commission,
    minimum_order_value: minOrder,
    payment_provider: provider,
  });
  const taxLive = useLiveFields(taxSettingsSchema, {
    name: taxName,
    rate: taxRate,
  });
  const businessLive = useLiveFields(letterheadSettingsSchema, {
    business_name: bName,
    business_email: bEmail,
    business_phone: bPhone,
    tax_registration_number: trn,
    invoice_prefix: prefix,
  });

  const reload = useCallback(() => {
    void systemSettingsApi
      .getAll()
      .then((data) => {
        setPlatform(data.platform);
        setTax(data.tax);
        setBusiness(data.business);
        if (data.platform) {
          setPName(data.platform.platform_name);
          setCurrency(data.platform.default_currency);
          setCommission(data.platform.commission_rate ?? "0.05");
          setMinOrder(data.platform.minimum_order_value ?? "0");
          setProvider(data.platform.payment_provider ?? "");
        }
        if (data.tax) {
          setTaxName(data.tax.name);
          setTaxRate(data.tax.rate ?? "0");
        }
        if (data.business) {
          setBName(data.business.business_name);
          setBEmail(data.business.business_email ?? "");
          setBPhone(data.business.business_phone ?? "");
          setTrn(data.business.tax_registration_number ?? "");
          setPrefix(data.business.invoice_prefix);
        }
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load settings");
      });
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  function savePlatform() {
    if (!platformLive.finish()) return;
    setBusy("platform");
    void systemSettingsApi
      .updatePlatform({
        platform_name: pName.trim(),
        default_currency: currency,
        commission_rate: commission,
        minimum_order_value: minOrder,
        payment_provider: provider.trim() || null,
      })
      .then((row) => {
        setPlatform(row);
        success("Platform settings saved");
      })
      .catch((err) =>
        toastError("Couldn't save", err instanceof ApiError ? err.message : "Error"),
      )
      .finally(() => setBusy(null));
  }

  function saveTax() {
    if (!taxLive.finish()) return;
    setBusy("tax");
    void systemSettingsApi
      .updateTax({ name: taxName.trim(), rate: taxRate })
      .then((row) => {
        setTax(row);
        success("Tax settings saved", "Historical invoices keep their snapped rates.");
      })
      .catch((err) =>
        toastError("Couldn't save", err instanceof ApiError ? err.message : "Error"),
      )
      .finally(() => setBusy(null));
  }

  function saveBusiness() {
    if (!businessLive.finish()) return;
    setBusy("business");
    void systemSettingsApi
      .updateBusiness({
        business_name: bName.trim(),
        business_email: bEmail.trim() || null,
        business_phone: bPhone.trim() || null,
        tax_registration_number: trn.trim() || null,
        invoice_prefix: prefix.trim().toUpperCase(),
      })
      .then((row) => {
        setBusiness(row);
        success("Business settings saved");
      })
      .catch((err) =>
        toastError("Couldn't save", err instanceof ApiError ? err.message : "Error"),
      )
      .finally(() => setBusy(null));
  }

  return (
    <AdminPage>
      <DirectoryMast
        title="System settings"
        mark="Platform"
        size="page"
        actions={
          <BackLink href={ROUTES.admin.home}>Command center</BackLink>
        }
      />

      {error ? (
        <FeedbackBanner tone="error" title="Settings error">
          {error}
        </FeedbackBanner>
      ) : null}

      <section className="tb-inv-panel mb-6">
        <header className="tb-inv-panel-head">
          <h2>Platform</h2>
          <p>Name, currency, commission, and order floor</p>
        </header>
        <div className="tb-inv-form-grid p-5">
          <label className="tb-split-field" data-state={platformLive.errors.platform_name ? "error" : undefined}>
            <span>Platform name</span>
            <input
              value={pName}
              onChange={(e) => setPName(e.target.value)}
              onBlur={() => platformLive.touch("platform_name")}
            />
            <FieldError error={platformLive.errors.platform_name} />
          </label>
          <label className="tb-split-field">
            <span>Default currency</span>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
              <option value="USD">USD</option>
              <option value="LBP">LBP</option>
            </select>
          </label>
          <label className="tb-split-field" data-state={platformLive.errors.commission_rate ? "error" : undefined}>
            <span>Commission rate (e.g. 0.05 = 5%)</span>
            <NumberInput
              kind="decimal"
              maxDecimals={4}
              value={commission}
              onChange={(e) => setCommission(e.target.value)}
              onBlur={() => platformLive.touch("commission_rate")}
            />
            <FieldError error={platformLive.errors.commission_rate} />
          </label>
          <label className="tb-split-field" data-state={platformLive.errors.minimum_order_value ? "error" : undefined}>
            <span>Minimum order value</span>
            <NumberInput
              kind="decimal"
              value={minOrder}
              onChange={(e) => setMinOrder(e.target.value)}
              onBlur={() => platformLive.touch("minimum_order_value")}
            />
            <FieldError error={platformLive.errors.minimum_order_value} />
          </label>
          <label className="tb-split-field">
            <span>Payment provider name (no secrets)</span>
            <input
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              onBlur={() => platformLive.touch("payment_provider")}
              placeholder="stripe"
            />
            <FieldError error={platformLive.errors.payment_provider} />
          </label>
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <AdminAct
            tone="go"
            busy={busy === "platform"}
            disabled={busy === "platform"}
            onClick={savePlatform}
          >
            {busy === "platform" ? "Saving…" : "Save platform"}
          </AdminAct>
        </div>
        {platform ? (
          <p className="px-5 pb-4 text-xs text-muted-foreground">
            Current commission {platform.commission_rate} · type {platform.commission_type}
          </p>
        ) : null}
      </section>

      <section className="tb-inv-panel mb-6">
        <header className="tb-inv-panel-head">
          <h2>Tax / VAT</h2>
          <p>Active rate is snapshotted onto invoices when issued</p>
        </header>
        <div className="tb-inv-form-grid p-5">
          <label className="tb-split-field" data-state={taxLive.errors.name ? "error" : undefined}>
            <span>Tax name</span>
            <input
              value={taxName}
              onChange={(e) => setTaxName(e.target.value)}
              onBlur={() => taxLive.touch("name")}
            />
            <FieldError error={taxLive.errors.name} />
          </label>
          <label className="tb-split-field" data-state={taxLive.errors.rate ? "error" : undefined}>
            <span>Rate (e.g. 0.11 = 11%)</span>
            <NumberInput
              kind="decimal"
              maxDecimals={4}
              value={taxRate}
              onChange={(e) => setTaxRate(e.target.value)}
              onBlur={() => taxLive.touch("rate")}
            />
            <FieldError error={taxLive.errors.rate} />
          </label>
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <AdminAct
            tone="go"
            busy={busy === "tax"}
            disabled={busy === "tax"}
            onClick={saveTax}
          >
            {busy === "tax" ? "Saving…" : "Save tax"}
          </AdminAct>
        </div>
        {tax ? (
          <p className="px-5 pb-4 text-xs text-muted-foreground">
            Active {tax.name} @ {tax.rate}
            {tax.effective_from ? ` from ${tax.effective_from.slice(0, 10)}` : ""}
          </p>
        ) : null}
      </section>

      <section className="tb-inv-panel mb-6">
        <header className="tb-inv-panel-head">
          <h2>Business information</h2>
          <p>Letterhead and invoice prefix for TradeBay documents</p>
        </header>
        <div className="tb-inv-form-grid p-5">
          <label className="tb-split-field" data-state={businessLive.errors.business_name ? "error" : undefined}>
            <span>Business name</span>
            <input
              value={bName}
              onChange={(e) => setBName(e.target.value)}
              onBlur={() => businessLive.touch("business_name")}
            />
            <FieldError error={businessLive.errors.business_name} />
          </label>
          <label className="tb-split-field" data-state={businessLive.errors.business_email ? "error" : undefined}>
            <span>Business email</span>
            <input
              value={bEmail}
              onChange={(e) => setBEmail(e.target.value)}
              onBlur={() => businessLive.touch("business_email")}
            />
            <FieldError error={businessLive.errors.business_email} />
          </label>
          <label className="tb-split-field">
            <span>Business phone</span>
            <input
              value={bPhone}
              onChange={(e) => setBPhone(e.target.value)}
              onBlur={() => businessLive.touch("business_phone")}
            />
            <FieldError error={businessLive.errors.business_phone} />
          </label>
          <label className="tb-split-field">
            <span>Tax registration number</span>
            <input
              value={trn}
              onChange={(e) => setTrn(e.target.value)}
              onBlur={() => businessLive.touch("tax_registration_number")}
            />
            <FieldError error={businessLive.errors.tax_registration_number} />
          </label>
          <label className="tb-split-field" data-state={businessLive.errors.invoice_prefix ? "error" : undefined}>
            <span>Invoice prefix</span>
            <input
              value={prefix}
              onChange={(e) => setPrefix(e.target.value)}
              onBlur={() => businessLive.touch("invoice_prefix")}
            />
            <FieldError error={businessLive.errors.invoice_prefix} />
          </label>
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <AdminAct
            tone="go"
            busy={busy === "business"}
            disabled={busy === "business"}
            onClick={saveBusiness}
          >
            {busy === "business" ? "Saving…" : "Save business"}
          </AdminAct>
        </div>
        {business ? (
          <p className="px-5 pb-4 text-xs text-muted-foreground">
            Invoices use prefix {business.invoice_prefix}-YYYY-####
          </p>
        ) : null}
      </section>
    </AdminPage>
  );
}

export default function AdminSystemSettingsPage() {
  return (
    <PermissionGate permission="settings.manage">
      <SettingsInner />
    </PermissionGate>
  );
}
