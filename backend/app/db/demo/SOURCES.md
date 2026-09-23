# Demo seed sources

TradeBay seed data is **development/demo only**.

No record in this seed is a TradeBay customer, supplier, buyer, partner, or
verified member in the real world.

## Intentionally excluded real businesses

These companies were verified from public websites so the *synthetic* catalog
could follow realistic Lebanese wholesale categories. They are **not** inserted
as TradeBay businesses, users, products, RFQs, orders, or reviews.

| Company (public) | Industry | Public source | Why excluded |
| --- | --- | --- | --- |
| Cortas Canning & Refrigerating Company SAL | Food manufacturing (tahini, molasses, canned goods, pickles) | https://www.cortasfood.com/ | Real company — must not appear as a TradeBay member |
| Al Wadi Al Akhdar | Lebanese food products since 1979 | https://www.alwadi.com/ | Real company — not a TradeBay customer |
| Cimenterie Nationale SAL (Al Sabeh Cement) | Cement, founded 1953 | https://www.cimnat.com.lb/ | Real company — not a TradeBay customer |
| Fattal Group | Beirut-headquartered FMCG / brand distribution since 1897 | https://www.fattal.com.lb/ | Real company — not a TradeBay customer |
| INDEVCO Group | Packaging / industrial manufacturing, HQ Lebanon | https://www.indevcogroup.com/ | Real company — not a TradeBay customer |
| UNIPAK SAL (INDEVCO member) | Corrugated and solid-board packaging, Halat | https://unipaklb.com/en | Real company — not a TradeBay customer |

Public contact emails, personal names, and private phone numbers from those
sites were **not** copied into seed users.

## What *is* in the database

All trading companies, logins, SKUs, RFQs, quotations, orders, invoices,
reviews, chats, and AI-sourcing examples are **synthetic demo records**:

- `data_source`: `synthetic_demo`
- `is_demo_seed`: `true` (on `business_accounts`)

Company names, Lebanese addresses, original SVG logos, and KYC PDFs are
**demo artwork** so the admin directory looks complete. They are not real
TradeBay customers.

Product ranges (olive oil, tahini, cement bags, corrugated boxes, office paper)
are *category-inspired* by the public industries above, not those companies'
catalogs or prices.

Prices, MOQs, stock, and lead times are demo values.
