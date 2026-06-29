#!/usr/bin/env python3
"""compose.py — compose MULTIPLE source chips into ONE composed chip that govd can serve.

Each source is itself a self-describing, AUTHENTIC chip — internally namespaced by source-group dir
(`<src>/<ns>/<skill>`) or flat. compose merges every source's skills into `<out>`, each placed by NAMESPACE
(`<out>/<ns>/<skill>`), then re-pins the composed v2 manifest. Two sources owning the SAME `<ns>:<name>` is
an EXACT DUPLICATE — a HARD ERROR demanding manual reconciliation (never first-source-wins). Two skills that
share a LEAF across DIFFERENT namespaces coexist (that is the whole point of namespacing). Idempotent:
composing the same sources twice yields a byte-identical chip (skill_sha is content-only; the roll-up is keyed
on the ns:name set, so source order does not matter).

A source is a path, optionally carrying a namespace:
  * namespace OMITTED  — the source's OWN internal source-groups are preserved (`general:fs` stays `general:fs`).
  * namespace GIVEN    — EVERY skill of that source is re-homed under it (`magnumopus:<leaf>`); use for a flat
                         source, or to place a product chip (skillchipMO) under its own namespace.

  python3 -m infra.tool.compose --out <dir> --source <pathA> --source <pathB>:<namespace> ...
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
import unicodedata

from infra import registry
from infra.tool import skill_index


class ComposeConflict(Exception):
    """Two sources declare the SAME composed id — or two ids that COLLIDE on a case-insensitive / Unicode-
    normalizing filesystem (macOS, many CI volumes), landing on the same directory. Manual reconciliation
    required; the engine never silently picks one. `.conflicts` maps the fs-fold key to the [(id, source
    label), ...] that collide on it."""

    def __init__(self, conflicts):
        self.conflicts = conflicts
        body = "\n".join("  " + " AND ".join(f"{tid} (from {lbl})" for tid, lbl in sorted(conflicts[k]))
                         for k in sorted(conflicts))
        super().__init__("colliding skill ids across sources — manual reconciliation required:\n" + body)


def _fold(tid):
    """The filesystem-equivalence key for a composed id (NFC + casefold), so two ids differing only by case or
    Unicode form — which collide on a case-insensitive / normalizing FS — are detected as ONE destination, not
    silently treated as two skills (then crashing mid-copy)."""
    return unicodedata.normalize("NFC", tid).casefold()


def _norm(sources):
    """Normalize a sources list — each entry a path string (optionally `path:namespace`) or a {path,namespace}
    dict — into {path, namespace|None, label}."""
    out = []
    for s in sources:
        if isinstance(s, str):
            path, ns = (s.rsplit(":", 1) + [None])[:2] if (":" in s and not os.path.exists(s)) else (s, None)
            out.append({"path": path, "namespace": ns})
        else:
            out.append({"path": s["path"], "namespace": s.get("namespace")})
    for spec in out:
        spec["label"] = (f"{spec['path']}:{spec['namespace']}" if spec["namespace"] else spec["path"])
    return out


def _target_id(scanned_id, namespace):
    """The COMPOSED id for a source skill: re-homed under `namespace` (keeping its leaf), or its own scanned
    ns:name. Returns None for a flat source skill with no namespace (ambiguous to compose — caller raises)."""
    ns, name = registry.parse_skill_id(scanned_id)
    if namespace is not None:
        return f"{namespace}:{name}"
    if ns is None:
        return None
    return f"{ns}:{name}"


def plan(sources):
    """Resolve every source skill to its composed id and DETECT exact-dup conflicts BEFORE any write. Returns
    (placements, conflicts): placements = [(target_id, src_skill_dir, source_label)]; conflicts =
    {target_id: [source_label, ...]} for any id ≥2 sources claim."""
    sources = _norm(sources)
    placements, owners, flat = [], {}, []
    for spec in sources:
        for sid in skill_index.scan_skills(spec["path"]):
            tid = _target_id(sid, spec["namespace"])
            if tid is None:
                flat.append((spec["label"], sid))
                continue
            placements.append((tid, registry.skill_dir(sid, spec["path"]), spec["label"]))
            owners.setdefault(_fold(tid), []).append((tid, spec["label"]))    # key on the FS-fold, not the raw id
    if flat:
        raise ValueError("flat source skill(s) need an explicit namespace to compose (use path:namespace): "
                         + ", ".join(f"{lbl}/{sid}" for lbl, sid in flat))
    conflicts = {fk: entries for fk, entries in owners.items() if len(entries) > 1}
    return placements, conflicts


def _full_verify(chip):
    """(ok, detail): the chip's manifest matches its skill set AND every skill's FILES match its per-skill
    index. verify_chip alone is insufficient — it rolls up the per-skill index.json `skill_sha` (the pinned
    value), so a file tamper that leaves the index untouched slips past it; the per-skill verify recomputes
    the sha from files and catches it (the cartridge-seal lesson)."""
    ok, detail = skill_index.verify_chip(chip)
    if not ok:
        return False, detail
    for sid in skill_index.scan_skills(chip):
        vok, drift = skill_index.verify(sid, chip)
        if not vok:
            return False, f"{sid}: files do not match its index ({str(drift)[:60]})"
    return True, "authentic"


def compose(sources, out_dir, *, validate_sources=True):
    """Compose `sources` into `out_dir`. Raises ComposeConflict on an exact ns:name dup (out_dir untouched),
    ValueError on an unauthentic or flat-unnamespaced source. Returns {chip_sha, count, skills, sources}."""
    specs = _norm(sources)
    if validate_sources:
        for spec in specs:
            ok, detail = _full_verify(spec["path"])
            if not ok:
                raise ValueError(f"refusing to compose an unauthentic source {spec['label']}: {detail}")
    placements, conflicts = plan(sources)
    if conflicts:
        raise ComposeConflict(conflicts)                      # HARD ERROR — before any write

    # Build into a SIBLING temp dir and swap on success, so out_dir is left UNTOUCHED on ANY failure (a copy
    # error, an fs collision plan() could not foresee, a failed authenticity check) — not only a detected dup.
    tmp = out_dir.rstrip("/\\") + ".composing"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        os.makedirs(tmp)
        for tid, src_dir, _ in placements:
            dst = registry.compiled_skill_dst(tid, tmp)       # structural write-path: <tmp>/<ns>/<name>
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst):                           # belt: a residual fs-fold collision -> hard error
                raise ComposeConflict({_fold(tid): [(tid, "source"), (tid, "filesystem-colliding sibling")]})
            shutil.copytree(src_dir, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
        manifest = skill_index.write_manifest(tmp)            # re-pin the composed v2 manifest
        ok, detail = _full_verify(tmp)
        if not ok:
            raise ValueError(f"composed chip failed its own authenticity check: {detail}")
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)                # out_dir untouched; nothing partial survives
        raise
    if os.path.exists(out_dir):                               # swap in the finished chip (idempotent re-register)
        shutil.rmtree(out_dir)
    os.rename(tmp, out_dir)
    return {"chip_sha": manifest["chip_sha"], "count": manifest["count"],
            "skills": [e["skill"] for e in manifest["skills"]],
            "sources": [s["label"] for s in specs]}


def main():
    ap = argparse.ArgumentParser(description="compose multiple source chips into one composed chip")
    ap.add_argument("--out", required=True, help="the composed chip dir to (re)write")
    ap.add_argument("--source", action="append", default=[], metavar="PATH[:NAMESPACE]",
                    help="a source chip dir; append :NAMESPACE to re-home all its skills under that namespace")
    ap.add_argument("--no-validate-sources", action="store_true", help="skip the per-source authenticity gate")
    a = ap.parse_args()
    if not a.source:
        ap.error("at least one --source is required")
    try:
        r = compose(a.source, a.out, validate_sources=not a.no_validate_sources)
    except ComposeConflict as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)                                           # distinct code: manual reconciliation required
    except (ValueError, OSError) as e:                        # unauthentic/flat source, or any filesystem error
        print(f"compose error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
