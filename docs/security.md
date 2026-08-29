# Tenant isolation — who can reach what

Written after an audit found that no endpoint authenticated anyone. This is the model the code
now enforces, the reasoning behind it, and what is still open.

Regression tests: [`tests/test_isolation.py`](../tests/test_isolation.py). Findings and the
before/after evidence: [`docs/testing.md`](./testing.md).

---

## Three credentials, none interchangeable

| Credential | Header | Issued by | Proves |
|---|---|---|---|
| Merchant API key | `X-Merchant-Key` | `POST /merchant/onboard`, once | control of **one** merchant |
| Consumer token | `Authorization: Bearer …` | `POST /consumer/register` / `login` | which shopper you are |
| Session token | `X-Session-Token` | `POST /agent/session`, once | you opened **this** shopping session |

Secrets are never stored in the clear: tokens are random 256-bit values kept as SHA-256
digests, passwords use scrypt with a per-row salt, and every comparison is constant-time.
A merchant row with no key on record is treated as **locked, not open** — an unkeyed row means
a seeding or migration gap, and failing closed is the only safe reading of it.

## Merchant isolation

A merchant key authorises exactly one merchant. Presenting merchant A's key against merchant B
is a `403`, not a `404` — the resource exists, you simply may not have it.

- `GET /merchant/{id}/config` · `PUT /merchant/{id}/config` · `POST /merchant/{id}/catalog` ·
  `GET /merchant/{id}/snippet` all require the key for that id.
- `catalog_product(sku, merchant_id)` takes the merchant as a **required argument**, so an
  unscoped product read is not expressible in the code. The HTTP route
  `GET /catalog/product/{sku}` requires `merchant_id` as a query parameter (`422` without it)
  and returns `404` when the SKU belongs to someone else.
- `_comparison()` reads every SKU scoped to the session's merchant and re-checks the result
  through the Guardian, so a rival's SKU is a `404` rather than a cross-tenant read.
- `create_cart` selects products `WHERE sku=? AND merchant_id=?` against the session's
  merchant, so a cart cannot mix merchants.

**The agent cannot widen its own scope.** The Guardian re-pins `merchant_ids` and `category`
server-side on every interpretation and rejects any `selected_sku` that was not already on
screen. That is a property of the code path, not of the prompt — a model that is talked into
asking for another merchant's catalog still cannot get it.

**The agent cannot write anything.** The `agent/` module holds no write path to merchants,
products, or configuration. Its only writes are to its own session row (visible SKUs, profile)
and, through `payments/`, to carts and mandates it is entitled to. Catalog and configuration
changes exist only behind a merchant key, which the agent never holds.

## Buyer isolation

Identity is never read from a request body. `POST /agent/session` takes no `consumer_id`; it
reads the consumer token, or treats the session as anonymous. While identity came from the
body, anyone could open a session as any shopper and have that shopper's saved shipping
address resolved into their cart.

- Every session-scoped endpoint — turn, message, action, confirm, pay, limit, status, trust
  events, receipt, mandate chain — requires the session token minted for that session. Another
  session's valid token is a `403`.
- `GET /consumer/{id}/addresses` and the default-address write require a consumer token for
  **that** consumer.
- A receipt belongs to the session that bought it, not to whoever can name a transaction id.
- Login answers "no such account" and "wrong password" identically, so the endpoint cannot be
  used to test which emails are registered.

**Anonymous browsing is deliberate.** Search, routines, comparison and product detail all work
without an account. Each anonymous session gets its own generated consumer id, so two anonymous
shoppers are as isolated from each other as two signed-in ones. Checkout is where an account
starts to matter: a cart needs a shipping address, and an anonymous session has none, so it
returns `409 ADDRESS_REQUIRED` rather than silently using someone else's.

**An unpublished merchant is not open for business.** `GET /catalog/search` and
`GET /catalog/product/{sku}` only return rows belonging to a merchant whose `status` is
`published`. A merchant who has onboarded and uploaded stock but not launched keeps their
catalog and prices private — they can still see their own with their key, and another
merchant's key does not unlock it. The internal `catalog_search()` takes a plain
`include_unpublished` flag rather than a header, because the agent calls it directly and a
FastAPI `Header()` default arrives as a `Header` object, not `None`, when it does.

**Credentials are throttled and expire.** Password guessing is limited per account and per
client; a correct login clears the counter, so a typo never accumulates toward a lockout.
Sign-up is limited per client too, but far more loosely — several people signing up from one
network is ordinary. Sessions expire after 12 hours. Signing out revokes only the token
presented, so logging out on a laptop does not log you out on a phone. Trivially common and
single-character-repeat passwords are refused.

**Signing in mid-visit claims the session in progress.** `PUT /agent/session/{id}/identity`
attaches an account to a session that was started as a guest, so a basket built while browsing
survives reaching the till. It requires **both** credentials — the session token proves you
opened this session, the consumer token proves who you are — and a session already bound to
someone else is never re-bound. Without it, signing in at checkout would have to re-open the
session and throw the basket away.

## Verified

`tests/test_isolation.py` (20), `tests/test_route_authorization.py` (4) and
`tests/test_auth_hardening.py` (9) cover each boundary above, plus a live suite of 24 cases
run against a running server. Both were red before these changes and are green after:

| Was | Now |
|---|---|
| Any caller could rewrite any merchant's config | `401` without a key, `403` with the wrong one |
| Any caller could inject products into any catalog | `401` / `403` |
| A session pinned to merchant A could read merchant B's rows via `/agent/action` | `404`, no rival data |
| `GET /catalog/product/{sku}` returned any merchant's row | `422` unscoped, `404` cross-merchant |
| Any caller could read any buyer's saved addresses | `401` / `403` |
| Any caller could open a session as any buyer | identity comes from the token; body is ignored |
| Any caller could read any session's trust log | session token required, not transferable |
| Signing in mid-visit discarded the shopper's basket | the session is claimed, the basket survives |
| `POST /pay/consent` recorded consent for any session, unguarded | session token required |
| The bank routes wrote trust events into any session's audit trail | naming a session requires holding it |
| A new unguarded route shipped silently | `tests/test_route_authorization.py` fails the build |
| An unpublished merchant's catalog and prices were public | published-only, owner sees their own |
| Passwords could be ground down with no limit | throttled per account and per client |
| Sessions never expired | 12-hour lifetime, enforced on every session call |
| Signing out ended every device's session | only the presented token is revoked |

## Enforcement — why this should not drift again

New endpoints default to open. That is not a hypothetical: the staged-catalog preview and
approve endpoints arrived unauthenticated in a merge, and `POST /pay/consent` sat unguarded
right next to the gated `/agent/confirm`, reaching the same `record_consent()` without a
session token or the human-confirmation check. Both were caught by reading, which does not
scale.

`tests/test_route_authorization.py` walks every route the app exposes and fails the build if
one has no credential check and is not on an explicit `PUBLIC_ROUTES` list with a written
reason. Three further assertions narrow it: every `/merchant/{merchant_id}` route must use
`assert_merchant`, every route naming a `{session_id}` must use `assert_session`, and the
public list may not name a route that no longer exists. Adding an unguarded endpoint now
fails CI rather than shipping quietly.

One subtlety the walker has to handle: this FastAPI version wraps `include_router()` results,
so the routes hang off `original_router` rather than the wrapper. Walking `app.routes` alone
reports 6 routes instead of 40 and looks like it passed.

### Currently public, deliberately

`/` · `/health` · `/docs` · `/redoc` · `/openapi.json` · `POST /agent/session` (mints the
session token) · `POST /consumer/register` · `POST /consumer/login` · `POST /merchant/onboard`
(all three create the credential) · `GET /catalog/search` and `GET /catalog/product/{sku}`
(public storefront, `merchant_id` required and scoping) · `GET /bank/token/{bank_token}`
(issuer simulator; the token is itself the secret). `POST /pay/authorize` is not on this list —
it is guarded by TAP signature verification rather than by one of the three credentials.

## Still open

- **The throttle is in-process**, so it is per-worker. It stops a script hammering one account;
  a shared limiter (Redis or the edge) is what a real deployment needs.
- **Registration still reveals whether an email has an account** (`409 EMAIL_TAKEN`). Hiding
  that needs the "we have sent you a link" pattern and an email path we do not have, and
  lying to someone typing their own address is worse than the leak. Throttled instead —
  a deliberate trade, not an oversight.
- **Consumer tokens do not rotate** and live 7 days.
- **The merchant key is a single long-lived secret** with no rotation endpoint. Rotation means
  re-onboarding today.
- **CORS is wide** (`allow_origin_regex=r"https?://.*"`) for demo convenience. Credentials are
  sent in headers rather than cookies, so this is not a CSRF hole, but it should be narrowed
  before anything real.
- **The issuer/bank simulator is otherwise unauthenticated**, by design — it stands in for an
  external ACS, not for a tenant of this system. Only its trust-log writes are now gated.
- **`POST /pay/consent` should probably be deleted.** It is undeclared in `contracts.md`, has no
  caller, and duplicates `/agent/confirm` minus the human-confirmation check. It is now gated
  rather than removed because `payments/` is Y4's module — their call.
