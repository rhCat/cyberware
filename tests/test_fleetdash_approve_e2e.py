#!/usr/bin/env python3
"""End-to-end browser test for the fleetdash approve button (real Chromium, real JS, real HTTP).

The unit tests around `render_risk` prove the button is *rendered* under the right conditions; they cannot
prove the integrated path works, because the interesting behaviour lives in the browser: the confirm()
gate, the custom CSRF header the fetch must set, and the claim govd actually receives. Tonight's recurring
failure mode was exactly this — something reporting success while achieving nothing — so this drives the
whole loop and asserts on what the SERVER received, not on what the page says.

Hermetic: a stub govd stands in for the node (records the claim it is handed) and the ledger mirror is a
fixture on disk. Nothing here touches the live fleet.

    pip install playwright pytest && playwright install chromium
    pytest tests/test_fleetdash_approve_e2e.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

pytest.importorskip("playwright", reason="pip install playwright && playwright install chromium")
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = "test-node"
RUN_PUSHBACK = "aa11bb22cc33dd44"
RUN_ALLOW = "ee55ff66aa77bb88"
APPROVE_TOKEN = "operator-secret-token"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _StubGovd(BaseHTTPRequestHandler):
    """Minimal node: enough /monitor/state for the mirror sweep, and a /govern that records the claim."""
    received: list = []

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/monitor/state"):
            return self._json(200, {"decisions": [], "decisions_page": {"pages": 1},
                                    "now": "2026-07-25T00:00:00Z"})
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True, "mode": "remote", "exec_mode": "delegated"})
        return self._json(404, {"error": "nope"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        type(self).received.append({"path": self.path, "body": body,
                                    "auth": self.headers.get("Authorization")})
        # what govd answers to a claim carrying the approve token
        return self._json(200, {"decision": "allow", "run_id": "newly1234allowed",
                                "plan_sha": "p" * 64, "approved": body.get("approve") or []})


@pytest.fixture()
def stub_govd():
    _StubGovd.received = []
    port = _free_port()
    srv = HTTPServer(("127.0.0.1", port), _StubGovd)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}", _StubGovd
    srv.shutdown()


def _mirror(tmp_path, node_url):
    """A ledger mirror fixture: one push_back awaiting approval, and one allow that must be refused."""
    base = tmp_path / "mirror" / NODE
    (base / "runs").mkdir(parents=True)
    pushback = {"run_id": RUN_PUSHBACK, "ts": "2026-07-25T19:34:43Z", "principal": "agent-1",
                "skill": "hermes:toolgate", "perk": "exec", "decision": "push_back", "destructive": True,
                "needs_approve": ["exec"], "approved": [],
                "var_keys": ["TOOL", "ARGS_DIGEST", "TARGET"], "_node": NODE}
    # An ALREADY-APPROVED run — the realistic `superseded` shape. It deliberately still carries
    # needs_approve, so the push_back guard is the ONLY thing that can refuse it: with an empty
    # needs_approve the later "no approve tokens" check would refuse it anyway and the test would pass
    # for the wrong reason (verified by mutation — dropping the guard did not fail the suite).
    allow = {"run_id": RUN_ALLOW, "ts": "2026-07-25T19:30:00Z", "principal": "agent-1",
             # a DIFFERENT perk from the push_back: same tuple would make mark_superseded hide the
             # push_back's button (a later approved run answered that claim), which is correct behaviour
             # but would silently gut the happy-path test.
             "skill": "hermes:toolgate", "perk": "write", "decision": "allow", "destructive": True,
             "needs_approve": ["write"], "approved": ["write"],
             "var_keys": ["TOOL", "ARGS_DIGEST", "TARGET"], "_node": NODE}
    for r in (pushback, allow):
        (base / "runs" / f"{r['run_id']}.json").write_text(json.dumps(r))
    (base / "index.json").write_text(json.dumps({RUN_PUSHBACK: pushback, RUN_ALLOW: allow}))
    return str(tmp_path / "mirror")


def _fleetdash(tmp_path, node_url, mirror_dir, *, with_approver):
    """Start a real fleetdash on a free loopback port. `with_approver` decides whether this node has an
    operator credential at all — the whole point of the gate."""
    node = {"name": NODE, "role": "body", "url": node_url}
    if with_approver:
        tok = tmp_path / "approve.token"
        tok.write_text(APPROVE_TOKEN)
        node["approve_token_file"] = str(tok)
    cfg = tmp_path / "fleet.json"
    cfg.write_text(json.dumps({"nodes": [node]}))
    port = _free_port()
    p = subprocess.Popen(
        [sys.executable, "-m", "infra.tool.fleetdash", "--config", str(cfg), "--serve", str(port),
         "--bind", "127.0.0.1", "--mirror-dir", mirror_dir, "--mirror-interval", "3600"],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": REPO})
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):                                   # wait for bind
        try:
            import urllib.request
            urllib.request.urlopen(url + "/risk", timeout=1).read()
            break
        except Exception:
            time.sleep(0.1)
    else:
        p.kill()
        pytest.fail("fleetdash did not start: " + (p.stdout.read().decode()[-2000:] if p.stdout else ""))
    return p, url


@pytest.fixture()
def page_ctx():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        yield browser
        browser.close()


def test_no_button_without_operator_credential(tmp_path, stub_govd, page_ctx):
    """A node with no approve credential must expose NO affordance — the read-only posture is the default."""
    node_url, _stub = stub_govd
    proc, url = _fleetdash(tmp_path, node_url, _mirror(tmp_path, node_url), with_approver=False)
    try:
        page = page_ctx.new_page()
        page.goto(url + "/risk")
        assert page.locator("button.approve").count() == 0
        assert "exec" in page.content()                    # the row IS there — only the button is withheld
    finally:
        proc.kill()


def test_credential_gate_is_enforced_SERVER_side(tmp_path, stub_govd, page_ctx):
    """Withholding the BUTTON is cosmetic — the route itself must refuse a node with no operator credential.

    Found by mutation: deleting the server-side `if not tok` check left the whole suite green, because the
    only coverage was "the button is not rendered". Anyone can POST /approve directly, so the UI gate proves
    nothing. This asserts the route refuses and that nothing reaches the node.
    """
    node_url, stub = stub_govd
    proc, url = _fleetdash(tmp_path, node_url, _mirror(tmp_path, node_url), with_approver=False)
    try:
        page = page_ctx.new_page()
        page.goto(url + "/risk")
        status = page.evaluate(
            """async ([node, run]) => {
                 const r = await fetch('/approve', {method:'POST',
                   headers:{'Content-Type':'application/json','X-Fleetdash-Approve':'1'},
                   body: JSON.stringify({node, run_id: run})});
                 return r.status;
               }""", [NODE, RUN_PUSHBACK])
        assert status == 403, "a node with no approve credential must refuse the route, not just hide the button"
        assert stub.received == [], "no credential must mean no claim reaches the node"
    finally:
        proc.kill()


def test_approve_end_to_end(tmp_path, stub_govd, page_ctx):
    """Click approve in a real browser and assert on what the NODE received — not on what the page claims."""
    node_url, stub = stub_govd
    proc, url = _fleetdash(tmp_path, node_url, _mirror(tmp_path, node_url), with_approver=True)
    try:
        page = page_ctx.new_page()
        page.goto(url + "/risk")

        btn = page.locator(f'button.approve[data-run="{RUN_PUSHBACK}"]')
        assert btn.count() == 1, "approve button missing for the push_back run"

        # the confirm() gate is part of the guard — a click must not proceed without it
        page.on("dialog", lambda d: d.accept())
        btn.click()
        page.wait_for_function(
            "() => !document.querySelector('button.approve[data-run=\"%s\"]')"
            " || document.querySelector('button.approve[data-run=\"%s\"]').textContent.trim() === 'approved'"
            % (RUN_PUSHBACK, RUN_PUSHBACK), timeout=8000)

        # THE assertion that matters: what did the node actually get?
        assert len(stub.received) == 1, f"expected exactly one claim, got {stub.received}"
        got = stub.received[0]
        assert got["path"] == "/govern"
        assert got["auth"] == f"Bearer {APPROVE_TOKEN}", "must use the OPERATOR credential, not a monitor token"
        assert got["body"]["approve"] == ["exec"]
        # the claim is REPLAYED from the mirrored record — the UI cannot widen it
        assert got["body"]["skill"] == "hermes:toolgate"
        assert got["body"]["perk"] == "exec"
        assert got["body"]["var_keys"] == ["TOOL", "ARGS_DIGEST", "TARGET"]
    finally:
        proc.kill()


def test_csrf_header_required(tmp_path, stub_govd, page_ctx):
    """A cross-origin page cannot set X-Fleetdash-Approve without a preflight we never answer. Simulate the
    drive-by: POST from the browser WITHOUT the header must be refused, and must not reach the node."""
    node_url, stub = stub_govd
    proc, url = _fleetdash(tmp_path, node_url, _mirror(tmp_path, node_url), with_approver=True)
    try:
        page = page_ctx.new_page()
        page.goto(url + "/risk")
        status = page.evaluate(
            """async ([node, run]) => {
                 const r = await fetch('/approve', {method:'POST',
                   headers:{'Content-Type':'application/json'},
                   body: JSON.stringify({node, run_id: run})});
                 return r.status;
               }""", [NODE, RUN_PUSHBACK])
        assert status == 403
        assert stub.received == [], "a header-less POST must never reach the node"
    finally:
        proc.kill()


def test_cannot_approve_a_non_pushback(tmp_path, stub_govd, page_ctx):
    """Approving an already-allowed run is refused — never approve something that was not pushed back."""
    node_url, stub = stub_govd
    proc, url = _fleetdash(tmp_path, node_url, _mirror(tmp_path, node_url), with_approver=True)
    try:
        page = page_ctx.new_page()
        page.goto(url + "/risk")
        status = page.evaluate(
            """async ([node, run]) => {
                 const r = await fetch('/approve', {method:'POST',
                   headers:{'Content-Type':'application/json','X-Fleetdash-Approve':'1'},
                   body: JSON.stringify({node, run_id: run})});
                 return r.status;
               }""", [NODE, RUN_ALLOW])
        assert status == 409
        assert stub.received == []
    finally:
        proc.kill()


def test_path_traversal_run_id_refused(tmp_path, stub_govd, page_ctx):
    """run_id is matched against ^[0-9a-f]{6,64}$ before it ever reaches a filesystem join."""
    node_url, stub = stub_govd
    proc, url = _fleetdash(tmp_path, node_url, _mirror(tmp_path, node_url), with_approver=True)
    try:
        page = page_ctx.new_page()
        page.goto(url + "/risk")
        status = page.evaluate(
            """async (node) => {
                 const r = await fetch('/approve', {method:'POST',
                   headers:{'Content-Type':'application/json','X-Fleetdash-Approve':'1'},
                   body: JSON.stringify({node, run_id: '../../etc/passwd'})});
                 return r.status;
               }""", NODE)
        assert status == 400
        assert stub.received == []
    finally:
        proc.kill()
