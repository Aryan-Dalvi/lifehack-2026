"""Every route is authorised, or is on this list with a reason.

The reason this test exists: new endpoints default to open. Twice now, work landed that added
routes with no credential check - the staged-catalog preview and approve endpoints arrived
unauthenticated in a merge, and /pay/consent sat unguarded next to the gated /agent/confirm
doing the same thing. Both were caught by reading, which does not scale and does not survive
a busy afternoon.

So: adding a route with no guard fails this test. Making it pass means either adding a guard
or adding it to PUBLIC_ROUTES with a written justification. That is a deliberate decision
rather than an oversight, which is the whole point.
"""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("DEMO_MODE", "1")

from app.main import app

# Any of these appearing in a handler's source means the route establishes who is calling.
GUARDS = (
    "assert_merchant",
    "assert_consumer",
    "require_consumer",
    "assert_session",
    "verify_tap_request",
)

# Routes that are reachable without a credential, each with the reason it has to be.
PUBLIC_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/"): "service banner, no data",
    ("GET", "/health"): "liveness probe, no data",
    ("GET", "/docs"): "API docs UI",
    ("GET", "/docs/oauth2-redirect"): "API docs UI",
    ("GET", "/redoc"): "API docs UI",
    ("GET", "/openapi.json"): "API schema",
    ("POST", "/agent/session"): "mints the session token; nothing to present yet",
    ("POST", "/consumer/register"): "creating the credential",
    ("POST", "/consumer/login"): "exchanging a password for the credential",
    ("POST", "/merchant/onboard"): "creating the merchant and its key",
    ("GET", "/catalog/search"): "public storefront; merchant_id is required and scopes it",
    ("GET", "/catalog/template"): "a blank workbook; the shape of a catalog, no merchant data",
    ("GET", "/catalog/product/{sku}"): "public storefront; merchant_id is required and scopes it",
    ("GET", "/bank/token/{bank_token}"): "issuer simulator; the bank token is itself the secret",
}


def _routes() -> list[tuple[str, str, list[str]]]:
    """Every (method, path, guards) the app exposes.

    include_router() results are wrapped, so the real routes hang off original_router rather
    than off the wrapper - walking app.routes alone silently reports almost nothing.
    """

    def walk(routes) -> list[tuple[str, str, list[str]]]:
        found: list[tuple[str, str, list[str]]] = []
        for route in routes:
            inner = getattr(route, "original_router", None)
            children = getattr(route, "routes", None) or (
                getattr(inner, "routes", None) if inner else None
            )
            if children:
                found += walk(children)
                continue
            path, methods = getattr(route, "path", None), getattr(route, "methods", None)
            if not path or not methods:
                continue
            endpoint = getattr(route, "endpoint", None)
            try:
                source = inspect.getsource(endpoint) if endpoint else ""
            except (OSError, TypeError):
                source = ""
            guards = [g for g in GUARDS if f"{g}(" in source]
            for method in sorted(set(methods) - {"HEAD", "OPTIONS"}):
                found.append((method, path, guards))
        return found

    return sorted({(m, p, tuple(g)) for m, p, g in walk(app.routes)})


def test_every_route_is_guarded_or_deliberately_public() -> None:
    unguarded = [
        f"{method} {path}"
        for method, path, guards in _routes()
        if not guards and (method, path) not in PUBLIC_ROUTES
    ]
    assert not unguarded, (
        "These routes have no credential check and are not listed as public:\n  "
        + "\n  ".join(unguarded)
        + "\n\nAdd a guard, or add the route to PUBLIC_ROUTES with the reason it is safe."
    )


def test_public_route_list_has_no_stale_entries() -> None:
    """A list of exceptions is only trustworthy while every exception is still real."""
    live = {(method, path) for method, path, _ in _routes()}
    stale = [f"{method} {path}" for method, path in PUBLIC_ROUTES if (method, path) not in live]
    assert not stale, "PUBLIC_ROUTES names routes that no longer exist:\n  " + "\n  ".join(stale)


def test_every_merchant_route_uses_the_merchant_key() -> None:
    """Merchant data is per-tenant: a merchant route that is not key-checked is a hole."""
    offenders = [
        f"{method} {path}"
        for method, path, guards in _routes()
        if path.startswith("/merchant/{merchant_id}") and "assert_merchant" not in guards
    ]
    assert not offenders, "Merchant routes missing assert_merchant:\n  " + "\n  ".join(offenders)


def test_every_session_scoped_route_checks_the_session_token() -> None:
    """Anything naming a session_id must prove the caller holds that session."""
    exempt = {("POST", "/agent/session")}  # mints the token
    offenders = [
        f"{method} {path}"
        for method, path, guards in _routes()
        if "{session_id}" in path and "assert_session" not in guards and (method, path) not in exempt
    ]
    assert not offenders, "Session routes missing assert_session:\n  " + "\n  ".join(offenders)
