TradeBay is a **Lebanon-focused B2B wholesale marketplace** connecting buyer and supplier companies in one platform for catalogs, RFQs, quotations, negotiation, orders, payments, and invoices. 

**Core functionality**

* **Identity & businesses:** Registration, email verification, authentication, company memberships, roles, invitations, and permissions.
* **Suppliers:** Suppliers submit business documents and must be **verified before selling**.
* **Catalog & inventory:** Products, categories, pricing, images, minimum orders, and stock reservations.
* **RFQ & quotations:** Buyers request quotes; suppliers respond; buyers can award quotations.
* **Negotiation:** Buyers and suppliers can exchange offers before accepting a quote.
* **Orders:** Accepted quotes or paid checkouts create orders that move through confirmation → shipping → delivery.
* **Finance:** Cash/card payments, invoices, receipts, commissions, supplier payouts, refunds, and credit notes.
* **AI:**

  * **Ask the Bay:** Natural-language product sourcing from verified suppliers.
  * **Business Planner:** Generates a business/sourcing plan based on user answers and catalog data.
* **Notifications, reviews, disputes, and admin management** are also included. 

### Main workflow

**Register → Verify → Create/switch company → Supplier verification → Products/stock → Buyer cart/RFQ/AI → Quotation → Negotiation → Accept/Checkout → Reserve stock → Invoice/Payment → Confirm → Ship → Deliver → Complete.** 

### Architecture

* **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS
* **Backend:** FastAPI, Pydantic v2, Python 3.12
* **Database:** MongoDB 7 with replica-set transactions
* **Auth:** JWT + HTTP-only cookies + bcrypt
* **Integrations:** Stripe, Elastic Email, Sentry, OpenAI-compatible API
* **Infrastructure:** Docker Compose + GitHub Actions 

### Security

The system includes bcrypt password hashing, HTTP-only cookies, refresh-token reuse detection, verification/reset attempt limits, role-based authorization, CORS restrictions, security headers, request IDs, rate limiting, audit logs, and webhook validation. Production requires HTTPS, strong secrets, restricted MongoDB access, and appropriate shared storage for multiple API instances. 

### Production status

**Implemented:** Core marketplace domains, cash checkout, RFQs, negotiation, orders, shipments, invoices, Ask the Bay, and Business Planner.

**Partial:** Card payments, email, carrier webhooks, and some observability/CI coverage require additional configuration or work.

**Important production considerations:** MongoDB must be a replica set; uploads currently use local disk; rate limiting is per API process; backups, DNS, and MongoDB infrastructure are not provisioned by the repository. 

**In one sentence:** TradeBay is a full B2B marketplace for Lebanese businesses, with company-based permissions, verified suppliers, procurement/RFQ workflows, negotiation, inventory, finance, and AI-assisted sourcing/planning.
