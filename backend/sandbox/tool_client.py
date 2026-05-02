"""ToolClient — pre-baked bridge client for the LexCore sandbox container.

Phase 14 / BRIDGE-01 (D-P14-08).

Reads BRIDGE_URL and BRIDGE_TOKEN from environment at call time (not import
time) so the module can be imported in tests without env vars set.

Uses only stdlib: urllib.request, urllib.error, json, os.
No third-party dependencies — the sandbox image is kept minimal.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ToolClient:
    """HTTP client for calling platform tools through the sandbox bridge."""

    def call(self, tool_name: str, **kwargs: Any) -> dict:
        """Call a platform tool through the bridge endpoint.

        Args:
            tool_name: Registered tool name (e.g. 'search_documents').
            **kwargs: Tool arguments (passed as JSON body 'arguments' field).

        Returns:
            Tool result as a dict on success.
            {'error': 'bridge_error', 'message': '...'} on any failure.
            Exceptions are NEVER raised — always returns a dict (BRIDGE-07).
        """
        bridge_url = os.environ.get("BRIDGE_URL", "")
        bridge_token = os.environ.get("BRIDGE_TOKEN", "")
        timeout = int(os.environ.get("BRIDGE_TIMEOUT", "30"))

        if not bridge_url:
            return {"error": "bridge_error", "message": "BRIDGE_URL not set"}

        payload = json.dumps({
            "tool_name": tool_name,
            "arguments": kwargs,
            "session_token": bridge_token,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{bridge_url}/bridge/call",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                detail = json.loads(body)
            except Exception:
                detail = {"detail": str(exc)}
            return {"error": "bridge_error", "message": str(exc), "detail": detail}
        except Exception as exc:
            return {"error": "bridge_error", "message": str(exc)}
