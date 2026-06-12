#!/usr/bin/env python3
"""chipfetch.py — acquire + VALIDATE the skillChip before govd serves it.

The engine never trusts a cartridge it hasn't checked. Two acquisition modes, ONE validation:

  * LOCAL (default)        — the chip baked into the image at build (`COPY skillChip/`, already gated
    by `skill_index --check` at build time). Re-validated at boot anyway: a mounted override or a
    corrupted layer must not serve.
  * CLOUD (`CLOUD_MODE=1`) — clone the chip LIVE at boot from `CLOUD_SOURCE` (default: the skillChip
    repo) at `CLOUD_SOURCE_TAG` (a branch, tag, or commit sha; default `main`). A private source
    authenticates with `CLOUD_SOURCE_TOKEN`. The clone lands at `CLOUD_CHIP_DIR` (default
    `~/.cyberware/skillChip-cloud`), fresh each boot.

Either way the resolved chip must pass the SAME authenticity gate — every skill's `index.json` plus the
chip-level manifest (`chip_sha`) — or this process exits non-zero and govd never starts. Provenance
(mode · source · ref · commit · chip_sha) is printed, and handed to govd via `GOVD_CHIP_PROVENANCE`
(surfaced at `/health`).

Token hygiene — the secret never persists, never leaks: the token is NEVER written into a URL. Auth goes
through a `GIT_ASKPASS` helper, so it lives only in the short-lived clone child's environment — never in
`.git/config`, the command line, an error message, the provenance, or govd's own environment. Inline
credentials in `CLOUD_SOURCE` are extracted and sanitised out of everything surfaced. A clone that fails
at any point leaves nothing on disk. Before exec'ing govd the boot-only `CLOUD_*` vars are dropped from
its environment, so the long-running server (and its TLC `java` children) never carry the secret.

  python3 -m infra.govern.chipfetch                          # resolve + validate, print provenance
  python3 -m infra.govern.chipfetch --exec CMD ARG...        # then exec CMD with CYBERWARE_SKILLCHIP set
"""
from __future__ import annotations
import argparse, json, os, shutil, stat, subprocess, sys, tempfile, urllib.parse

from infra import registry
from infra.tool import skill_index

DEFAULT_SOURCE = "https://github.com/rhCat/skillChip.git"
DEFAULT_TAG = "main"
BOOT_ONLY_ENV = ("CLOUD_MODE", "CLOUD_SOURCE", "CLOUD_SOURCE_TAG", "CLOUD_SOURCE_TOKEN", "CLOUD_CHIP_DIR")


def _truthy(v):
    return str(v or "").strip().lower() not in ("", "0", "false", "no", "off")


def _split_creds(url, token):
    """Pull any inline userinfo OUT of the URL (an operator may embed creds in CLOUD_SOURCE) and prefer an
    explicit token. Returns (clean_url, token) — the clean url is what we clone + surface; the token (if
    any) is fed to git only via GIT_ASKPASS, never re-embedded."""
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return url, token
    if p.username or p.password:
        token = token or p.password or p.username
        netloc = (p.hostname or "") + (f":{p.port}" if p.port else "")
        url = urllib.parse.urlunsplit((p.scheme, netloc, p.path, p.query, p.fragment))
    return url, token


def _sanitize(url):
    """A display-safe remote: strip any inline userinfo so it can never reach logs / provenance / health."""
    return _split_creds(url, None)[0]


def _askpass_env(token, base_env=None):
    """Auth git WITHOUT the token ever touching the URL / .git-config / cmdline / error text: a GIT_ASKPASS
    helper reads the token from the (clone-child-only) environment. Returns (env, helper_path) — the caller
    deletes the helper. GIT_TERMINAL_PROMPT=0 fails fast instead of hanging on a missing credential."""
    env = dict(base_env if base_env is not None else os.environ)
    fd, helper = tempfile.mkstemp(prefix="cw-askpass-")
    os.write(fd, b'#!/bin/sh\ncase "$1" in *[Uu]sername*) printf x-access-token;; *) printf "%s" "$GIT_TOKEN";; esac\n')
    os.close(fd)
    os.chmod(helper, stat.S_IRWXU)
    env.update(GIT_ASKPASS=helper, GIT_TOKEN=token, GIT_TERMINAL_PROMPT="0")
    return env, helper


def _git(args, cwd=None, env=None):
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def fetch_cloud(source, tag, token=None, dest=None):
    """Shallow-clone the chip at `tag` (branch/tag; full-clone + checkout fallback for a raw sha). Returns
    (chip_dir, provenance). The token is supplied only via GIT_ASKPASS, so it never lands on disk; a clone
    that fails at any point leaves nothing behind; only the sanitised source is recorded."""
    dest = dest or os.environ.get("CLOUD_CHIP_DIR") or os.path.expanduser("~/.cyberware/skillChip-cloud")
    clean, token = _split_creds(source, token)               # creds out of the URL; token (if any) -> askpass
    if os.path.exists(dest):
        shutil.rmtree(dest)                                  # fresh each boot — "live" means live
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    env, helper = _askpass_env(token) if token else (None, None)
    try:
        code, out = _git(["clone", "--depth", "1", "--branch", tag, clean, dest], env=env)
        if code != 0:                                        # a raw commit sha can't be --branch'ed
            shutil.rmtree(dest, ignore_errors=True)
            code2, out2 = _git(["clone", clean, dest], env=env)
            if code2 != 0:
                shutil.rmtree(dest, ignore_errors=True)
                sys.exit(f"chipfetch: clone failed from {clean}\n{out}\n{out2}")
            code3, out3 = _git(["checkout", "--quiet", tag], cwd=dest, env=env)
            if code3 != 0:
                shutil.rmtree(dest, ignore_errors=True)      # never leave a half-clone (or its config) on disk
                sys.exit(f"chipfetch: ref {tag!r} not found in {clean}\n{out3}")
        _, commit = _git(["rev-parse", "HEAD"], cwd=dest)
    finally:
        if helper:
            os.unlink(helper)
    return dest, {"mode": "cloud", "source": clean, "ref": tag, "commit": commit.strip()}


def resolve():
    """The chip dir + its provenance, per the acquisition mode (CLOUD_MODE env)."""
    if _truthy(os.environ.get("CLOUD_MODE")):
        source = os.environ.get("CLOUD_SOURCE") or DEFAULT_SOURCE
        tag = os.environ.get("CLOUD_SOURCE_TAG") or DEFAULT_TAG
        return fetch_cloud(source, tag, token=os.environ.get("CLOUD_SOURCE_TOKEN"))
    return registry.SKILLCHIP, {"mode": "local", "source": registry.SKILLCHIP}


def validate(chip):
    """The one gate both modes pass: every skill's index + the chip manifest. Returns a problem list."""
    if not os.path.isdir(chip):
        return [f"chip dir missing: {chip}"]
    skills = skill_index.all_skills(chip)
    if not skills:
        return [f"no skills on the chip at {chip} (nothing with a perks.json)"]
    problems = []
    for s in skills:
        ok, probs = skill_index.verify(s, chip)
        if not ok:
            problems.append(f"{s}: " + "; ".join(probs[:3]))
    cok, cdetail = skill_index.verify_chip(chip)
    if not cok:
        problems.append(f"chip manifest: {cdetail}")
    return problems


def chip_sha(chip):
    mp = os.path.join(chip, registry.CHIP_MANIFEST)
    return (json.load(open(mp)).get("chip_sha") if os.path.isfile(mp) else None)


def main():
    ap = argparse.ArgumentParser(description="acquire + validate the skillChip (local or CLOUD_MODE)")
    ap.add_argument("--exec", dest="exec_cmd", nargs=argparse.REMAINDER,
                    help="after validation, exec this command with CYBERWARE_SKILLCHIP + provenance set")
    a = ap.parse_args()

    chip, prov = resolve()
    problems = validate(chip)
    if problems:
        print(f"chipfetch: REFUSED — the chip at {chip} failed validation:", file=sys.stderr)
        for p in problems:
            print(f"  [DRIFT] {p}", file=sys.stderr)
        sys.exit(1)
    prov["chip_sha"] = chip_sha(chip)
    prov["skills"] = len(skill_index.all_skills(chip))
    src = prov["source"] if prov["mode"] == "local" else f"{prov['source']} @ {prov['ref']} ({prov['commit'][:12]})"
    print(f"chipfetch: chip VALID — {prov['skills']} skills · chip_sha {prov['chip_sha'][:16]} · {prov['mode']}: {src}")
    print(json.dumps(prov))

    if a.exec_cmd:
        env = dict(os.environ)
        for k in BOOT_ONLY_ENV:                              # the boot secret never enters govd (nor its TLC children)
            env.pop(k, None)
        env["CYBERWARE_SKILLCHIP"] = chip                    # the exec'd govd resolves the chip from HERE
        env["GOVD_CHIP_PROVENANCE"] = json.dumps(prov)       # surfaced at /health — sanitised, no secret
        os.execvpe(a.exec_cmd[0], a.exec_cmd, env)


if __name__ == "__main__":
    main()
