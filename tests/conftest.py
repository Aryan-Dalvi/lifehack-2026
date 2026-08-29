"""Test environment: the suite must never reach a live model, and it must carry credentials.

app/settings.py loads .env, so without DEMO_MODE a developer's real OPENAI_API_KEY would make
the suite billable, slow and non-deterministic. It is set before app.settings is first
imported - its Settings dataclass reads the environment once, when its class body executes.
"""

from __future__ import annotations

import os
import re

os.environ["DEMO_MODE"] = "1"

from fastapi.testclient import TestClient

_SESSION_PATH = re.compile(r"/agent/session/(?P<session_id>[^/?]+)")


class SessionAwareClient(TestClient):
    """A TestClient that holds each session's token, the way a browser does.

    Every session-scoped endpoint requires X-Session-Token. Rather than thread that header
    through every call in the suite, this learns the token minted by POST /agent/session and
    attaches the matching one per request - so tests exercise the real authenticated path
    without each assertion having to restate it. A test that wants to prove isolation still
    can: pass an explicit X-Session-Token and it wins over the remembered one.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.session_tokens: dict[str, str] = {}
        self.consumer_token: str | None = None

    @staticmethod
    def _session_id_for(url: str, kwargs: dict) -> str | None:
        body = kwargs.get("json")
        if isinstance(body, dict) and isinstance(body.get("session_id"), str):
            return body["session_id"]
        params = kwargs.get("params")
        if isinstance(params, dict) and isinstance(params.get("session_id"), str):
            return params["session_id"]
        text = str(url)
        query = re.search(r"[?&]session_id=([^&]+)", text)
        if query:
            return query.group(1)
        path = _SESSION_PATH.search(text)
        return path.group("session_id") if path else None

    def request(self, method: str, url, **kwargs):  # type: ignore[override]
        headers = dict(kwargs.get("headers") or {})
        session_id = self._session_id_for(url, kwargs)
        if session_id and session_id in self.session_tokens:
            headers.setdefault("X-Session-Token", self.session_tokens[session_id])
        if self.consumer_token:
            headers.setdefault("Authorization", f"Bearer {self.consumer_token}")
        kwargs["headers"] = headers

        response = super().request(method, url, **kwargs)

        if str(url).endswith("/agent/session") and response.status_code == 200:
            payload = response.json()
            if "session_token" in payload:
                self.session_tokens[payload["session_id"]] = payload["session_token"]
        return response
