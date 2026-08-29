# Merchant CRM dashboard

Status: built. Reached at `/admin` once a merchant's agent is published; store setup moved to
`/admin/setup`.

## Why it exists

Onboarding ends when the agent goes live, and at that moment the merchant's questions change.
They stop asking "did my file upload" and start asking CRM questions: who is buying, what is
selling, what needs attention today. Leaving them on the upload form answers none of those, so
publishing now hands them a dashboard instead.

## What it shows, and why those things

The layout follows the CRM dashboard conventions NetSuite documents: five to seven reports (more
than that stops being readable), a mix of backward-looking, in-the-moment and forward-looking
figures, KPIs carrying a period-over-period comparison, and a task list that turns state into
today's work.

| Panel | What it is | NetSuite equivalent |
|---|---|---|
| Three KPI cards | Customers, revenue, orders for the window, each against the previous window of the same length | KPIs with comparison |
| Revenue analytics | Daily takings as a dot column per day, plus a labelled forecast | Forecasted sales; revenue as a trend |
| Priority tasks | Open work derived from live state, each with a real remainder | Tasks and appointments; alerts |
| Manage customers | Per-customer rows with status, last basket, stated concern and value | Customer/lead list with drill-down |
| Performance (Analytics tab) | Conversion, average order value, repeat rate, lifetime spend, recoverable carts | Lead conversion ratio, CLTV, retention |

Tabs: **Overview · Customers · Products · Tasks · Analytics**. The window control (30/14/7 days)
drives every figure on the page.

### Where each number comes from

Everything is computed in `merchant/insights.py` from this merchant's own rows. There is no
metrics store and nothing is cached, so a checkout completed in the storefront during a demo
moves the dashboard on the next load.

- **Revenue, orders, customers** — `orders` joined to `transactions` (status `approved`) and to
  `carts`. `transactions` has no merchant column, so the tenant boundary is the cart.
- **Conversion** — paid orders over sessions opened against this merchant in the window.
- **Repeat rate and lifetime spend** — over *every* buyer, all time, not the twelve rows the
  customer table shows.
- **Recoverable carts** — carts with no approved transaction against them.
- **Follow-up** — shoppers with a `fail` trust event and no order.
- **Tasks** — sold-out and low-stock products, products without photos, rows held out of the live
  catalog by the last upload, abandoned carts, failed checkouts, an unpublished agent.

Every derived figure carries its own `basis` string naming the denominator, so a percentage on
this screen can always be checked ("40% — 8 of 20 customers bought more than once").

### The forecast

The projected series is the **trailing seven-day mean carried forward**, stated as such in the
payload and printed under the chart. It is arithmetic, not a model. Deliberately the dullest
method that still answers "if the last week repeats, where does this month land".

## Summarising any business content

The assistant panel answers a merchant's question about their own data. The control rule is the
same one the shopper agent runs under: **facts travel through deterministic code, only phrasing
travels through a model.**

1. The question is routed to one of seven reports by deterministic keyword matching
   (`overview`, `revenue`, `orders`, `customers`, `catalog`, `tasks`, `payments`).
2. The report's figures and its prose are built from `merchant_insights` output. This text is
   correct on its own and is what a demo-mode or offline run shows.
3. Only then, if a model is configured, it may reword that text — and the rewrite is **rejected
   unless every number in it is one it was handed**. `_NUMBER` normalises `3,552.00` and `3552`
   to the same figure, so separators cannot smuggle a new one past the check.

On rejection or any error the merchant reads the deterministic sentence. A dashboard that
invents a revenue figure is worse than no dashboard, so the failure mode is boring on purpose.

## API

Both routes are `assert_merchant`-guarded and scoped to one tenant.

```
GET  /merchant/{merchant_id}/insights?days=30        -> the whole dashboard payload
POST /merchant/{merchant_id}/insights/summary        -> {question?, scope?, days?}
```

`days` is bounded to 1–45. An unknown `scope` is a 400 naming the valid reports rather than a
guess. Response shapes are mirrored in `web/src/features/merchant/insights.ts`.

## Demo data

A fresh database has no trading history, so `seed/demo_history.py` writes 60 days of it for
Mysa Skin: sessions, signed mandates, server-priced carts, approved authorizations, orders and
trust events, written exactly as the live code writes them. It is:

- **Deterministic** — the same day plan, roster and baskets every time, so the numbers on stage
  match the numbers in rehearsal.
- **Inert** — historic sessions carry no session-token hash, so none can be resumed or spent
  against.
- **Written once** — reseeding a store that already has orders is a no-op.

It spans two windows because the dashboard's "compare" is the 30 days before the 30 on screen.
The shape is chosen to be worth looking at: 14 customers this window against 10 before it, on
slightly *lower* revenue — customer count growing while basket size falls is exactly the pattern
a merchant needs a dashboard to make visible.

Seeded history remains simulated. Live orders retain their own `transactions.simulated` flag, so
the dashboard reports whether the selected period used the simulator, the Visa sandbox adapter,
or both; an empty period describes the currently configured adapter instead of making a claim
about transactions that do not exist.

## Routing

| Path | Renders |
|---|---|
| `/admin` | CRM dashboard (redirects to `/admin/setup` if the merchant is still a draft) |
| `/admin/setup` | Store setup — the onboarding flow |

Publishing from setup navigates to `/admin`. Store setup stays reachable from the dashboard's
settings icon, its footer, and every task that is fixed there.

## Styling

`web/src/features/merchant/dashboard.css` stays scoped under `.crm-shell`, but aliases the same
tokens used by merchant onboarding: warm paper and white surfaces, sage navigation and data marks,
coral primary actions, serif section headings, thin neutral borders and compact radii. The CRM is
denser than setup because it carries tables and charts, but it now reads as the next screen in the
same merchant journey rather than a separate purple product. Nothing leaks into the storefront or
setup page.

## Tests

`tests/test_insights.py` — 20 cases, covering tenant isolation (a rival key gets 403; a new
merchant sees zeroes, not the demo merchant's trade), the window comparison arithmetic, the chart
totalling to the KPI, the forecast being reproducible from the series, task derivation, the
repeat-rate denominator, question routing, the invented-figure guardrail, and a live order moving
the numbers. `web/e2e/core.spec.ts` covers the published-merchant landing and the summary panel.
