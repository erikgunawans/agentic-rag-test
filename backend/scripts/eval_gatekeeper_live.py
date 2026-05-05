"""Phase 22 / D-22-04 -- Live-LLM gatekeeper trigger check (manual run).

Runs gatekeeper_eval_set.json against the REAL LLM (not mocked). Use to verify
the system prompt structure works with gpt-4o-mini for actual intent matching.
Cost: ~15 cheap LLM calls (~$0.01 total per run).

Usage:
  python -m scripts.eval_gatekeeper_live --base-url https://api-production-cde1.up.railway.app --token <jwt>

Security note (T-22-05-01): --token is passed via argv and is NEVER echoed
to stdout/stderr or included in any log output from this script.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import uuid
from typing import Any

import httpx

EVAL_SET_PATH = pathlib.Path(__file__).parents[1] / "tests" / "data" / "gatekeeper_eval_set.json"

# Minimal synthetic binary stubs.
# The eval set's size_bytes values are used only in the LLM prompt; the actual
# upload bytes don't need to match those sizes.
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MIME = "application/pdf"

# Minimal DOCX stub: ZIP PK magic header (not a real DOCX, but sufficient for upload)
_SYNTH_DOCX_BYTES = b"PK\x03\x04" + b"\x00" * 196

# Minimal PDF stub: single-page PDF
_SYNTH_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
)


# ---------------------------------------------------------------------------
# TTY color helpers
# ---------------------------------------------------------------------------

def _is_tty() -> bool:
    return sys.stdout.isatty()


def _green(s: str) -> str:
    return f"\033[92m{s}\033[0m" if _is_tty() else s


def _red(s: str) -> str:
    return f"\033[91m{s}\033[0m" if _is_tty() else s


def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m" if _is_tty() else s


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def create_thread(client: httpx.AsyncClient, base_url: str, headers: dict) -> str:
    """Create a fresh thread and return its id."""
    resp = await client.post(
        f"{base_url}/threads",
        json={"title": f"gk-check-{uuid.uuid4().hex[:8]}"},
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()["id"]


async def upload_workspace_file(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    thread_id: str,
    file_path: str,
    mime_type: str,
) -> None:
    """Upload a synthetic file to the workspace for the given thread."""
    content = _SYNTH_DOCX_BYTES if mime_type == _DOCX_MIME else _SYNTH_PDF_BYTES
    filename = pathlib.Path(file_path).name
    files = {"file": (filename, content, mime_type)}
    # Exclude Content-Type so httpx sets multipart boundary automatically
    upload_headers = {k: v for k, v in headers.items() if k != "Content-Type"}
    resp = await client.post(
        f"{base_url}/threads/{thread_id}/files/upload",
        files=files,
        headers=upload_headers,
    )
    resp.raise_for_status()


async def send_message_get_gatekeeper(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    thread_id: str,
    message: str,
) -> dict[str, Any]:
    """Send a chat message via SSE and return the gatekeeper_complete event payload.

    Returns dict with keys: triggered (bool | None).
    triggered=None means no gatekeeper_complete event appeared (unexpected).
    """
    payload = {"message": message, "thread_id": thread_id}
    result: dict[str, Any] = {"triggered": None}

    async with client.stream(
        "POST",
        f"{base_url}/chat",
        json=payload,
        headers=headers,
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "gatekeeper_complete":
                result["triggered"] = event.get("triggered")
                break

    return result


# ---------------------------------------------------------------------------
# Main check loop
# ---------------------------------------------------------------------------

async def check_all_phrasings(
    base_url: str,
    token: str,
    limit: int,
    phrasings: list[dict],
) -> tuple[list[dict], list[str]]:
    """Check up to `limit` phrasings against the live API.

    Returns (results, fail_ids).
    """
    # NOTE: token is NEVER logged (T-22-05-01)
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    results: list[dict] = []
    fail_ids: list[str] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        for phrasing in phrasings[:limit]:
            pid = phrasing["id"]
            print(f"  [{pid}] {phrasing['text'][:60]!r} ...", end=" ", flush=True)

            try:
                # 1. Fresh thread per phrasing (no cross-phrasing contamination)
                thread_id = await create_thread(client, base_url, auth_headers)

                # 2. Upload workspace files if any
                for ws_file in phrasing.get("workspace", []):
                    await upload_workspace_file(
                        client,
                        base_url,
                        auth_headers,
                        thread_id,
                        ws_file["file_path"],
                        ws_file.get("mime_type", _PDF_MIME),
                    )

                # 3. Send message and collect gatekeeper event
                check_result = await send_message_get_gatekeeper(
                    client, base_url, auth_headers, thread_id, phrasing["text"]
                )
                actual = check_result.get("triggered")

                if actual is None:
                    print(_red("[NO_GATEKEEPER_EVENT]"))
                    passed = False
                else:
                    expected = phrasing["expected_triggered"]
                    passed = actual == expected
                    marker = _green("[PASS]") if passed else _red("[FAIL]")
                    detail = f"expected={expected}, actual={actual}"
                    print(f"{marker} {detail}")

                results.append({
                    "id": pid,
                    "harness": phrasing["harness"],
                    "text": phrasing["text"],
                    "expected_triggered": phrasing["expected_triggered"],
                    "actual_triggered": actual,
                    "passed": passed,
                })
                if not passed:
                    fail_ids.append(pid)

            except Exception as exc:
                print(_red(f"[ERROR] {exc}"))
                results.append({
                    "id": pid,
                    "harness": phrasing["harness"],
                    "text": phrasing["text"],
                    "expected_triggered": phrasing["expected_triggered"],
                    "actual_triggered": None,
                    "passed": False,
                    "error": str(exc),
                })
                fail_ids.append(pid)

    return results, fail_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live-LLM gatekeeper trigger check against the real API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python -m scripts.eval_gatekeeper_live \\\n"
            "    --base-url https://api-production-cde1.up.railway.app \\\n"
            "    --token $JWT\n"
        ),
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--token",
        required=True,
        help="JWT access token",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max phrasings to check (default: all 15)",
    )
    args = parser.parse_args()

    if not EVAL_SET_PATH.exists():
        print(f"ERROR: eval set not found at {EVAL_SET_PATH}", file=sys.stderr)
        return 1

    eval_set = json.loads(EVAL_SET_PATH.read_text())
    phrasings = eval_set["phrasings"]
    limit = args.limit if args.limit is not None else len(phrasings)

    print(_bold(f"\nGatekeeper Live Check -- {limit}/{len(phrasings)} phrasings"))
    print(f"  Target: {args.base_url}")
    print(f"  Set: {EVAL_SET_PATH.name} v{eval_set.get('version', '?')}")
    print()

    results, fail_ids = asyncio.run(
        check_all_phrasings(args.base_url, args.token, limit, phrasings)
    )

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    pct = (passed / total * 100) if total else 0.0

    print()
    if fail_ids:
        fail_str = ", ".join(fail_ids)
        print(_bold(f"PASS: {passed}/{total} ({pct:.1f}%)  FAIL_IDS: {fail_str}"))
    else:
        print(_bold(_green(f"PASS: {passed}/{total} ({pct:.1f}%)  ALL PHRASINGS PASSED")))

    return 0 if not fail_ids else 1


if __name__ == "__main__":
    sys.exit(main())
