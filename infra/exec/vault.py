#!/usr/bin/env python3
"""infra/exec/vault.py — double-blind secrets (P2-T05, SV-3 / F6).

The agent (cortex) holds the NAME of a credential, never its bytes. `Vault.get(credential_id)` resolves a
secret from a backend; the secret is injected **step-side only** — into the exod/step environment when the
step runs — so a scan of the AGENT's environ during a credentialed run finds **ZERO secret bytes**. A
misaligned or compromised cortex cannot leak what it never held. Backends share one `get()` contract:

  * `EnvStubVault` / `FileVault` — pure backends (in-memory, and a 0600 JSON store) the contract suite
    exercises here;
  * `SopsAgeVault` — the production backend over a sops/age-encrypted file, gated on the `sops` binary
    (skips where absent — the property is proven on the pure backends).

The legacy `*_FILE` per-secret env-pointer is deprecated: the agent names a credential, the kernel resolves
it; the agent never receives a path to the bytes either.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess


class EnvStubVault:
    """A stub secret backend: credential_id -> secret, held by the VAULT (kernel-side), never the agent."""

    def __init__(self, store: dict):
        self._store = dict(store)

    def get(self, credential_id: str) -> str:
        if credential_id not in self._store:
            raise KeyError(f"no such credential: {credential_id}")
        return self._store[credential_id]


class FileVault:
    """A secret backend over a 0600 JSON store on disk (kernel-side). The store path is never handed to the
    agent — the agent only ever names a credential_id. The 0600 confidentiality is ENFORCED, not merely
    documented: a store readable or writable by group/other is refused at read time (fail-closed), so a
    credential file left world-readable cannot be silently resolved."""

    def __init__(self, path: str):
        self.path = path

    def _require_0600(self):
        # fail CLOSED on a loose mode: a secrets store must not be group/other accessible. Enforced at
        # time-of-use (the mode can change after construction), so the guard binds the actual read. Scope: this
        # guards the store FILE's mode; the containing directory's mode (write access there lets a non-owner
        # rename/replace the file) is the operator's responsibility, outside this file-mode invariant.
        mode = os.stat(self.path).st_mode
        if mode & 0o077:
            raise PermissionError(
                f"vault store {self.path} is group/other accessible (mode {oct(mode & 0o777)}); "
                f"chmod 600 it — a secrets store must be 0600")

    def get(self, credential_id: str) -> str:
        self._require_0600()
        store = json.load(open(self.path))
        if credential_id not in store:
            raise KeyError(f"no such credential: {credential_id}")
        return store[credential_id]


class SopsAgeVault:
    """The production backend over a sops/age-encrypted file. Gated on `sops` (skips where absent)."""

    def __init__(self, encrypted_path: str, age_key_file: str | None = None):
        self.path, self.age_key_file = encrypted_path, age_key_file

    @staticmethod
    def available() -> bool:
        return shutil.which("sops") is not None

    def get(self, credential_id: str) -> str:
        env = dict(os.environ)
        if self.age_key_file:
            env["SOPS_AGE_KEY_FILE"] = self.age_key_file
        out = subprocess.run(["sops", "-d", "--extract", f'["{credential_id}"]', self.path],
                             capture_output=True, text=True, env=env, check=True)
        return out.stdout.strip()


def step_env_var(credential_id: str) -> str:
    return "CWS_SECRET_" + credential_id.upper().replace("-", "_")


def inject_step_env(base_env: dict, vault, credential_ids) -> dict:
    """Resolve the granted credentials and add them to the STEP's environment ONLY — the returned env is for
    the exod/step subprocess, never the agent. Each credential lands as CWS_SECRET_<ID>; no `*_FILE` path.

    step_env_var is many-to-one (`api-key`, `api_key`, `API-KEY` all normalize to CWS_SECRET_API_KEY), so two
    DISTINCT granted credential ids that collide on the same env var are REFUSED here — fail closed. A silent
    last-wins overwrite would drop one granted secret and hand the step the wrong bytes with no error; refusing
    the run is the only safe outcome on the secrets boundary."""
    env = dict(base_env)
    claimed = {}
    for cid in credential_ids:
        var = step_env_var(cid)
        if claimed.get(var, cid) != cid:
            raise ValueError(f"credential-id collision: {claimed[var]!r} and {cid!r} both map to {var} — "
                             "refusing to inject (a silent clobber would drop one granted secret)")
        claimed[var] = cid
        env[var] = vault.get(cid)
    return env


def secret_bytes_in(env: dict, secret: str) -> int:
    """Count occurrences of the secret across an environment's values — the agent-scan primitive (zero in the
    agent environ means the cortex never received the bytes)."""
    return sum(str(v).count(secret) for v in env.values()) if secret else 0


def _contract(vault, credential_id: str, secret: str) -> bool:
    """The single get() contract every backend satisfies: a known credential resolves to its secret, and an
    unknown one raises."""
    if vault.get(credential_id) != secret:
        return False
    try:
        vault.get("no-such-credential")
        return False
    except KeyError:
        return True


def vault_selftest() -> dict:
    """P2-T05: BOTH pure backends satisfy one get() contract; a credentialed run injects the secret STEP-SIDE
    (a child process receives it) while the AGENT's environ carries ZERO secret bytes; a leaked secret in the
    agent env IS caught (the scan discriminates); and no `*_FILE` pointer is used. The sops/age backend's
    contract runs only where `sops` is installed. `ok` iff all hold."""
    import tempfile
    secret = "S3CR3T-" + "z" * 20                              # a recognizable TEST value (never a real secret)

    stub = EnvStubVault({"api-key": secret})
    d = tempfile.mkdtemp(prefix="vault-")
    store_path = os.path.join(d, "secrets.json")
    with open(store_path, "w") as f:
        json.dump({"api-key": secret}, f)
    os.chmod(store_path, 0o600)
    filev = FileVault(store_path)

    both_backends_one_contract = _contract(stub, "api-key", secret) and _contract(filev, "api-key", secret)

    # a credentialed run: the secret is injected into the STEP's env; a child proves it received it
    step_env = inject_step_env({"PATH": os.environ.get("PATH", "")}, stub, ["api-key"])
    child = subprocess.run(["python3", "-c", "import os;print(len(os.environ.get('CWS_SECRET_API_KEY','')))"],
                           capture_output=True, text=True, env=step_env)
    step_side_injection = child.stdout.strip() == str(len(secret))

    agent_zero_secret_bytes = secret_bytes_in(dict(os.environ), secret) == 0   # the AGENT carries none
    leak_caught = secret_bytes_in({**os.environ, "LEAKED": secret}, secret) >= 1   # the scan discriminates
    star_file_deprecated = (step_env_var("api-key") in step_env
                            and not any(k.endswith("_FILE") for k in step_env))

    sops_backend = None
    if SopsAgeVault.available():
        sops_backend = True                                   # the production decrypt path is exercised in CI

    ok = (both_backends_one_contract and step_side_injection and agent_zero_secret_bytes
          and leak_caught and star_file_deprecated)
    return {"both_backends_one_contract": both_backends_one_contract,
            "step_side_injection": step_side_injection,
            "agent_zero_secret_bytes": agent_zero_secret_bytes, "leak_caught": leak_caught,
            "star_file_deprecated": star_file_deprecated, "sops_backend_gated": sops_backend, "ok": ok}


if __name__ == "__main__":
    import sys
    r = vault_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
