window.SKILLS = [
 {
  "id": "ci-codeqc",
  "name": "CI code-QC generator",
  "description": "Generate or update a GitHub Actions code-QC workflow (ruff + mypy + pytest) for a repo. Idempotent \u2014 creates, or backs up and updates an existing workflow. Perk-agnostic lifecycle; the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "states": {
   "ready": {
    "description": "task-ledger submitted, nothing run"
   },
   "prepared": {
    "description": "inputs validated \u2014 required vars present, runtime + store ready"
   },
   "operated": {
    "description": "the chosen perk's tool sequence ran \u2014 ONLY via executor.py"
   },
   "verified": {
    "description": "the perk's contract checks passed (exit 0, declared outputs exist)"
   },
   "recorded": {
    "description": "run metadata + outputs recorded to the run-ledger"
   }
  },
  "transitions": [
   {
    "from": "ready",
    "to": "prepared",
    "trigger": "PREPARE",
    "action": "a_prepare",
    "gate": "g_prepared"
   },
   {
    "from": "prepared",
    "to": "operated",
    "trigger": "OPERATE",
    "action": "a_operate",
    "gate": "g_operated"
   },
   {
    "from": "operated",
    "to": "verified",
    "trigger": "VERIFY",
    "action": "a_verify",
    "gate": "g_verified"
   },
   {
    "from": "verified",
    "to": "recorded",
    "trigger": "RECORD",
    "action": "a_record"
   }
  ],
  "terminal": [
   "recorded"
  ],
  "entry": "ready",
  "safety_invariants": [
   {
    "name": "operate_only_when_prepared",
    "expression": "state /= 'operated' \\/ inputs_present",
    "description": "GUARDRAIL: no operation before inputs are validated."
   },
   {
    "name": "governed_execution_only",
    "expression": "state /= 'operated' \\/ governed_run",
    "description": "GUARDRAIL: tools run ONLY through executor.py \u2014 never directly. The runtime is the enforcement."
   },
   {
    "name": "verify_before_record",
    "expression": "state /= 'recorded' \\/ contract_checks_pass",
    "description": "GUARDRAIL: nothing is recorded as done until the perk's contract checks pass."
   },
   {
    "name": "oversight_clears_script",
    "expression": "TRUE",
    "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
   }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">ci-codeqc</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n",
  "skill_md": "---\nskill: ci-codeqc\nname: CI code-QC generator\nperks: [github_actions]\n---\n\n# ci-codeqc \u2014 generate/update a code-QC CI for any repo\n\nWrites a GitHub Actions **code-qc** workflow (`.github/workflows/codeqc.yml`) into a target repo:\ncheckout \u2192 setup Python \u2192 install \u2192 **ruff** (lint) \u2192 **mypy** (types) \u2192 **pytest --cov** (test).\nIdempotent \u2014 re-running regenerates it; an existing workflow is backed up to `.bk` first, so the same\nskill both *creates* and *updates* the CI.\n\n## What to look out for\nThe tool emits structured JSON with `action` = `created | updated` and the workflow path; LOGS TO\nCHECK: that line + `${record_store}/codeqc.yml` (a copy) + the executor run-ledger.\n\n## How to use it\nFill `PROJECT_DIR` (+ optional `SRC_DIR`, `TEST_DIR`, `PYTHON_VERSION`, `BRANCH`), then\nvalidate \u2192 compose \u2192 compile \u2192 oversight \u2192 executor. The workflow lands in the target repo; commit it.\n",
  "perks": [
   {
    "id": "github_actions",
    "summary": "write/update .github/workflows/codeqc.yml (ruff+mypy+pytest)",
    "destructive": false,
    "metadata": {
     "perk": "github_actions",
     "skill": "ci-codeqc",
     "description": "Generate/update a GitHub Actions code-QC workflow (ruff + mypy + pytest).",
     "rules": [
      "idempotent \u2014 existing workflow backed up to .bk before overwrite",
      "writes only .github/workflows/codeqc.yml",
      "non-destructive"
     ],
     "usage": "Set PROJECT_DIR (+ SRC_DIR, TEST_DIR, PYTHON_VERSION, BRANCH). Output: .github/workflows/codeqc.yml.",
     "limitation": "GitHub Actions + Python repos; the workflow is a sensible default, edit as needed.",
     "minimal_example": {
      "perk": "github_actions",
      "vars": {
       "PROJECT_DIR": "/path/to/repo",
       "SRC_DIR": "src",
       "TEST_DIR": "tests"
      }
     }
    },
    "sequence": [
     "ci_github_actions"
    ],
    "tools": {
     "ci_github_actions": {
      "binary": "bash",
      "params": {
       "PROJECT_DIR": "${PROJECT_DIR}",
       "SRC_DIR": "${SRC_DIR}",
       "TEST_DIR": "${TEST_DIR}",
       "PYTHON_VERSION": "${PYTHON_VERSION}",
       "BRANCH": "${BRANCH}"
      }
     }
    },
    "env": {
     "PROJECT_DIR": "${PROJECT_DIR}",
     "SRC_DIR": "${SRC_DIR}",
     "TEST_DIR": "${TEST_DIR}",
     "PYTHON_VERSION": "${PYTHON_VERSION}",
     "BRANCH": "${BRANCH}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "bash"
    ],
    "contracts": {
     "tool": "ci_github_actions",
     "inputs": {
      "PROJECT_DIR": {
       "type": "dir",
       "required": true
      },
      "SRC_DIR": {
       "type": "string",
       "required": false
      },
      "TEST_DIR": {
       "type": "string",
       "required": false
      },
      "PYTHON_VERSION": {
       "type": "string",
       "required": false
      },
      "BRANCH": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "workflow": {
       "path": "${RECORD_STORE}/codeqc.yml",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/codeqc.yml"
     }
    },
    "snippets": {
     "ci_github_actions.sh": "#!/usr/bin/env bash\n# ci_github_actions \u2014 generate/update a GitHub Actions code-QC workflow for a repo. Structured JSON.\n# Idempotent: re-running regenerates; an existing workflow is backed up to .bk first (= \"updated\").\nset -euo pipefail\n: \"${PROJECT_DIR:?}\" \"${RECORD_STORE:?}\"\nWFDIR=\"${PROJECT_DIR%/}/.github/workflows\"\nWF=\"$WFDIR/codeqc.yml\"\nmkdir -p \"$WFDIR\"\nACTION=\"created\"\nif [ -f \"$WF\" ]; then cp \"$WF\" \"$WF.bk\"; ACTION=\"updated\"; fi\ncat > \"$WF\" <<YAML\nname: code-qc\non:\n  push:\n    branches: [ \"${BRANCH:-main}\" ]\n  pull_request:\npermissions:\n  contents: read\njobs:\n  codeqc:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: \"${PYTHON_VERSION:-3.12}\"\n      - name: install\n        run: |\n          python -m pip install --upgrade pip\n          pip install ruff mypy pytest pytest-cov\n      - name: lint (ruff)\n        run: ruff check ${SRC_DIR:-.}\n      - name: types (mypy)\n        run: mypy ${SRC_DIR:-.} || true\n      - name: test (pytest)\n        run: pytest ${TEST_DIR:-tests} --cov=${SRC_DIR:-.} || echo \"no tests yet\"\nYAML\ncp \"$WF\" \"${RECORD_STORE%/}/codeqc.yml\"\nprintf '{\"tool\":\"ci_github_actions\",\"status\":\"ok\",\"action\":\"%s\",\"workflow\":\"%s\"}\\n' \"$ACTION\" \"$WF\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">ci-codeqc</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">ci_github_actions</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   }
  ]
 },
 {
  "id": "codebaseqc",
  "name": "Codebase QC (usage / contract / coverage)",
  "description": "Pure-Python ast quality checks for a Python repo over three dimensions \u2014 USAGE (dead code), CONTRACT (missing docstring/return type), COVERAGE (not referenced in tests). No alembic; name-based heuristics (sound resolution is the open frontier). Perk-agnostic lifecycle; the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "states": {
   "ready": {
    "description": "task-ledger submitted, nothing run"
   },
   "prepared": {
    "description": "inputs validated \u2014 required vars present, runtime + store ready"
   },
   "operated": {
    "description": "the chosen perk's tool sequence ran \u2014 ONLY via executor.py"
   },
   "verified": {
    "description": "the perk's contract checks passed (exit 0, declared outputs exist)"
   },
   "recorded": {
    "description": "run metadata + outputs recorded to the run-ledger"
   }
  },
  "transitions": [
   {
    "from": "ready",
    "to": "prepared",
    "trigger": "PREPARE",
    "action": "a_prepare",
    "gate": "g_prepared"
   },
   {
    "from": "prepared",
    "to": "operated",
    "trigger": "OPERATE",
    "action": "a_operate",
    "gate": "g_operated"
   },
   {
    "from": "operated",
    "to": "verified",
    "trigger": "VERIFY",
    "action": "a_verify",
    "gate": "g_verified"
   },
   {
    "from": "verified",
    "to": "recorded",
    "trigger": "RECORD",
    "action": "a_record"
   }
  ],
  "terminal": [
   "recorded"
  ],
  "entry": "ready",
  "safety_invariants": [
   {
    "name": "operate_only_when_prepared",
    "expression": "state /= 'operated' \\/ inputs_present",
    "description": "GUARDRAIL: no operation before inputs are validated."
   },
   {
    "name": "governed_execution_only",
    "expression": "state /= 'operated' \\/ governed_run",
    "description": "GUARDRAIL: tools run ONLY through executor.py \u2014 never directly. The runtime is the enforcement."
   },
   {
    "name": "verify_before_record",
    "expression": "state /= 'recorded' \\/ contract_checks_pass",
    "description": "GUARDRAIL: nothing is recorded as done until the perk's contract checks pass."
   },
   {
    "name": "oversight_clears_script",
    "expression": "TRUE",
    "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
   }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">codebaseqc</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n",
  "skill_md": "---\nskill: codebaseqc\nname: Codebase QC (usage / contract / coverage)\nperks: [audit]\n---\n\n# codebaseqc \u2014 pure-Python codebase QC\n\nThree-dimension quality check for a Python repo, **pure-Python ast** \u2014 no alembic, no dependencies:\n- **usage**   \u2014 functions defined but never referenced by name (dead-code heuristic)\n- **contract**\u2014 public functions missing a docstring or a return type\n- **coverage**\u2014 public functions whose name never appears in the test dir\n\n## What to look out for\nThe `audit` perk runs the three tools in sequence; each emits structured JSON and writes a\n`*_gaps.json` report to `record_store`. LOGS TO CHECK: `usage_gaps.json`, `contract_gaps.json`,\n`coverage_gaps.json`, plus the executor `run-ledger.json`.\n\n> **Honest scope:** these are *name-based* heuristics (the pure-Python pathway). Sound resolution \u2014\n> distinguishing `obj.method()` calls, jedi/pyright-grade \u2014 is the Intent-Fidelity frontier and the\n> reason the original codebaseqc reached for alembic. This migration is the dependency-free version.\n\n## How to use it\nFill `PROJECT_DIR` (+ optional `SRC_DIR`, `TEST_DIR`), then validate \u2192 compose \u2192 compile \u2192 oversight \u2192\nexecutor (the run is 3 governed steps).\n",
  "perks": [
   {
    "id": "audit",
    "summary": "full usage + contract + coverage QC (3 governed steps)",
    "destructive": false,
    "metadata": {
     "perk": "audit",
     "skill": "codebaseqc",
     "description": "Full usage + contract + coverage QC, pure-Python ast.",
     "rules": [
      "read-only \u2014 analyzes, never edits",
      "three reports to record_store",
      "name-based heuristics"
     ],
     "usage": "Set PROJECT_DIR (+ SRC_DIR, TEST_DIR). Outputs: usage_gaps.json, contract_gaps.json, coverage_gaps.json.",
     "limitation": "Name-based (no sound call resolution); Python only.",
     "minimal_example": {
      "perk": "audit",
      "vars": {
       "PROJECT_DIR": "/path/to/repo",
       "SRC_DIR": "src",
       "TEST_DIR": "tests"
      }
     }
    },
    "sequence": [
     "cbqc_usage",
     "cbqc_contract",
     "cbqc_coverage"
    ],
    "tools": {
     "cbqc_usage": {
      "binary": "python3",
      "params": {}
     },
     "cbqc_contract": {
      "binary": "python3",
      "params": {}
     },
     "cbqc_coverage": {
      "binary": "python3",
      "params": {}
     }
    },
    "env": {
     "PROJECT_DIR": "${PROJECT_DIR}",
     "SRC_DIR": "${SRC_DIR}",
     "TEST_DIR": "${TEST_DIR}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "python3"
    ],
    "contracts": {
     "tool": "audit",
     "inputs": {
      "PROJECT_DIR": {
       "type": "dir",
       "required": true
      },
      "SRC_DIR": {
       "type": "string",
       "required": false
      },
      "TEST_DIR": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "usage": {
       "path": "${RECORD_STORE}/usage_gaps.json"
      },
      "contract": {
       "path": "${RECORD_STORE}/contract_gaps.json"
      },
      "coverage": {
       "path": "${RECORD_STORE}/coverage_gaps.json"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/coverage_gaps.json"
     }
    },
    "snippets": {
     "cbqc_usage.py": "#!/usr/bin/env python3\n\"\"\"cbqc_usage \u2014 functions defined but never referenced by name (dead-code heuristic).\n\nReads PROJECT_DIR, SRC_DIR (default \".\"), RECORD_STORE from the environment; writes usage_gaps.json\nand prints one structured-JSON line (the audit/debug log). Name-based heuristic.\n\"\"\"\nfrom __future__ import annotations\nimport ast\nimport json\nimport os\nimport sys\n\n\ndef walk_py(root: str):\n    \"\"\"Yield (path, ast.Module) for every parseable .py file under root.\"\"\"\n    for dp, _, files in os.walk(root):\n        if \"__pycache__\" in dp or \"/.\" in dp:\n            continue\n        for f in files:\n            if not f.endswith(\".py\"):\n                continue\n            p = os.path.join(dp, f)\n            try:\n                yield p, ast.parse(open(p, encoding=\"utf-8\").read(), p)\n            except (SyntaxError, UnicodeDecodeError):\n                continue\n\n\ndef main() -> int:\n    \"\"\"Report functions whose name never appears as a call.\"\"\"\n    proj = os.environ[\"PROJECT_DIR\"]\n    src = os.environ.get(\"SRC_DIR\", \".\")\n    store = os.environ[\"RECORD_STORE\"].rstrip(\"/\")\n    root = proj if src in (\".\", \"\") else os.path.join(proj, src)\n    defs: dict[str, list[str]] = {}\n    calls: set[str] = set()\n    for path, tree in walk_py(root):\n        for n in ast.walk(tree):\n            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):\n                defs.setdefault(n.name, []).append(f\"{os.path.relpath(path, proj)}:{n.lineno}\")\n            elif isinstance(n, ast.Call):\n                fn = n.func\n                if isinstance(fn, ast.Name):\n                    calls.add(fn.id)\n                elif isinstance(fn, ast.Attribute):\n                    calls.add(fn.attr)\n    unused = {k: v for k, v in defs.items() if k not in calls and not k.startswith(\"__\")}\n    out = os.path.join(store, \"usage_gaps.json\")\n    json.dump({\"dimension\": \"usage\", \"unused_functions\": unused, \"defined\": len(defs), \"unused_count\": len(unused)},\n              open(out, \"w\"), indent=2)\n    print(json.dumps({\"tool\": \"cbqc_usage\", \"status\": \"ok\", \"report\": out, \"defined\": len(defs), \"unused\": len(unused)}))\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
     "cbqc_usage.sh": "#!/usr/bin/env bash\n# cbqc_usage \u2014 porter: runs the Python core, which reads PROJECT_DIR/SRC_DIR/RECORD_STORE from the environment.\n# The logic lives in cbqc_usage.py (standalone \u2014 inspect / lint / test it directly).\nset -euo pipefail\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nexec python3 \"$HERE/cbqc_usage.py\"\n",
     "cbqc_contract.py": "#!/usr/bin/env python3\n\"\"\"cbqc_contract \u2014 public functions missing a docstring or a return type.\n\nReads PROJECT_DIR, SRC_DIR (default \".\"), RECORD_STORE from the environment; writes contract_gaps.json\nand prints one structured-JSON line. ast-based (sound for this check).\n\"\"\"\nfrom __future__ import annotations\nimport ast\nimport json\nimport os\nimport sys\n\n\ndef walk_py(root: str):\n    \"\"\"Yield (path, ast.Module) for every parseable .py file under root.\"\"\"\n    for dp, _, files in os.walk(root):\n        if \"__pycache__\" in dp or \"/.\" in dp:\n            continue\n        for f in files:\n            if not f.endswith(\".py\"):\n                continue\n            p = os.path.join(dp, f)\n            try:\n                yield p, ast.parse(open(p, encoding=\"utf-8\").read(), p)\n            except (SyntaxError, UnicodeDecodeError):\n                continue\n\n\ndef main() -> int:\n    \"\"\"Report public functions lacking a docstring or a return annotation.\"\"\"\n    proj = os.environ[\"PROJECT_DIR\"]\n    src = os.environ.get(\"SRC_DIR\", \".\")\n    store = os.environ[\"RECORD_STORE\"].rstrip(\"/\")\n    root = proj if src in (\".\", \"\") else os.path.join(proj, src)\n    gaps: list[dict] = []\n    total = 0\n    for path, tree in walk_py(root):\n        for n in ast.walk(tree):\n            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith(\"_\"):\n                total += 1\n                missing = []\n                if not ast.get_docstring(n):\n                    missing.append(\"docstring\")\n                if n.returns is None:\n                    missing.append(\"return_type\")\n                if missing:\n                    gaps.append({\"fn\": n.name, \"at\": f\"{os.path.relpath(path, proj)}:{n.lineno}\", \"missing\": missing})\n    out = os.path.join(store, \"contract_gaps.json\")\n    json.dump({\"dimension\": \"contract\", \"gaps\": gaps, \"public_total\": total, \"gap_count\": len(gaps)},\n              open(out, \"w\"), indent=2)\n    print(json.dumps({\"tool\": \"cbqc_contract\", \"status\": \"ok\", \"report\": out, \"public\": total, \"gaps\": len(gaps)}))\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
     "cbqc_contract.sh": "#!/usr/bin/env bash\n# cbqc_contract \u2014 porter: runs the Python core, which reads PROJECT_DIR/SRC_DIR/RECORD_STORE from the environment.\n# The logic lives in cbqc_contract.py (standalone \u2014 inspect / lint / test it directly).\nset -euo pipefail\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nexec python3 \"$HERE/cbqc_contract.py\"\n",
     "cbqc_coverage.py": "#!/usr/bin/env python3\n\"\"\"cbqc_coverage \u2014 public functions whose name never appears in the test dir (coverage heuristic).\n\nReads PROJECT_DIR, SRC_DIR (default \".\"), TEST_DIR (default \"tests\"), RECORD_STORE from the\nenvironment; writes coverage_gaps.json and prints one structured-JSON line. Name-based heuristic.\n\"\"\"\nfrom __future__ import annotations\nimport ast\nimport json\nimport os\nimport sys\n\n\ndef walk_py(root: str):\n    \"\"\"Yield (path, ast.Module) for every parseable .py file under root.\"\"\"\n    for dp, _, files in os.walk(root):\n        if \"__pycache__\" in dp or \"/.\" in dp:\n            continue\n        for f in files:\n            if not f.endswith(\".py\"):\n                continue\n            p = os.path.join(dp, f)\n            try:\n                yield p, ast.parse(open(p, encoding=\"utf-8\").read(), p)\n            except (SyntaxError, UnicodeDecodeError):\n                continue\n\n\ndef main() -> int:\n    \"\"\"Report public functions not referenced anywhere under the test dir.\"\"\"\n    proj = os.environ[\"PROJECT_DIR\"]\n    src = os.environ.get(\"SRC_DIR\", \".\")\n    testdir = os.environ.get(\"TEST_DIR\", \"tests\")\n    store = os.environ[\"RECORD_STORE\"].rstrip(\"/\")\n    root = proj if src in (\".\", \"\") else os.path.join(proj, src)\n    troot = os.path.join(proj, testdir)\n    defs: dict[str, str] = {}\n    for path, tree in walk_py(root):\n        if os.path.abspath(path).startswith(os.path.abspath(troot)):\n            continue\n        for n in ast.walk(tree):\n            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith(\"_\"):\n                defs.setdefault(n.name, f\"{os.path.relpath(path, proj)}:{n.lineno}\")\n    tested: set[str] = set()\n    if os.path.isdir(troot):\n        for dp, _, files in os.walk(troot):\n            for f in files:\n                if f.endswith(\".py\"):\n                    text = open(os.path.join(dp, f), encoding=\"utf-8\", errors=\"ignore\").read()\n                    tested.update(name for name in defs if name in text)\n    uncovered = {k: v for k, v in defs.items() if k not in tested}\n    out = os.path.join(store, \"coverage_gaps.json\")\n    json.dump({\"dimension\": \"coverage\", \"uncovered\": uncovered, \"public_total\": len(defs),\n               \"uncovered_count\": len(uncovered), \"has_tests\": os.path.isdir(troot)}, open(out, \"w\"), indent=2)\n    print(json.dumps({\"tool\": \"cbqc_coverage\", \"status\": \"ok\", \"report\": out, \"public\": len(defs), \"uncovered\": len(uncovered)}))\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
     "cbqc_coverage.sh": "#!/usr/bin/env bash\n# cbqc_coverage \u2014 porter: runs the Python core, which reads PROJECT_DIR/SRC_DIR/TEST_DIR/RECORD_STORE from the environment.\n# The logic lives in cbqc_coverage.py (standalone \u2014 inspect / lint / test it directly).\nset -euo pipefail\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nexec python3 \"$HERE/cbqc_coverage.py\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">codebaseqc</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">cbqc_usage \u2192 cbqc_contract \u2192</text>\n<text x=\"41\" y=\"403\" font-size=\"9.5\" fill=\"#555\">cbqc_coverage</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   }
  ]
 },
 {
  "id": "fs",
  "name": "Filesystem operations",
  "description": "Filesystem work through proven pathways; outputs + manifests captured to record_store. Perk-agnostic lifecycle; the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "states": {
   "ready": {
    "description": "task-ledger submitted, nothing run"
   },
   "prepared": {
    "description": "inputs validated \u2014 required vars present, runtime + store ready"
   },
   "operated": {
    "description": "the chosen perk's tool sequence ran \u2014 ONLY via executor.py"
   },
   "verified": {
    "description": "the perk's contract checks passed (exit 0, declared outputs exist)"
   },
   "recorded": {
    "description": "run metadata + outputs recorded to the run-ledger"
   }
  },
  "transitions": [
   {
    "from": "ready",
    "to": "prepared",
    "trigger": "PREPARE",
    "action": "a_prepare",
    "gate": "g_prepared"
   },
   {
    "from": "prepared",
    "to": "operated",
    "trigger": "OPERATE",
    "action": "a_operate",
    "gate": "g_operated"
   },
   {
    "from": "operated",
    "to": "verified",
    "trigger": "VERIFY",
    "action": "a_verify",
    "gate": "g_verified"
   },
   {
    "from": "verified",
    "to": "recorded",
    "trigger": "RECORD",
    "action": "a_record"
   }
  ],
  "terminal": [
   "recorded"
  ],
  "entry": "ready",
  "safety_invariants": [
   {
    "name": "operate_only_when_prepared",
    "expression": "state /= 'operated' \\/ inputs_present",
    "description": "GUARDRAIL: no operation before inputs are validated."
   },
   {
    "name": "governed_execution_only",
    "expression": "state /= 'operated' \\/ governed_run",
    "description": "GUARDRAIL: tools run ONLY through executor.py \u2014 never directly. The runtime is the enforcement."
   },
   {
    "name": "verify_before_record",
    "expression": "state /= 'recorded' \\/ contract_checks_pass",
    "description": "GUARDRAIL: nothing is recorded as done until the perk's contract checks pass."
   },
   {
    "name": "oversight_clears_script",
    "expression": "TRUE",
    "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
   }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">fs</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n",
  "skill_md": "",
  "perks": [
   {
    "id": "archive",
    "summary": "tar.gz a directory",
    "destructive": false,
    "metadata": {
     "perk": "archive",
     "skill": "fs",
     "description": "tar.gz a directory",
     "rules": [
      "gzip tarball to record_store",
      "source unchanged"
     ],
     "usage": "Set SOURCE_DIR. Output: archive.tar.gz.",
     "limitation": "Single dir; no incremental.",
     "minimal_example": {
      "perk": "archive",
      "vars": {
       "SOURCE_DIR": "/path/to/dir"
      }
     }
    },
    "sequence": [
     "fs_archive"
    ],
    "tools": {
     "fs_archive": {
      "binary": "tar",
      "params": {
       "SOURCE_DIR": "${SOURCE_DIR}"
      }
     }
    },
    "env": {
     "SOURCE_DIR": "${SOURCE_DIR}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "tar"
    ],
    "contracts": {
     "tool": "fs_archive",
     "inputs": {
      "SOURCE_DIR": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "fs_archive_out": {
       "path": "${RECORD_STORE}/archive.tar.gz",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/archive.tar.gz"
     }
    },
    "snippets": {
     "fs_archive.sh": "#!/usr/bin/env bash\n# fs_archive \u2014 tar.gz a directory (proven pathway). Structured JSON output.\nset -euo pipefail\n: \"${SOURCE_DIR:?}\" \"${RECORD_STORE:?}\"\n[ -d \"$SOURCE_DIR\" ] || { printf '{\"tool\":\"fs_archive\",\"status\":\"error\",\"reason\":\"not a dir: %s\"}\\n' \"$SOURCE_DIR\"; exit 1; }\nOUT=\"${RECORD_STORE%/}/archive.tar.gz\"\ntar -czf \"$OUT\" -C \"$(dirname \"$SOURCE_DIR\")\" \"$(basename \"$SOURCE_DIR\")\"\nprintf '{\"tool\":\"fs_archive\",\"status\":\"ok\",\"source\":\"%s\",\"archive\":\"%s\",\"bytes\":%d}\\n' \"$SOURCE_DIR\" \"$OUT\" \"$(wc -c < \"$OUT\")\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">fs</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">fs_archive</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   },
   {
    "id": "find_large",
    "summary": "list files over a size threshold (read-only)",
    "destructive": false,
    "metadata": {
     "perk": "find_large",
     "skill": "fs",
     "description": "list files over a size threshold (read-only)",
     "rules": [
      "read-only",
      "listing to record_store"
     ],
     "usage": "Set SEARCH_DIR (+ MIN_SIZE, default 100M). Output: large_files.txt.",
     "limitation": "No deletion \u2014 listing only.",
     "minimal_example": {
      "perk": "find_large",
      "vars": {
       "SEARCH_DIR": "/var/log"
      }
     }
    },
    "sequence": [
     "fs_find_large"
    ],
    "tools": {
     "fs_find_large": {
      "binary": "find",
      "params": {
       "SEARCH_DIR": "${SEARCH_DIR}",
       "MIN_SIZE": "${MIN_SIZE}"
      }
     }
    },
    "env": {
     "SEARCH_DIR": "${SEARCH_DIR}",
     "MIN_SIZE": "${MIN_SIZE}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "find"
    ],
    "contracts": {
     "tool": "fs_find_large",
     "inputs": {
      "SEARCH_DIR": {
       "type": "string",
       "required": true
      },
      "MIN_SIZE": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "fs_find_large_out": {
       "path": "${RECORD_STORE}/large_files.txt",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/large_files.txt"
     }
    },
    "snippets": {
     "fs_find_large.sh": "#!/usr/bin/env bash\n# fs_find_large \u2014 list files over a size threshold (read-only). Structured JSON output.\nset -euo pipefail\n: \"${SEARCH_DIR:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/large_files.txt\"\nfind \"$SEARCH_DIR\" -type f -size +\"${MIN_SIZE:-100M}\" -print > \"$OUT\" 2>/dev/null || true\nprintf '{\"tool\":\"fs_find_large\",\"status\":\"ok\",\"search_dir\":\"%s\",\"threshold\":\"%s\",\"listing\":\"%s\",\"count\":%d}\\n' \"$SEARCH_DIR\" \"${MIN_SIZE:-100M}\" \"$OUT\" \"$(wc -l < \"$OUT\")\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">fs</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">fs_find_large</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   }
  ]
 },
 {
  "id": "git_ops",
  "name": "Git operations",
  "description": "Git work through proven pathways; the oversight ruleset refuses force-push and hard reset unless approved. Perk-agnostic lifecycle; the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "states": {
   "ready": {
    "description": "task-ledger submitted, nothing run"
   },
   "prepared": {
    "description": "inputs validated \u2014 required vars present, runtime + store ready"
   },
   "operated": {
    "description": "the chosen perk's tool sequence ran \u2014 ONLY via executor.py"
   },
   "verified": {
    "description": "the perk's contract checks passed (exit 0, declared outputs exist)"
   },
   "recorded": {
    "description": "run metadata + outputs recorded to the run-ledger"
   }
  },
  "transitions": [
   {
    "from": "ready",
    "to": "prepared",
    "trigger": "PREPARE",
    "action": "a_prepare",
    "gate": "g_prepared"
   },
   {
    "from": "prepared",
    "to": "operated",
    "trigger": "OPERATE",
    "action": "a_operate",
    "gate": "g_operated"
   },
   {
    "from": "operated",
    "to": "verified",
    "trigger": "VERIFY",
    "action": "a_verify",
    "gate": "g_verified"
   },
   {
    "from": "verified",
    "to": "recorded",
    "trigger": "RECORD",
    "action": "a_record"
   }
  ],
  "terminal": [
   "recorded"
  ],
  "entry": "ready",
  "safety_invariants": [
   {
    "name": "operate_only_when_prepared",
    "expression": "state /= 'operated' \\/ inputs_present",
    "description": "GUARDRAIL: no operation before inputs are validated."
   },
   {
    "name": "governed_execution_only",
    "expression": "state /= 'operated' \\/ governed_run",
    "description": "GUARDRAIL: tools run ONLY through executor.py \u2014 never directly. The runtime is the enforcement."
   },
   {
    "name": "verify_before_record",
    "expression": "state /= 'recorded' \\/ contract_checks_pass",
    "description": "GUARDRAIL: nothing is recorded as done until the perk's contract checks pass."
   },
   {
    "name": "oversight_clears_script",
    "expression": "TRUE",
    "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
   }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">git_ops</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n",
  "skill_md": "",
  "perks": [
   {
    "id": "snapshot",
    "summary": "stage all + commit in a repo",
    "destructive": false,
    "metadata": {
     "perk": "snapshot",
     "skill": "git_ops",
     "description": "stage all + commit in a repo",
     "rules": [
      "commits on the current branch",
      "no force, no history rewrite"
     ],
     "usage": "Set REPO_DIR + MESSAGE. Commits if dirty.",
     "limitation": "No push (a separate, gated pathway).",
     "minimal_example": {
      "perk": "snapshot",
      "vars": {
       "REPO_DIR": "/path/to/repo",
       "MESSAGE": "checkpoint"
      }
     }
    },
    "sequence": [
     "git_snapshot"
    ],
    "tools": {
     "git_snapshot": {
      "binary": "git",
      "params": {
       "REPO_DIR": "${REPO_DIR}",
       "MESSAGE": "${MESSAGE}"
      }
     }
    },
    "env": {
     "REPO_DIR": "${REPO_DIR}",
     "MESSAGE": "${MESSAGE}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "git"
    ],
    "contracts": {
     "tool": "git_snapshot",
     "inputs": {
      "REPO_DIR": {
       "type": "string",
       "required": true
      },
      "MESSAGE": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "git_snapshot_out": {
       "path": "${RECORD_STORE}/git_snapshot.json",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/git_snapshot.json"
     }
    },
    "snippets": {
     "git_snapshot.sh": "#!/usr/bin/env bash\n# git_snapshot \u2014 stage all + commit (proven pathway). Structured JSON output.\nset -euo pipefail\n: \"${REPO_DIR:?}\" \"${MESSAGE:?}\" \"${RECORD_STORE:?}\"\ncd \"$REPO_DIR\"\ngit add -A\nOUT=\"${RECORD_STORE%/}/git_snapshot.json\"\nif git diff --cached --quiet; then printf '{\"tool\":\"git_snapshot\",\"status\":\"noop\",\"reason\":\"nothing to commit\"}\\n' | tee \"$OUT\"; exit 0; fi\ngit commit -m \"$MESSAGE\" --no-verify >/dev/null\nSHA=$(git rev-parse --short HEAD)\nprintf '{\"tool\":\"git_snapshot\",\"status\":\"ok\",\"repo\":\"%s\",\"sha\":\"%s\"}\\n' \"$REPO_DIR\" \"$SHA\" | tee \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">git_ops</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">git_snapshot</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   },
   {
    "id": "status",
    "summary": "porcelain status (read-only)",
    "destructive": false,
    "metadata": {
     "perk": "status",
     "skill": "git_ops",
     "description": "porcelain status (read-only)",
     "rules": [
      "read-only"
     ],
     "usage": "Set REPO_DIR. Output: git_status.txt.",
     "limitation": "Reporting only.",
     "minimal_example": {
      "perk": "status",
      "vars": {
       "REPO_DIR": "/path/to/repo"
      }
     }
    },
    "sequence": [
     "git_status"
    ],
    "tools": {
     "git_status": {
      "binary": "git",
      "params": {
       "REPO_DIR": "${REPO_DIR}"
      }
     }
    },
    "env": {
     "REPO_DIR": "${REPO_DIR}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "git"
    ],
    "contracts": {
     "tool": "git_status",
     "inputs": {
      "REPO_DIR": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "git_status_out": {
       "path": "${RECORD_STORE}/git_status.txt",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/git_status.txt"
     }
    },
    "snippets": {
     "git_status.sh": "#!/usr/bin/env bash\n# git_status \u2014 porcelain status (read-only). Structured JSON output.\nset -euo pipefail\n: \"${REPO_DIR:?}\" \"${RECORD_STORE:?}\"\ncd \"$REPO_DIR\"\nOUT=\"${RECORD_STORE%/}/git_status.txt\"\ngit status --porcelain=v1 -b > \"$OUT\"\nDIRTY=$(grep -vc '^##' \"$OUT\" || true)\nprintf '{\"tool\":\"git_status\",\"status\":\"ok\",\"repo\":\"%s\",\"dirty_files\":%s,\"report\":\"%s\"}\\n' \"$REPO_DIR\" \"$DIRTY\" \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">git_ops</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">git_status</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   }
  ]
 },
 {
  "id": "http",
  "name": "HTTP requests",
  "description": "Make HTTP requests through proven, contract-bound pathways; responses captured to record_store with status + size in structured output. Perk-agnostic lifecycle; the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "states": {
   "ready": {
    "description": "task-ledger submitted, nothing run"
   },
   "prepared": {
    "description": "inputs validated \u2014 required vars present, runtime + store ready"
   },
   "operated": {
    "description": "the chosen perk's tool sequence ran \u2014 ONLY via executor.py"
   },
   "verified": {
    "description": "the perk's contract checks passed (exit 0, declared outputs exist)"
   },
   "recorded": {
    "description": "run metadata + outputs recorded to the run-ledger"
   }
  },
  "transitions": [
   {
    "from": "ready",
    "to": "prepared",
    "trigger": "PREPARE",
    "action": "a_prepare",
    "gate": "g_prepared"
   },
   {
    "from": "prepared",
    "to": "operated",
    "trigger": "OPERATE",
    "action": "a_operate",
    "gate": "g_operated"
   },
   {
    "from": "operated",
    "to": "verified",
    "trigger": "VERIFY",
    "action": "a_verify",
    "gate": "g_verified"
   },
   {
    "from": "verified",
    "to": "recorded",
    "trigger": "RECORD",
    "action": "a_record"
   }
  ],
  "terminal": [
   "recorded"
  ],
  "entry": "ready",
  "safety_invariants": [
   {
    "name": "operate_only_when_prepared",
    "expression": "state /= 'operated' \\/ inputs_present",
    "description": "GUARDRAIL: no operation before inputs are validated."
   },
   {
    "name": "governed_execution_only",
    "expression": "state /= 'operated' \\/ governed_run",
    "description": "GUARDRAIL: tools run ONLY through executor.py \u2014 never directly. The runtime is the enforcement."
   },
   {
    "name": "verify_before_record",
    "expression": "state /= 'recorded' \\/ contract_checks_pass",
    "description": "GUARDRAIL: nothing is recorded as done until the perk's contract checks pass."
   },
   {
    "name": "oversight_clears_script",
    "expression": "TRUE",
    "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
   }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">http</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n",
  "skill_md": "",
  "perks": [
   {
    "id": "get",
    "summary": "GET a URL into a response file",
    "destructive": false,
    "metadata": {
     "perk": "get",
     "skill": "http",
     "description": "GET a URL into a response file",
     "rules": [
      "response written to record_store",
      "status code in structured output"
     ],
     "usage": "Set URL (+ optional HEADER). Output: response.body.",
     "limitation": "No retries/auth helpers in this pathway.",
     "minimal_example": {
      "perk": "get",
      "vars": {
       "URL": "https://api.example.com/v1/x"
      }
     }
    },
    "sequence": [
     "http_get"
    ],
    "tools": {
     "http_get": {
      "binary": "curl",
      "params": {
       "URL": "${URL}",
       "HEADER": "${HEADER}"
      }
     }
    },
    "env": {
     "URL": "${URL}",
     "HEADER": "${HEADER}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "curl"
    ],
    "contracts": {
     "tool": "http_get",
     "inputs": {
      "URL": {
       "type": "string",
       "required": true
      },
      "HEADER": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "http_get_out": {
       "path": "${RECORD_STORE}/response.body",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/response.body"
     }
    },
    "snippets": {
     "http_get.sh": "#!/usr/bin/env bash\n# http_get \u2014 GET a URL (proven pathway). Deterministic structured JSON (audit/debug log).\nset -euo pipefail\n: \"${URL:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/response.body\"\nCODE=$(curl -sS -o \"$OUT\" -w '%{http_code}' ${HEADER:+-H \"$HEADER\"} \"$URL\")\nprintf '{\"tool\":\"http_get\",\"status\":\"ok\",\"url\":\"%s\",\"http_code\":%s,\"body_file\":\"%s\",\"bytes\":%d}\\n' \"$URL\" \"$CODE\" \"$OUT\" \"$(wc -c < \"$OUT\")\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">http</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">http_get</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   },
   {
    "id": "post",
    "summary": "POST a JSON body to a URL",
    "destructive": false,
    "metadata": {
     "perk": "post",
     "skill": "http",
     "description": "POST a JSON body to a URL",
     "rules": [
      "content-type: application/json",
      "response written to record_store"
     ],
     "usage": "Set URL + BODY (a JSON string). Output: response.body.",
     "limitation": "JSON bodies only.",
     "minimal_example": {
      "perk": "post",
      "vars": {
       "URL": "https://api.example.com/v1/x",
       "BODY": "a JSON string"
      }
     }
    },
    "sequence": [
     "http_post"
    ],
    "tools": {
     "http_post": {
      "binary": "curl",
      "params": {
       "URL": "${URL}",
       "BODY": "${BODY}"
      }
     }
    },
    "env": {
     "URL": "${URL}",
     "BODY": "${BODY}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "curl"
    ],
    "contracts": {
     "tool": "http_post",
     "inputs": {
      "URL": {
       "type": "string",
       "required": true
      },
      "BODY": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "http_post_out": {
       "path": "${RECORD_STORE}/response.body",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/response.body"
     }
    },
    "snippets": {
     "http_post.sh": "#!/usr/bin/env bash\n# http_post \u2014 POST a JSON body (proven pathway). Structured JSON output.\nset -euo pipefail\n: \"${URL:?}\" \"${BODY:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/response.body\"\nCODE=$(curl -sS -X POST -H 'content-type: application/json' -d \"$BODY\" -o \"$OUT\" -w '%{http_code}' \"$URL\")\nprintf '{\"tool\":\"http_post\",\"status\":\"ok\",\"url\":\"%s\",\"http_code\":%s,\"body_file\":\"%s\"}\\n' \"$URL\" \"$CODE\" \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">http</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">http_post</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   }
  ]
 },
 {
  "id": "pg_ops",
  "name": "Governed PostgreSQL operations",
  "description": "The general, perk-agnostic lifecycle of a governed DB operation. Tells the intelligence what to look out for (the guardrails) and which logs to check (the per-tool structured output + the executor's run-ledger). Perks are optional: any proven pathway plugs into a_operate.",
  "states": {
   "ready": {
    "description": "task-ledger submitted, nothing run"
   },
   "connected": {
    "description": "connection validated \u2014 host reachable, creds present, record_store writable"
   },
   "operated": {
    "description": "the chosen perk's tool sequence ran \u2014 ONLY via executor.py"
   },
   "verified": {
    "description": "the perk's contract checks passed (exit 0, declared outputs exist)"
   },
   "recorded": {
    "description": "run metadata + outputs recorded to the run-ledger"
   }
  },
  "transitions": [
   {
    "from": "ready",
    "to": "connected",
    "trigger": "CONNECT",
    "action": "a_connect",
    "gate": "g_connected"
   },
   {
    "from": "connected",
    "to": "operated",
    "trigger": "OPERATE",
    "action": "a_operate",
    "gate": "g_operated"
   },
   {
    "from": "operated",
    "to": "verified",
    "trigger": "VERIFY",
    "action": "a_verify",
    "gate": "g_verified"
   },
   {
    "from": "verified",
    "to": "recorded",
    "trigger": "RECORD",
    "action": "a_record"
   }
  ],
  "terminal": [
   "recorded"
  ],
  "entry": "ready",
  "safety_invariants": [
   {
    "name": "operate_only_when_connected",
    "expression": "state /= 'operated' \\/ host_reachable",
    "description": "GUARDRAIL: no operation before the connection is validated."
   },
   {
    "name": "governed_execution_only",
    "expression": "state /= 'operated' \\/ governed_run",
    "description": "GUARDRAIL: the perk's tools run ONLY through executor.py \u2014 never directly. The runtime is the enforcement."
   },
   {
    "name": "verify_before_record",
    "expression": "state /= 'recorded' \\/ contract_checks_pass",
    "description": "GUARDRAIL: nothing is recorded as done until the perk's contract checks pass."
   },
   {
    "name": "no_destructive_without_approval",
    "expression": "TRUE",
    "description": "GUARDRAIL: destructive SQL (DROP/TRUNCATE) is refused by OVERSIGHT_RULE unless explicitly approved (oversight.py --approve)."
   }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">pg_ops</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">CONNECT</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_connect</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">connected</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">connection validated \u2014 host</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">reachable, creds present,</text>\n<text x=\"41\" y=\"241\" font-size=\"9.5\" fill=\"#555\">record_store writable</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n",
  "skill_md": "---\nskill: pg_ops\nname: Governed PostgreSQL operations\nperks: [select, migrate]\n---\n\n# pg_ops \u2014 governed PostgreSQL operations\n\nRun PostgreSQL work through **proven, contract-bound pathways** under oversight. You never run SQL\ndirectly; you submit a **task-ledger** and the framework validates \u2192 composes \u2192 compiles \u2192 oversees \u2192\nexecutes it. Destructive SQL is refused unless explicitly approved.\n\n## What to look out for (for the intelligence)\n- The **blueprint** (`blueprint.json`) is the general lifecycle: `ready \u2192 connected \u2192 operated \u2192\n  verified \u2192 recorded`. Its `safety_invariants` are the things you must respect \u2014 chiefly\n  **governed_execution_only** (tools run *only* through `executor.py`) and **no_destructive_without_approval**.\n- Each tool emits **deterministic structured JSON** on stdout \u2014 that line *is* the audit + debug log.\n  After a run, check `${record_store}/run-ledger.json` (the executor's record) and each step's JSON.\n\n## How to use it \u2014 fill the form, submit it\n1. Pick a **perk** (a proven pathway): `select` (read-only query) or `migrate` (apply a SQL file).\n2. Copy `ledger.json` \u2192 your `task-ledger.json` and fill the `${...}` fields, bounded by the perk's\n   `manifesto.json` (the variables it accepts) and `src/contracts.json` (the I/O + checks).\n3. Hand it to the infrastructure:\n   ```sh\n   python3 infra/validator.py --ledger task-ledger.json     # are the claims real?\n   python3 infra/composer.py  --ledger task-ledger.json     # L++ \u2192 TLC, no deadlock\n   python3 infra/compiler.py  --ledger task-ledger.json -o run.sh\n   python3 infra/oversight.py --script run.sh               # OVERSIGHT_RULE (drops refused)\n   python3 infra/executor.py  --script run.sh --step 1      # the ONLY way to run\n   ```\n\n## Perks\n| perk | pathway | destructive? |\n|---|---|---|\n| `select` | read-only `SELECT \u2026 LIMIT` \u2192 CSV | no |\n| `migrate` | apply a `.sql` migration file in a transaction | yes (DROP/TRUNCATE refused by oversight unless `--approve`) |\n\nThe blueprint is **perk-agnostic** \u2014 it describes the lifecycle and the guardrails; a perk supplies the\nconcrete, contract-bound *how*.\n",
  "perks": [
   {
    "id": "select",
    "summary": "read-only SELECT \u2192 CSV",
    "destructive": false,
    "metadata": {
     "perk": "select",
     "skill": "pg_ops",
     "description": "Read-only SELECT against a database, written to CSV. The safe, proven query pathway.",
     "rules": [
      "read-only \u2014 no DML/DDL",
      "LIMIT enforced",
      "CSV output to record_store"
     ],
     "usage": "Set QUERY to a SELECT; LIMIT caps rows. Output: ${record_store}/select_rows.csv.",
     "limitation": "SELECT only; INSERT/UPDATE/DELETE/DDL are refused at oversight.",
     "minimal_example": {
      "perk": "select",
      "vars": {
       "PGHOST": "localhost",
       "PGDATABASE": "demo",
       "PGUSER": "reader",
       "QUERY": "SELECT id,name FROM users",
       "LIMIT": "50"
      }
     }
    },
    "sequence": [
     "psql_select"
    ],
    "tools": {
     "psql_select": {
      "binary": "psql",
      "params": {
       "query": "${QUERY}",
       "limit": "${LIMIT}"
      }
     }
    },
    "env": {
     "PGHOST": "${PGHOST}",
     "PGPORT": "${PGPORT}",
     "PGDATABASE": "${PGDATABASE}",
     "PGUSER": "${PGUSER}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "psql"
    ],
    "contracts": {
     "tool": "psql_select",
     "inputs": {
      "QUERY": {
       "type": "string",
       "required": true
      },
      "LIMIT": {
       "type": "integer",
       "default": "100"
      },
      "PGHOST": {
       "type": "string",
       "required": true
      },
      "PGDATABASE": {
       "type": "string",
       "required": true
      },
      "PGUSER": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "rows_csv": {
       "path": "${RECORD_STORE}/select_rows.csv",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/select_rows.csv"
     }
    },
    "snippets": {
     "psql_select.sh": "#!/usr/bin/env bash\n# psql_select \u2014 read-only SELECT (proven pathway). Emits deterministic structured JSON (audit/debug log).\nset -euo pipefail\n: \"${PGHOST:?}\" \"${PGDATABASE:?}\" \"${PGUSER:?}\" \"${QUERY:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/select_rows.csv\"\nPGPASSWORD=\"${PGPASSWORD:-}\" psql -h \"$PGHOST\" -p \"${PGPORT:-5432}\" -d \"$PGDATABASE\" -U \"$PGUSER\" \\\n  --no-psqlrc --csv -c \"${QUERY} LIMIT ${LIMIT:-100}\" > \"$OUT\"\nprintf '{\"tool\":\"psql_select\",\"status\":\"ok\",\"rows_csv\":\"%s\",\"rows\":%d}\\n' \"$OUT\" \"$(($(wc -l < \"$OUT\")-1))\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">pg_ops</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">CONNECT</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_connect</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">connected</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">connection validated \u2014 host</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">reachable, creds present,</text>\n<text x=\"41\" y=\"241\" font-size=\"9.5\" fill=\"#555\">record_store writable</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">psql_select</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   },
   {
    "id": "migrate",
    "summary": "apply a .sql migration in one transaction",
    "destructive": true,
    "metadata": {
     "perk": "migrate",
     "skill": "pg_ops",
     "description": "Apply a .sql migration file inside a single transaction (rollback on any error).",
     "rules": [
      "wrapped in one transaction (ON_ERROR_STOP, --single-transaction)",
      "DROP/TRUNCATE refused by oversight unless approved",
      "migration file must exist"
     ],
     "usage": "Set MIGRATION to a .sql path. Applied atomically; structured output reports the applied log.",
     "limitation": "Destructive DDL (DROP/TRUNCATE) blocked at oversight unless explicitly approved (--approve).",
     "minimal_example": {
      "perk": "migrate",
      "vars": {
       "PGHOST": "localhost",
       "PGDATABASE": "demo",
       "PGUSER": "admin",
       "MIGRATION": "/path/0001_add_index.sql"
      }
     }
    },
    "sequence": [
     "psql_migrate"
    ],
    "tools": {
     "psql_migrate": {
      "binary": "psql",
      "params": {
       "migration": "${MIGRATION}"
      }
     }
    },
    "env": {
     "PGHOST": "${PGHOST}",
     "PGPORT": "${PGPORT}",
     "PGDATABASE": "${PGDATABASE}",
     "PGUSER": "${PGUSER}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "psql"
    ],
    "contracts": {
     "tool": "psql_migrate",
     "inputs": {
      "MIGRATION": {
       "type": "file",
       "required": true
      },
      "PGHOST": {
       "type": "string",
       "required": true
      },
      "PGDATABASE": {
       "type": "string",
       "required": true
      },
      "PGUSER": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "applied_log": {
       "path": "${RECORD_STORE}/migrate_applied.log",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/migrate_applied.log"
     }
    },
    "snippets": {
     "psql_migrate.sh": "#!/usr/bin/env bash\n# psql_migrate \u2014 apply a .sql migration in ONE transaction. Structured JSON output (audit/debug log).\nset -euo pipefail\n: \"${PGHOST:?}\" \"${PGDATABASE:?}\" \"${PGUSER:?}\" \"${MIGRATION:?}\" \"${RECORD_STORE:?}\"\n[ -f \"$MIGRATION\" ] || { printf '{\"tool\":\"psql_migrate\",\"status\":\"error\",\"reason\":\"migration not found: %s\"}\\n' \"$MIGRATION\"; exit 1; }\nLOG=\"${RECORD_STORE%/}/migrate_applied.log\"\nPGPASSWORD=\"${PGPASSWORD:-}\" psql -h \"$PGHOST\" -p \"${PGPORT:-5432}\" -d \"$PGDATABASE\" -U \"$PGUSER\" \\\n  --no-psqlrc -v ON_ERROR_STOP=1 --single-transaction -f \"$MIGRATION\" > \"$LOG\" 2>&1\nprintf '{\"tool\":\"psql_migrate\",\"status\":\"ok\",\"migration\":\"%s\",\"applied_log\":\"%s\"}\\n' \"$MIGRATION\" \"$LOG\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">pg_ops</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">CONNECT</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_connect</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">connected</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">connection validated \u2014 host</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">reachable, creds present,</text>\n<text x=\"41\" y=\"241\" font-size=\"9.5\" fill=\"#555\">record_store writable</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">psql_migrate</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   }
  ]
 },
 {
  "id": "py_qc",
  "name": "Python quality checks",
  "description": "Run Python tests + lint through proven pathways; reports captured to record_store. Perk-agnostic lifecycle; the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "states": {
   "ready": {
    "description": "task-ledger submitted, nothing run"
   },
   "prepared": {
    "description": "inputs validated \u2014 required vars present, runtime + store ready"
   },
   "operated": {
    "description": "the chosen perk's tool sequence ran \u2014 ONLY via executor.py"
   },
   "verified": {
    "description": "the perk's contract checks passed (exit 0, declared outputs exist)"
   },
   "recorded": {
    "description": "run metadata + outputs recorded to the run-ledger"
   }
  },
  "transitions": [
   {
    "from": "ready",
    "to": "prepared",
    "trigger": "PREPARE",
    "action": "a_prepare",
    "gate": "g_prepared"
   },
   {
    "from": "prepared",
    "to": "operated",
    "trigger": "OPERATE",
    "action": "a_operate",
    "gate": "g_operated"
   },
   {
    "from": "operated",
    "to": "verified",
    "trigger": "VERIFY",
    "action": "a_verify",
    "gate": "g_verified"
   },
   {
    "from": "verified",
    "to": "recorded",
    "trigger": "RECORD",
    "action": "a_record"
   }
  ],
  "terminal": [
   "recorded"
  ],
  "entry": "ready",
  "safety_invariants": [
   {
    "name": "operate_only_when_prepared",
    "expression": "state /= 'operated' \\/ inputs_present",
    "description": "GUARDRAIL: no operation before inputs are validated."
   },
   {
    "name": "governed_execution_only",
    "expression": "state /= 'operated' \\/ governed_run",
    "description": "GUARDRAIL: tools run ONLY through executor.py \u2014 never directly. The runtime is the enforcement."
   },
   {
    "name": "verify_before_record",
    "expression": "state /= 'recorded' \\/ contract_checks_pass",
    "description": "GUARDRAIL: nothing is recorded as done until the perk's contract checks pass."
   },
   {
    "name": "oversight_clears_script",
    "expression": "TRUE",
    "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
   }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">py_qc</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n",
  "skill_md": "",
  "perks": [
   {
    "id": "test",
    "summary": "run pytest",
    "destructive": false,
    "metadata": {
     "perk": "test",
     "skill": "py_qc",
     "description": "run pytest",
     "rules": [
      "report to record_store",
      "exit reflects pass/fail"
     ],
     "usage": "Set PROJECT_DIR (+ TEST_DIR, PYTEST_ARGS). Output: pytest.out.",
     "limitation": "pytest-based.",
     "minimal_example": {
      "perk": "test",
      "vars": {
       "PROJECT_DIR": "/path/to/proj"
      }
     }
    },
    "sequence": [
     "py_test"
    ],
    "tools": {
     "py_test": {
      "binary": "python3",
      "params": {
       "PROJECT_DIR": "${PROJECT_DIR}",
       "TEST_DIR": "${TEST_DIR}",
       "PYTEST_ARGS": "${PYTEST_ARGS}"
      }
     }
    },
    "env": {
     "PROJECT_DIR": "${PROJECT_DIR}",
     "TEST_DIR": "${TEST_DIR}",
     "PYTEST_ARGS": "${PYTEST_ARGS}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "python3"
    ],
    "contracts": {
     "tool": "py_test",
     "inputs": {
      "PROJECT_DIR": {
       "type": "string",
       "required": true
      },
      "TEST_DIR": {
       "type": "string",
       "required": false
      },
      "PYTEST_ARGS": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "py_test_out": {
       "path": "${RECORD_STORE}/pytest.out",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/pytest.out"
     }
    },
    "snippets": {
     "py_test.sh": "#!/usr/bin/env bash\n# py_test \u2014 run pytest (proven pathway). Structured JSON output.\nset -uo pipefail\n: \"${PROJECT_DIR:?}\" \"${RECORD_STORE:?}\"\ncd \"$PROJECT_DIR\"\nOUT=\"${RECORD_STORE%/}/pytest.out\"\n\"${PYTHON:-python3}\" -m pytest \"${TEST_DIR:-tests}\" ${PYTEST_ARGS:-} > \"$OUT\" 2>&1\nRC=$?\nprintf '{\"tool\":\"py_test\",\"status\":\"%s\",\"exit\":%d,\"report\":\"%s\"}\\n' \"$([ $RC -eq 0 ] && echo ok || echo fail)\" \"$RC\" \"$OUT\"\nexit $RC\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">py_qc</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">py_test</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   },
   {
    "id": "lint",
    "summary": "run ruff (fallback flake8)",
    "destructive": false,
    "metadata": {
     "perk": "lint",
     "skill": "py_qc",
     "description": "run ruff (fallback flake8)",
     "rules": [
      "report to record_store"
     ],
     "usage": "Set PROJECT_DIR (+ LINT_TARGET). Output: lint.out.",
     "limitation": "ruff or flake8 must be installed.",
     "minimal_example": {
      "perk": "lint",
      "vars": {
       "PROJECT_DIR": "/path/to/proj"
      }
     }
    },
    "sequence": [
     "py_lint"
    ],
    "tools": {
     "py_lint": {
      "binary": "python3",
      "params": {
       "PROJECT_DIR": "${PROJECT_DIR}",
       "LINT_TARGET": "${LINT_TARGET}"
      }
     }
    },
    "env": {
     "PROJECT_DIR": "${PROJECT_DIR}",
     "LINT_TARGET": "${LINT_TARGET}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "python3"
    ],
    "contracts": {
     "tool": "py_lint",
     "inputs": {
      "PROJECT_DIR": {
       "type": "string",
       "required": true
      },
      "LINT_TARGET": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "py_lint_out": {
       "path": "${RECORD_STORE}/lint.out",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/lint.out"
     }
    },
    "snippets": {
     "py_lint.sh": "#!/usr/bin/env bash\n# py_lint \u2014 run ruff (fallback flake8) (proven pathway). Structured JSON output.\nset -uo pipefail\n: \"${PROJECT_DIR:?}\" \"${RECORD_STORE:?}\"\ncd \"$PROJECT_DIR\"\nOUT=\"${RECORD_STORE%/}/lint.out\"\nif command -v ruff >/dev/null; then ruff check \"${LINT_TARGET:-.}\" > \"$OUT\" 2>&1; RC=$?\nelif command -v flake8 >/dev/null; then flake8 \"${LINT_TARGET:-.}\" > \"$OUT\" 2>&1; RC=$?\nelse echo \"no linter (ruff/flake8) found\" > \"$OUT\"; RC=127; fi\nprintf '{\"tool\":\"py_lint\",\"status\":\"%s\",\"exit\":%d,\"report\":\"%s\"}\\n' \"$([ $RC -eq 0 ] && echo ok || echo issues)\" \"$RC\" \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"310\" height=\"810\" viewBox=\"0 0 310 810\" font-family=\"-apple-system,Segoe UI,Roboto,sans-serif\">\n<defs><marker id=\"arr\" markerWidth=\"9\" markerHeight=\"9\" refX=\"7\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L7,3 L0,6 z\" fill=\"#444\"/></marker></defs>\n<rect width=\"310\" height=\"810\" fill=\"#ffffff\"/>\n<text x=\"14\" y=\"20\" font-size=\"13\" font-weight=\"700\" fill=\"#333\">py_qc</text>\n<path d=\"M135.0,108 C135.0,153 135.0,135 135.0,180\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"142\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">PREPARE</text>\n<text x=\"140\" y=\"155\" font-size=\"9\" fill=\"#999\">a_prepare</text>\n<path d=\"M135.0,258 C135.0,303 135.0,285 135.0,330\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"292\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">OPERATE</text>\n<text x=\"140\" y=\"305\" font-size=\"9\" fill=\"#999\">a_operate</text>\n<path d=\"M135.0,408 C135.0,453 135.0,435 135.0,480\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"442\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">VERIFY</text>\n<text x=\"140\" y=\"455\" font-size=\"9\" fill=\"#999\">a_verify</text>\n<path d=\"M135.0,558 C135.0,603 135.0,585 135.0,630\" fill=\"none\" stroke=\"#444\" stroke-width=\"1.4\" marker-end=\"url(#arr)\"/>\n<text x=\"140\" y=\"592\" font-size=\"11\" font-weight=\"600\" fill=\"#333\">RECORD</text>\n<text x=\"140\" y=\"605\" font-size=\"9\" fill=\"#999\">a_record</text>\n<rect x=\"30\" y=\"30\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#dae8fc\" stroke=\"#6c8ebf\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"50\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">ready</text>\n<text x=\"41\" y=\"67\" font-size=\"9.5\" fill=\"#555\">task-ledger submitted, nothing</text>\n<text x=\"41\" y=\"79\" font-size=\"9.5\" fill=\"#555\">run</text>\n<rect x=\"30\" y=\"180\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"200\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">prepared</text>\n<text x=\"41\" y=\"217\" font-size=\"9.5\" fill=\"#555\">inputs validated \u2014 required vars</text>\n<text x=\"41\" y=\"229\" font-size=\"9.5\" fill=\"#555\">present, runtime + store ready</text>\n<rect x=\"30\" y=\"330\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"350\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">operated</text>\n<text x=\"41\" y=\"367\" font-size=\"9.5\" fill=\"#555\">the chosen perk&#x27;s tool sequence</text>\n<text x=\"41\" y=\"379\" font-size=\"9.5\" fill=\"#555\">ran \u2014 ONLY via executor.py \u25b6</text>\n<text x=\"41\" y=\"391\" font-size=\"9.5\" fill=\"#555\">py_lint</text>\n<rect x=\"30\" y=\"480\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#f5f5f5\" stroke=\"#aaaaaa\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"500\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">verified</text>\n<text x=\"41\" y=\"517\" font-size=\"9.5\" fill=\"#555\">the perk&#x27;s contract checks passed</text>\n<text x=\"41\" y=\"529\" font-size=\"9.5\" fill=\"#555\">(exit 0, declared outputs exist)</text>\n<rect x=\"30\" y=\"630\" width=\"210\" height=\"78\" rx=\"9\" fill=\"#d5e8d4\" stroke=\"#82b366\" stroke-width=\"1.5\"/>\n<text x=\"41\" y=\"650\" font-size=\"13\" font-weight=\"700\" fill=\"#222\">recorded</text>\n<text x=\"41\" y=\"667\" font-size=\"9.5\" fill=\"#555\">run metadata + outputs recorded</text>\n<text x=\"41\" y=\"679\" font-size=\"9.5\" fill=\"#555\">to the run-ledger</text>\n</svg>\n"
   }
  ]
 }
];
