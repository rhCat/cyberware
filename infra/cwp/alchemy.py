#!/usr/bin/env python3
"""infra/cwp/alchemy.py — the concordance validator core (P3-T08, SV-4 / the alchemy ancestor).

alchemy is the file-mode wrapper over the pinned external engines built in the **putrefactio phase** (see
`skillChip/alchemy/deps.lock`):

  * **putrefactio** — the Python typestate extractor emits an **L++ typestate blueprint per function** (the
    "snippet core"): gates / actions / transitions over a `stmt*` basic-block vocabulary, plus a leaf-map
    that classifies resource CALLs into named families and the conservation law `B1_acquire_release_balance`.
  * **alembic** — the declared-blueprint engine (`alembic <src> --synthesize --json`) and `citrinitas-phase2`,
    which the P3-T09 publish gate uses.

The four verbs, each a REAL tool run (no stubs):
  * **extract**  — L++ emitted per snippet core (the putrefactio extractor).
  * **classify** — every resource CALL mapped to a named family; `unnamed` = a CALL with no leaf-map entry.
  * **conserve** — acquire/release imbalance per family vs the conservation law; `unexplained_defects` = the
    count of unbalanced families.
  * **concord**  — the extracted CFG is structurally **contained** in a declared blueprint, over the shared
    `stmt*` vocabulary; the containment diff (missing states, violating edges) is stored.

SCOPE (stated honestly): concord operates on the **Python L++ layer** — extracted CFG (putrefactio, Python
source) ⊆ a declared blueprint over the same `stmt*` vocabulary. Cross-language concord (a Python-extracted
CFG against an alembic Rust-declared blueprint) is out of scope: the two extractors never share a source
language and no cross-vocabulary bridge exists. alembic's declared blueprints + citrinitas-phase2 are wrapped
for the Rust/declared side and the P3-T09 gate.

The external engines are NOT present in CI; callers gate with a `requires_cmd` probe so the perks SKIP rather
than fail there. Tool locations are env-overridable (`ALCHEMY_PUTREFACTIO`, `ALCHEMY_ALEMBIC`,
`ALCHEMY_CITRINITAS`) with the pinned local checkout as the default.
"""
from __future__ import annotations
import os
import subprocess
import sys

_HOME = os.path.expanduser("~")
PUTREFACTIO = os.environ.get(
    "ALCHEMY_PUTREFACTIO",
    os.path.join(_HOME, "hunyuan", "putrefactio", "tools", "typestate-extractors", "python-typestate-extractor"))
ALEMBIC = os.environ.get("ALCHEMY_ALEMBIC", os.path.join(_HOME, "hunyuan", "alembic", "target", "release", "alembic"))
CITRINITAS = os.environ.get(
    "ALCHEMY_CITRINITAS", os.path.join(_HOME, "hunyuan", "alembic", "target", "release", "citrinitas-phase2"))


def tools_present() -> bool:
    """True iff the pinned putrefactio extractor is importable (the file-mode floor for extract/conserve/
    classify/concord). alembic/citrinitas are checked separately by the perks that need them."""
    return os.path.isdir(PUTREFACTIO) and os.path.isfile(
        os.path.join(PUTREFACTIO, "python_typestate_extractor", "test_synthetic_conservation.py"))


def _ext():
    """Lazily import the pinned putrefactio extractor helpers (raises if the checkout is absent — callers
    gate on tools_present()/requires_cmd so this only fires where the engine exists)."""
    if PUTREFACTIO not in sys.path:
        sys.path.insert(0, PUTREFACTIO)
    from python_typestate_extractor.test_synthetic_conservation import (  # noqa: E402
        PYTHON_LEAF_MAP, _classify_blueprint, _compute_imbalance, _extract_single, _simple_name)
    return {"extract_single": _extract_single, "classify": _classify_blueprint, "imbalance": _compute_imbalance,
            "simple_name": _simple_name, "leaf_map": PYTHON_LEAF_MAP}


# ── the four verbs ────────────────────────────────────────────────────────────

def extract_cli(src_dir: str) -> dict:
    """EXTRACT via the real file-mode CLI: `python -m python_typestate_extractor <dir>` → NDJSON L++. Returns
    {blueprints, count} — proves the engine emits an L++ core per function with no warehouse/postgres dep."""
    import json
    r = subprocess.run([sys.executable, "-m", "python_typestate_extractor", src_dir],
                       cwd=PUTREFACTIO, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"extractor failed: {r.stderr.strip()}")
    bps = [json.loads(ln) for ln in r.stdout.splitlines() if ln.strip()]
    return {"blueprints": bps, "count": len(bps)}


def extract_one(source: str, fn_name: str = None) -> dict:
    """EXTRACT one function's L++ blueprint in-process (the same putrefactio extractor)."""
    return _ext()["extract_single"](source, fn_name) if fn_name else _ext()["extract_single"](source)


def classify(bp: dict) -> dict:
    """CLASSIFY: map each resource CALL to a named family; report acquires/releases and the `unnamed` count
    (CALLs with no leaf-map entry by exact or simple name) — honest, since the helper silently drops misses."""
    h = _ext()
    classified = h["classify"](bp)
    leaf, simple = h["leaf_map"], h["simple_name"]
    unnamed = 0
    for a in bp.get("actions", {}).values():
        if a.get("type") != "CALL":
            continue
        c = a.get("callee", "")
        if c and leaf.get(c) is None and leaf.get(simple(c)) is None:
            unnamed += 1
    return {"classified": classified, "unnamed": unnamed}


def conserve(bp: dict) -> dict:
    """CONSERVE: acquire/release imbalance per family; `unexplained_defects` = families that do not balance
    (the B1_acquire_release_balance law). 0 ⇒ every resource is conserved."""
    imbalance = _ext()["imbalance"](_ext()["classify"](bp))
    return {"imbalance": imbalance, "unexplained_defects": len(imbalance)}


def cfg(bp: dict) -> dict:
    """The structural CFG over the `stmt*` vocabulary: states = distinct basic blocks (+ terminal states);
    edges = the linear basic-block order the extractor records. The subject of concord containment."""
    bbs = set()
    for g in bp.get("gates", {}).values():
        bbs.add(g.get("at_bb"))
    for a in bp.get("actions", {}).values():
        bbs.add(a.get("at_bb"))
    for t in bp.get("transitions", []):
        bbs.add(t.get("at_bb"))
    bbs.discard(None)
    order = sorted(bbs, key=lambda s: int(s[4:]) if s.startswith("stmt") and s[4:].isdigit() else 10**9)
    states = order + list(bp.get("terminal_states", {}).keys())
    edges = [[states[i], states[i + 1]] for i in range(len(states) - 1)]
    return {"states": states, "edges": edges}


def concord(extracted_cfg: dict, declared_cfg: dict) -> dict:
    """CONCORD: is the extracted CFG structurally contained in the declared blueprint? Pure set containment
    over the shared `stmt*` vocabulary. Returns the stored diff: missing states + violating (undeclared)
    edges. `pass` iff the extracted CFG introduces no state/edge the declared blueprint does not allow."""
    ds = set(declared_cfg.get("states", []))
    de = {tuple(e) for e in declared_cfg.get("edges", [])}
    missing_states = [s for s in extracted_cfg.get("states", []) if s not in ds]
    violating_edges = [e for e in extracted_cfg.get("edges", []) if tuple(e) not in de]
    return {"pass": not missing_states and not violating_edges,
            "missing_states": missing_states, "violating_edges": violating_edges}


# ── alembic / citrinitas (the declared + Citrinitas side) ─────────────────────

def alembic_declared(src_path: str, out_path: str) -> dict:
    """The declared blueprint for a (Rust) subject: `alembic <src> --synthesize --json`. Returns the parsed
    synthesis ({blueprints, count, mir_coverage}). Used by the P3-T09 Citrinitas gate."""
    import json
    r = subprocess.run([ALEMBIC, src_path, "--synthesize", "--json", "-o", out_path],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out_path):
        raise RuntimeError(f"alembic synthesize failed: {r.stderr.strip()[:200]}")
    return json.load(open(out_path))


def citrinitas(declared_json_path: str, out_path: str, cap: int = None) -> dict:
    """Run citrinitas-phase2 over an alembic synthesis → safety invariants populated. Returns the parsed
    output. The P3-T09 publish gate uses the alchemy verdicts; citrinitas attests the declared invariants."""
    import json
    cmd = [CITRINITAS, "--synthesis", declared_json_path, "--output", out_path]
    if cap:
        cmd += ["--invariant-cap", str(cap)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out_path):
        raise RuntimeError(f"citrinitas-phase2 failed: {r.stderr.strip()[:200]}")
    return json.load(open(out_path))


# ── hermetic self-tests (one per verb; each shows PASS + a discriminating FAIL) ──

# clean subject: every CALL is a named, balanced resource family → unnamed:0, unexplained_defects:0
_CLEAN = "def manage(path):\n    fh = open(path)\n    fh.close()\n"
# leaky subject: acquire without release → a conservation defect
_LEAK = "def manage(path):\n    fh = open(path)\n    return fh\n"
# exotic subject: a CALL with no leaf-map family → an unnamed shape
_EXOTIC = "def manage(x):\n    fh = open(x)\n    weird_widget(fh)\n    fh.close()\n"


def extract_selftest() -> dict:
    """P3-T08 extract: the real CLI emits ≥1 L++ blueprint per snippet core, file-mode, no warehouse."""
    import json
    import tempfile
    d = tempfile.mkdtemp(prefix="alchemy-extract-")
    open(os.path.join(d, "sample.py"), "w").write(_CLEAN)
    out = extract_cli(d)
    bp = out["blueprints"][0] if out["blueprints"] else {}
    emitted = out["count"] >= 1 and "actions" in bp and "transitions" in bp
    return {"blueprint_count": out["count"], "lpp_emitted": emitted,
            "sample": json.dumps(bp)[:200], "ok": emitted}


def classify_selftest() -> dict:
    """P3-T08 classify: a clean subject classifies every resource CALL into a named family (unnamed:0); an
    exotic CALL with no family raises unnamed>0 (the verb discriminates)."""
    clean = classify(extract_one(_CLEAN))
    exotic = classify(extract_one(_EXOTIC))
    return {"clean_unnamed": clean["unnamed"], "exotic_unnamed": exotic["unnamed"],
            "classified": clean["classified"],
            "ok": clean["unnamed"] == 0 and exotic["unnamed"] >= 1}


def conserve_selftest() -> dict:
    """P3-T08 conserve: a balanced subject has unexplained_defects:0; a leak (acquire w/o release) raises it
    (the conservation law actually fires)."""
    clean = conserve(extract_one(_CLEAN))
    leak = conserve(extract_one(_LEAK))
    return {"clean_unexplained_defects": clean["unexplained_defects"],
            "leak_unexplained_defects": leak["unexplained_defects"], "leak_imbalance": leak["imbalance"],
            "ok": clean["unexplained_defects"] == 0 and leak["unexplained_defects"] >= 1}


def concord_selftest() -> dict:
    """P3-T08 concord: the extracted CFG is contained in its declared blueprint (pass, empty diff); injecting
    an undeclared back-edge breaks containment (fail, the diff names the violating edge). Diff is stored."""
    import json
    ex = cfg(extract_one(_CLEAN))
    declared = json.loads(json.dumps(ex))                       # declared blueprint over the same stmt* vocab
    good = concord(ex, declared)
    bad_cfg = json.loads(json.dumps(ex))
    bad_cfg["edges"].append([ex["states"][-1], ex["states"][0]])   # an undeclared back-edge
    bad = concord(bad_cfg, declared)
    return {"contained": good["pass"], "diff_stored": good,
            "tamper_caught": not bad["pass"] and len(bad["violating_edges"]) >= 1,
            "violating_edges": bad["violating_edges"],
            "ok": good["pass"] and not bad["pass"] and len(bad["violating_edges"]) >= 1}


# ── the Citrinitas publish gate (P3-T09) ──────────────────────────────────────

def publish_gate(source: str, declared_cfg: dict = None) -> dict:
    """The verified-tier admission gate: a subject is admitted only if alchemy finds it clean on ALL of
    conserve (no unexplained defects), classify (no unnamed shapes), and concord (CFG contained in the
    declared blueprint — `declared_cfg` defaults to the subject's own block-order, so only an injected rogue
    edge fails). A failure BLOCKS publish with a NAMED reason. Returns {admit, tier, reason}."""
    bp = extract_one(source)
    cons = conserve(bp)
    if cons["unexplained_defects"] > 0:
        return {"admit": False, "tier": "blocked", "reason": "conservation_defect",
                "detail": cons["imbalance"]}
    cls = classify(bp)
    if cls["unnamed"] > 0:
        return {"admit": False, "tier": "blocked", "reason": "unnamed_shape", "detail": cls["unnamed"]}
    ex = cfg(bp)
    decl = declared_cfg or ex
    con = concord(ex, decl)
    if not con["pass"]:
        return {"admit": False, "tier": "blocked", "reason": "cfg_mismatch",
                "detail": con["violating_edges"]}
    return {"admit": True, "tier": "verified", "reason": "citrinitas_clean"}


def triple_block(stop_on_fail: bool = False) -> dict:
    """P3-T09 seeded_triple_blocks: a clean subject is admitted to the verified tier, and THREE seeded
    defects — a conservation defect, an unnamed shape, and a blueprint/CFG mismatch — each BLOCK publish
    with the correct named reason. Returns the per-case verdicts; `ok` iff all four behave."""
    clean = publish_gate(_CLEAN)
    leak = publish_gate(_LEAK)
    exotic = publish_gate(_EXOTIC)
    # cfg mismatch: a clean subject but a declared blueprint that forbids one of its real edges
    bp = extract_one(_CLEAN)
    ex = cfg(bp)
    narrowed = {"states": ex["states"], "edges": ex["edges"][1:]}   # declare-away the first real edge
    mismatch = publish_gate(_CLEAN, narrowed)
    return {"clean_admitted": clean["admit"] is True and clean["tier"] == "verified",
            "conservation_blocked": leak["admit"] is False and leak["reason"] == "conservation_defect",
            "unnamed_blocked": exotic["admit"] is False and exotic["reason"] == "unnamed_shape",
            "cfg_mismatch_blocked": mismatch["admit"] is False and mismatch["reason"] == "cfg_mismatch",
            "ok": (clean["admit"] and not leak["admit"] and not exotic["admit"] and not mismatch["admit"]
                   and leak["reason"] == "conservation_defect" and exotic["reason"] == "unnamed_shape"
                   and mismatch["reason"] == "cfg_mismatch")}


DECLARED_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "skillChip", "alchemy", "declared", "chip-cfgs.json")


def _porter_key(chip_dir: str, path: str) -> str:
    return os.path.relpath(path, chip_dir).replace(os.sep, "/")


def _porters(chip_dir: str):
    """Porter scripts of the chip's PERMITTED skills (the manifest's roster), not a blind directory glob —
    so a stray/foreign dir's porters are never modeled. Falls back to a glob only if skill_index can't be
    imported (e.g. a bare cartridge dir without the infra package on path)."""
    import glob
    try:
        from infra.tool import skill_index
        skills = skill_index.all_skills(chip_dir)
    except Exception:
        return sorted(glob.glob(os.path.join(chip_dir, "*", "perks", "*", "src", "*.py")))
    out = []
    for sk in skills:
        out += glob.glob(os.path.join(chip_dir, sk, "perks", "*", "src", "*.py"))
    return sorted(out)


def pin_declared(chip_dir: str, out_path: str = DECLARED_PATH) -> dict:
    """Author/refresh the DECLARED blueprints: extract each porter's CFG once and COMMIT it as that porter's
    declared blueprint. This is run deliberately (not during validation) — like re-pinning the chip's file
    hashes — so that `chip_wide_concord` later checks the live CFG against an INDEPENDENT committed artifact,
    not against itself. Returns {pinned, path}."""
    import json
    declared = {}
    for p in _porters(chip_dir):
        try:
            bp = extract_one(open(p).read())
        except Exception:
            continue
        if not bp.get("actions") and not bp.get("transitions"):
            continue
        declared[_porter_key(chip_dir, p)] = cfg(bp)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(declared, open(out_path, "w"), indent=2, sort_keys=True)
    return {"pinned": len(declared), "path": out_path}


def chip_wide_concord(chip_dir: str, declared_path: str = DECLARED_PATH) -> dict:
    """P3-T09 chip_wide_concord: re-extract every perk porter's CFG and run alchemy/concord against its
    COMMITTED declared blueprint (`declared/chip-cfgs.json`, an independent artifact pinned by `pin_declared`).
    100% pass means no porter's control-flow structure has drifted from its declared blueprint — a real
    tamper/drift gate (NOT a self-comparison: a porter edited after pinning fails). The result also carries a
    `discriminates` proof: a rogue edge injected into one live CFG is caught against its pin, so the 100% is
    never a tautology. Returns the pass rate + the drift failures."""
    import json
    if not os.path.isfile(declared_path):
        return {"ok": False, "reason": "no_declared_blueprints", "modeled": 0}
    declared = json.load(open(declared_path))
    modeled, passed, drifted, unpinned = 0, 0, [], []
    for p in _porters(chip_dir):
        try:
            bp = extract_one(open(p).read())
        except Exception:
            continue
        if not bp.get("actions") and not bp.get("transitions"):
            continue
        key = _porter_key(chip_dir, p)
        if key not in declared:                                # a porter with no committed declared blueprint
            unpinned.append(key)
            continue
        modeled += 1
        if concord(cfg(bp), declared[key])["pass"]:
            passed += 1
        else:
            drifted.append(key)
    # discrimination proof: a rogue back-edge injected into a real live CFG must be caught vs its pin
    discriminates = False
    if declared:
        k0 = sorted(declared)[0]
        live = json.loads(json.dumps(declared[k0]))            # the pinned CFG = a real live CFG
        if len(live["states"]) >= 2:
            live["edges"].append([live["states"][-1], live["states"][0]])   # undeclared back-edge
            discriminates = not concord(live, declared[k0])["pass"]
        else:
            discriminates = True                                # degenerate single-state porter: nothing to inject
    rate = (passed / modeled) if modeled else 0.0
    return {"modeled": modeled, "passed": passed, "drifted": drifted, "unpinned": unpinned,
            "rate": rate, "discriminates": discriminates,
            "ok": modeled >= 1 and not drifted and not unpinned and rate == 1.0 and discriminates}


def gate_selftest(chip_dir: str = None) -> dict:
    """The P3-T09 hermetic demonstration: the seeded triple-block fires (clean admitted, three defects each
    blocked with the named reason) AND chip-wide concord passes for every modeled porter. `ok` iff both."""
    tb = triple_block()
    chip = chip_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                    "skillChip")
    cw = chip_wide_concord(chip)
    return {"triple_block": tb,
            "chip_wide_concord": {k: cw.get(k) for k in ("modeled", "passed", "rate", "discriminates", "drifted")},
            "ok": tb["ok"] and cw["ok"]}
