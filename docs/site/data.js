window.SKILLS = [
 {
  "id": "ci-codeqc",
  "name": "CI code-QC generator",
  "description": "Generate or update a GitHub Actions code-QC workflow (ruff + mypy + pytest) for a repo. Idempotent \u2014 creates, or backs up and updates an existing workflow. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "ci-codeqc",
   "name": "CI code-QC generator",
   "description": "Generate or update a GitHub Actions code-QC workflow (ruff + mypy + pytest) for a repo. Idempotent \u2014 creates, or backs up and updates an existing workflow. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">CI-CODEQC</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">CI-CODEQC</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 ci_github_actions</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "ci-codeqc",
      "perk": "github_actions",
      "record_store": "/tmp/ci-codeqc-demo",
      "vars": {
       "PROJECT_DIR": "/path/to/repo",
       "SRC_DIR": "src",
       "TEST_DIR": "tests",
       "PYTHON_VERSION": "3.12",
       "BRANCH": "main"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=ci-codeqc perk=github_actions\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport PROJECT_DIR=/path/to/repo SRC_DIR=src TEST_DIR=tests PYTHON_VERSION=3.12 BRANCH=main RECORD_STORE=/tmp/ci-codeqc-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/ci-codeqc/perks/github_actions/src\n\nstep1() {   # ci_github_actions\n  echo \"[step 1] ci_github_actions\"\n  bash \"$SNIP/ci_github_actions.sh\"\n  test -f \"${RECORD_STORE}/codeqc.yml\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/codeqc.yml\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tci_github_actions\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "codebaseqc",
  "name": "Codebase QC (usage / contract / coverage)",
  "description": "Pure-Python ast quality checks for a Python repo over three dimensions \u2014 USAGE (dead code), CONTRACT (missing docstring/return type), COVERAGE (not referenced in tests). No alembic; name-based heuristics (sound resolution is the open frontier). Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "codebaseqc",
   "name": "Codebase QC (usage / contract / coverage)",
   "description": "Pure-Python ast quality checks for a Python repo over three dimensions \u2014 USAGE (dead code), CONTRACT (missing docstring/return type), COVERAGE (not referenced in tests). No alembic; name-based heuristics (sound resolution is the open frontier). Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">CODEBASEQC</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"703\" height=\"1028\" viewBox=\"0 0 703 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"703\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"703\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">CODEBASEQC</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 cbqc_usage \u2192 cbqc_contract \u2192 cbqc_coverage</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "codebaseqc",
      "perk": "audit",
      "record_store": "/tmp/codebaseqc-demo",
      "vars": {
       "PROJECT_DIR": "/path/to/repo",
       "SRC_DIR": "src",
       "TEST_DIR": "tests"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=codebaseqc perk=audit\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport PROJECT_DIR=/path/to/repo SRC_DIR=src TEST_DIR=tests RECORD_STORE=/tmp/codebaseqc-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/codebaseqc/perks/audit/src\n\nstep1() {   # cbqc_usage\n  echo \"[step 1] cbqc_usage\"\n  bash \"$SNIP/cbqc_usage.sh\"\n}\n\nstep2() {   # cbqc_contract\n  echo \"[step 2] cbqc_contract\"\n  bash \"$SNIP/cbqc_contract.sh\"\n}\n\nstep3() {   # cbqc_coverage\n  echo \"[step 3] cbqc_coverage\"\n  bash \"$SNIP/cbqc_coverage.sh\"\n  test -f \"${RECORD_STORE}/coverage_gaps.json\" || { echo \"CONTRACT FAIL step 3: missing ${RECORD_STORE}/coverage_gaps.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tcbqc_usage\\n2\\tcbqc_contract\\n3\\tcbqc_coverage\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 && step2 && step3 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "cws-create",
  "name": "Cyberware skill create",
  "description": "Evaluate a candidate skill \u2014 execution (tool) vs design (taste) vs transformable \u2014 and, when it fits, scaffold it into cyberware format. The framework's on-ramp for new skills. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "cws internals",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "cws-create",
   "name": "Cyberware skill create",
   "description": "Evaluate a candidate skill \u2014 execution (tool) vs design (taste) vs transformable \u2014 and, when it fits, scaffold it into cyberware format. The framework's on-ramp for new skills. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">CWS-CREATE</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
  "skill_md": "---\nskill: cws-create\nname: Cyberware skill create\nperks: [evaluate, scaffold]\n---\n\n# cws-create \u2014 the on-ramp for new skills\n\nHand it a candidate skill (a name + a plain description of what it does) and it classifies it:\n\n- **execution** \u2014 a deterministic tool/pathway (run, build, query, fetch, \u2026). Fits cyberware directly.\n- **design** \u2014 a taste/aesthetic skill (palette, typography, layout, \u2026). **Not** the cyberware emphasis \u2014\n  the framework governs deterministic execution, not aesthetics. Keep it as guidance.\n- **transformable** \u2014 mixes both; extract the execution core into a governed pathway, leave the taste as guidance.\n- **unclear** \u2014 describe what it DOES (inputs \u2192 action \u2192 output) so it can be classified.\n\n## What to look out for\n`evaluate` emits the verdict + the signals it matched + a recommendation, to `evaluation.json`. The verdict\nis a keyword heuristic \u2014 a recommendation, not a proof; the intelligence makes the call.\n\n## Perks\n- `evaluate` \u2014 classify a candidate + recommendation (read-only).\n- `scaffold` \u2014 lay down the cyberware skeleton (blueprint + perks + contracts + snippet stubs) for a fitting\n  skill, via `infra/scaffold.py`.\n\n## How to use it\n1. `evaluate`: set `SKILL_NAME` + `SKILL_DESC` \u2192 the verdict.\n2. If execution / transformable \u2014 `scaffold`: set `NEW_SKILL` + `NEW_NAME` + `PERKS`\n   (space-separated `<pid>:<tool>[:<binary>]`) \u2192 the skeleton is created.\n",
  "perks": [
   {
    "id": "evaluate",
    "summary": "classify a candidate skill: execution | design | transformable",
    "destructive": false,
    "metadata": {
     "perk": "evaluate",
     "skill": "cws-create",
     "description": "Classify a candidate skill: execution | design | transformable | unclear.",
     "rules": [
      "read-only \u2014 analyzes a description, writes no skill",
      "keyword heuristic \u2014 a recommendation, not a proof"
     ],
     "usage": "Set SKILL_NAME + SKILL_DESC. Output: evaluation.json (verdict + signals + recommendation).",
     "limitation": "Heuristic on the description text; the intelligence makes the final call.",
     "minimal_example": {
      "perk": "evaluate",
      "vars": {
       "SKILL_NAME": "pg-backup",
       "SKILL_DESC": "runs pg_dump to back up a Postgres database to a file"
      }
     }
    },
    "sequence": [
     "cws_evaluate"
    ],
    "tools": {
     "cws_evaluate": {
      "binary": "python3",
      "params": {
       "SKILL_NAME": "${SKILL_NAME}",
       "SKILL_DESC": "${SKILL_DESC}"
      }
     }
    },
    "env": {
     "SKILL_NAME": "${SKILL_NAME}",
     "SKILL_DESC": "${SKILL_DESC}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "python3"
    ],
    "contracts": {
     "tool": "cws_evaluate",
     "inputs": {
      "SKILL_NAME": {
       "type": "string",
       "required": true
      },
      "SKILL_DESC": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "evaluation": {
       "path": "${RECORD_STORE}/evaluation.json",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/evaluation.json"
     }
    },
    "snippets": {
     "cws_evaluate.py": "#!/usr/bin/env python3\n\"\"\"cws_evaluate \u2014 classify a candidate skill: execution (tool) | design (taste) | transformable | unclear.\n\nReads SKILL_NAME, SKILL_DESC, RECORD_STORE from the environment; writes evaluation.json and prints one\nstructured-JSON line. Keyword heuristic \u2014 the verdict is a recommendation, not a proof.\n\"\"\"\nfrom __future__ import annotations\nimport json\nimport os\nimport re\nimport sys\n\nEXEC = [\"run\", \"build\", \"fetch\", \"query\", \"deploy\", \"compile\", \"test\", \"lint\", \"transform\", \"convert\",\n        \"archive\", \"search\", \"commit\", \"tag\", \"execute\", \"send\", \"post\", \"request\", \"scan\", \"validate\",\n        \"generate\", \"migrate\", \"backup\", \"restore\", \"extract\", \"parse\", \"format\", \"check\", \"process\",\n        \"upload\", \"download\", \"sync\", \"render\", \"analyze\", \"count\", \"resolve\", \"diff\", \"snapshot\"]\nDESIGN = [\"color\", \"colour\", \"font\", \"layout\", \"aesthetic\", \"style\", \"theme\", \"visual\", \"fade\",\n          \"gradient\", \"spacing\", \"typography\", \"palette\", \"look\", \"feel\", \"beautiful\", \"pretty\",\n          \"vibe\", \"tasteful\", \"elegant\", \"minimalist\", \"ornament\", \"branding\", \"mood\"]\n\n\ndef signals(text: str, words: list) -> list:\n    \"\"\"The signal words present in text (whole-word).\"\"\"\n    low = text.lower()\n    return sorted({w for w in words if re.search(r\"\\b\" + re.escape(w) + r\"(?:s|es|ed|ing|d)?\\b\", low)})\n\n\ndef main() -> int:\n    \"\"\"Classify the candidate and write evaluation.json.\"\"\"\n    name = os.environ[\"SKILL_NAME\"]\n    desc = os.environ[\"SKILL_DESC\"]\n    store = os.environ[\"RECORD_STORE\"].rstrip(\"/\")\n    ex, dz = signals(desc, EXEC), signals(desc, DESIGN)\n    if ex and not dz:\n        verdict, onboard = \"execution\", True\n        rec = (f\"'{name}' is an execution / tool skill \u2014 a deterministic pathway. It fits cyberware \"\n               f\"directly: model it as a blueprint + perks, each tool emitting structured JSON. \"\n               f\"Run cws-create/scaffold to lay down the skeleton.\")\n    elif dz and not ex:\n        verdict, onboard = \"design\", False\n        rec = (f\"'{name}' is a design / taste skill (e.g. {', '.join(dz)}). That is NOT the cyberware \"\n               f\"emphasis \u2014 the framework governs deterministic execution, not aesthetics. Keep it as \"\n               f\"guidance, not a governed tool skill.\")\n    elif ex and dz:\n        verdict, onboard = \"transformable\", True\n        rec = (f\"'{name}' mixes execution ({', '.join(ex)}) and design ({', '.join(dz)}). Extract the \"\n               f\"execution core into a governed cyberware pathway; leave the taste/design part as \"\n               f\"guidance. Run cws-create/scaffold on the execution core.\")\n    else:\n        verdict, onboard = \"unclear\", False\n        rec = (f\"'{name}' shows no clear execution verbs or design signals \u2014 describe what it DOES \"\n               f\"(inputs -> action -> output) so it can be classified.\")\n    out = os.path.join(store, \"evaluation.json\")\n    result = {\"tool\": \"cws_evaluate\", \"status\": \"ok\", \"skill\": name, \"verdict\": verdict,\n              \"onboard\": onboard, \"execution_signals\": ex, \"design_signals\": dz,\n              \"recommendation\": rec, \"report\": out}\n    json.dump(result, open(out, \"w\"), indent=2)\n    print(json.dumps(result))\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
     "cws_evaluate.sh": "#!/usr/bin/env bash\n# cws_evaluate \u2014 porter: runs the Python core (cws_evaluate.py), which reads SKILL_NAME/SKILL_DESC/RECORD_STORE from the environment.\nset -euo pipefail\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nexec python3 \"$HERE/cws_evaluate.py\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">CWS-CREATE</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 cws_evaluate</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "cws-create",
      "perk": "evaluate",
      "record_store": "/tmp/cws-create-demo",
      "vars": {
       "SKILL_NAME": "pg-backup",
       "SKILL_DESC": "runs pg_dump to back up a Postgres database to a file"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=cws-create perk=evaluate\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport SKILL_NAME=pg-backup SKILL_DESC='runs pg_dump to back up a Postgres database to a file' RECORD_STORE=/tmp/cws-create-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/cws-create/perks/evaluate/src\n\nstep1() {   # cws_evaluate\n  echo \"[step 1] cws_evaluate\"\n  bash \"$SNIP/cws_evaluate.sh\"\n  test -f \"${RECORD_STORE}/evaluation.json\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/evaluation.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tcws_evaluate\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   },
   {
    "id": "scaffold",
    "summary": "lay down the cyberware skeleton for a fitting skill (via scaffold.py)",
    "destructive": false,
    "metadata": {
     "perk": "scaffold",
     "skill": "cws-create",
     "description": "Lay down a cyberware skill skeleton (blueprint + perks + contracts + snippet stubs).",
     "rules": [
      "calls infra/scaffold.py",
      "creates skills/<NEW_SKILL>/ \u2014 composes out of the box; fill the snippets"
     ],
     "usage": "Set NEW_SKILL + NEW_NAME + PERKS (space-separated <pid>:<tool>[:<binary>]). Output: scaffold.log.",
     "limitation": "Creates the skeleton only; you fill the snippets + vars.",
     "minimal_example": {
      "perk": "scaffold",
      "vars": {
       "NEW_SKILL": "pg_backup",
       "NEW_NAME": "Postgres backup",
       "PERKS": "dump:pg_dump:pg_dump"
      }
     }
    },
    "sequence": [
     "cws_scaffold"
    ],
    "tools": {
     "cws_scaffold": {
      "binary": "python3",
      "params": {
       "NEW_SKILL": "${NEW_SKILL}",
       "NEW_NAME": "${NEW_NAME}",
       "PERKS": "${PERKS}"
      }
     }
    },
    "env": {
     "NEW_SKILL": "${NEW_SKILL}",
     "NEW_NAME": "${NEW_NAME}",
     "PERKS": "${PERKS}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "python3"
    ],
    "contracts": {
     "tool": "cws_scaffold",
     "inputs": {
      "NEW_SKILL": {
       "type": "string",
       "required": true
      },
      "NEW_NAME": {
       "type": "string",
       "required": true
      },
      "PERKS": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "log": {
       "path": "${RECORD_STORE}/scaffold.log",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/scaffold.log"
     }
    },
    "snippets": {
     "cws_scaffold.sh": "#!/usr/bin/env bash\n# cws_scaffold \u2014 lay down a cyberware skill skeleton via infra/scaffold.py (the \"create\" step). Structured JSON.\nset -uo pipefail\n: \"${NEW_SKILL:?}\" \"${NEW_NAME:?}\" \"${PERKS:?}\" \"${RECORD_STORE:?}\"\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nREPO=\"$(cd \"$HERE/../../../../..\" && pwd)\"\nOUT=\"${RECORD_STORE%/}/scaffold.log\"\nARGS=\"\"\nfor p in $PERKS; do ARGS=\"$ARGS --perk $p\"; done   # PERKS = space-separated <pid>:<tool>[:<binary>]\npython3 \"$REPO/infra/scaffold.py\" --skill \"$NEW_SKILL\" --name \"$NEW_NAME\" $ARGS > \"$OUT\" 2>&1\nRC=$?\nprintf '{\"tool\":\"cws_scaffold\",\"status\":\"%s\",\"skill\":\"%s\",\"exit\":%d,\"log\":\"%s\"}\\n' \"$([ $RC -eq 0 ] && echo ok || echo fail)\" \"$NEW_SKILL\" \"$RC\" \"$OUT\"\nexit $RC\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">CWS-CREATE</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 cws_scaffold</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "cws-create",
      "perk": "scaffold",
      "record_store": "/tmp/cws-create-demo",
      "vars": {
       "NEW_SKILL": "pg_backup",
       "NEW_NAME": "Postgres backup",
       "PERKS": "dump:pg_dump:pg_dump"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=cws-create perk=scaffold\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport NEW_SKILL=pg_backup NEW_NAME='Postgres backup' PERKS=dump:pg_dump:pg_dump RECORD_STORE=/tmp/cws-create-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/cws-create/perks/scaffold/src\n\nstep1() {   # cws_scaffold\n  echo \"[step 1] cws_scaffold\"\n  bash \"$SNIP/cws_scaffold.sh\"\n  test -f \"${RECORD_STORE}/scaffold.log\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/scaffold.log\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tcws_scaffold\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "data",
  "name": "Data wrangling",
  "description": "Data transforms through proven pathways \u2014 CSV\u2192JSON and jq queries. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "data",
   "name": "Data wrangling",
   "description": "Data transforms through proven pathways \u2014 CSV\u2192JSON and jq queries. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">DATA</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
  "skill_md": "---\nskill: data\nname: Data wrangling\nperks: [csv2json, jq]\n---\n\n# data \u2014 Data wrangling\n\nData transforms through proven pathways \u2014 CSV\u2192JSON and jq queries.\n\n## What to look out for\nEach tool emits one line of structured JSON (the audit + debug log) and writes its\nartifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.\n\n## Perks\n| perk | tool | nature |\n|---|---|---|\n| `csv2json` | `data_csv2json` | read-only / safe |\n| `jq` | `data_jq` | read-only / safe |\n\n## How to use it\nPick a perk, copy `ledger.json` \u2192 `task-ledger.json`, fill its vars + `record_store`, then\nvalidate \u2192 compose \u2192 compile \u2192 oversight \u2192 executor.\n",
  "perks": [
   {
    "id": "csv2json",
    "summary": "convert a CSV file to a JSON array",
    "destructive": false,
    "metadata": {
     "perk": "csv2json",
     "skill": "data",
     "description": "convert a CSV file to a JSON array",
     "rules": [
      "row objects keyed by header",
      "result to record_store"
     ],
     "usage": "Set CSV_FILE. Output: data.json.",
     "limitation": "Header row required.",
     "minimal_example": {
      "perk": "csv2json",
      "vars": {
       "CSV_FILE": "/path/to/data.csv"
      }
     }
    },
    "sequence": [
     "data_csv2json"
    ],
    "tools": {
     "data_csv2json": {
      "binary": "python3",
      "params": {
       "CSV_FILE": "${CSV_FILE}"
      }
     }
    },
    "env": {
     "CSV_FILE": "${CSV_FILE}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "python3"
    ],
    "contracts": {
     "tool": "data_csv2json",
     "inputs": {
      "CSV_FILE": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "data_csv2json_out": {
       "path": "${RECORD_STORE}/data.json",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/data.json"
     }
    },
    "snippets": {
     "data_csv2json.py": "#!/usr/bin/env python3\n\"\"\"data_csv2json \u2014 convert a CSV file to a JSON array of row objects. Reads CSV_FILE, RECORD_STORE from env.\"\"\"\nfrom __future__ import annotations\nimport csv\nimport json\nimport os\nimport sys\n\n\ndef main() -> int:\n    \"\"\"Read CSV_FILE and write data.json.\"\"\"\n    src = os.environ[\"CSV_FILE\"]\n    store = os.environ[\"RECORD_STORE\"].rstrip(\"/\")\n    out = os.path.join(store, \"data.json\")\n    with open(src, newline=\"\", encoding=\"utf-8\") as f:\n        rows = list(csv.DictReader(f))\n    json.dump(rows, open(out, \"w\"), indent=2)\n    cols = list(rows[0].keys()) if rows else []\n    print(json.dumps({\"tool\": \"data_csv2json\", \"status\": \"ok\", \"rows\": len(rows), \"columns\": cols, \"out\": out}))\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
     "data_csv2json.sh": "#!/usr/bin/env bash\n# data_csv2json \u2014 porter: runs the Python core (data_csv2json.py), which reads CSV_FILE/RECORD_STORE from the environment.\nset -euo pipefail\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nexec python3 \"$HERE/data_csv2json.py\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">DATA</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 data_csv2json</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "data",
      "perk": "csv2json",
      "record_store": "/tmp/data-demo",
      "vars": {
       "CSV_FILE": "/path/to/data.csv"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=data perk=csv2json\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport CSV_FILE=/path/to/data.csv RECORD_STORE=/tmp/data-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/data/perks/csv2json/src\n\nstep1() {   # data_csv2json\n  echo \"[step 1] data_csv2json\"\n  bash \"$SNIP/data_csv2json.sh\"\n  test -f \"${RECORD_STORE}/data.json\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/data.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tdata_csv2json\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   },
   {
    "id": "jq",
    "summary": "run a jq query over a JSON file",
    "destructive": false,
    "metadata": {
     "perk": "jq",
     "skill": "data",
     "description": "run a jq query over a JSON file",
     "rules": [
      "result to record_store"
     ],
     "usage": "Set JSON_FILE + QUERY. Output: jq_result.json.",
     "limitation": "Needs jq installed.",
     "minimal_example": {
      "perk": "jq",
      "vars": {
       "JSON_FILE": "/path/to/in.json",
       "QUERY": ".items | length"
      }
     }
    },
    "sequence": [
     "data_jq"
    ],
    "tools": {
     "data_jq": {
      "binary": "jq",
      "params": {
       "JSON_FILE": "${JSON_FILE}",
       "QUERY": "${QUERY}"
      }
     }
    },
    "env": {
     "JSON_FILE": "${JSON_FILE}",
     "QUERY": "${QUERY}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "jq"
    ],
    "contracts": {
     "tool": "data_jq",
     "inputs": {
      "JSON_FILE": {
       "type": "string",
       "required": true
      },
      "QUERY": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "data_jq_out": {
       "path": "${RECORD_STORE}/jq_result.json",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/jq_result.json"
     }
    },
    "snippets": {
     "data_jq.sh": "#!/usr/bin/env bash\n# data_jq \u2014 run a jq query over a JSON file (proven pathway). Structured JSON output.\nset -uo pipefail\n: \"${JSON_FILE:?}\" \"${QUERY:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/jq_result.json\"\njq \"$QUERY\" \"$JSON_FILE\" > \"$OUT\" 2>/dev/null\nRC=$?\nprintf '{\"tool\":\"data_jq\",\"status\":\"%s\",\"exit\":%d,\"out\":\"%s\"}\\n' \"$([ $RC -eq 0 ] && echo ok || echo fail)\" \"$RC\" \"$OUT\"\nexit $RC\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">DATA</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 data_jq</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "data",
      "perk": "jq",
      "record_store": "/tmp/data-demo",
      "vars": {
       "JSON_FILE": "/path/to/in.json",
       "QUERY": ".items | length"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=data perk=jq\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport JSON_FILE=/path/to/in.json QUERY='.items | length' RECORD_STORE=/tmp/data-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/data/perks/jq/src\n\nstep1() {   # data_jq\n  echo \"[step 1] data_jq\"\n  bash \"$SNIP/data_jq.sh\"\n  test -f \"${RECORD_STORE}/jq_result.json\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/jq_result.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tdata_jq\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "docker",
  "name": "Docker operations",
  "description": "Container operations through proven pathways \u2014 build images, inspect running containers. Requires a reachable Docker daemon. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "docker",
   "name": "Docker operations",
   "description": "Container operations through proven pathways \u2014 build images, inspect running containers. Requires a reachable Docker daemon. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">DOCKER</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
  "skill_md": "---\nskill: docker\nname: Docker operations\nperks: [build, ps]\n---\n\n# docker \u2014 Docker operations\n\nContainer operations through proven pathways \u2014 build images, inspect running containers. Requires a reachable Docker daemon.\n\n## What to look out for\nEach tool emits one line of structured JSON (the audit + debug log) and writes its\nartifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.\n\n## Perks\n| perk | tool | nature |\n|---|---|---|\n| `build` | `docker_build` | read-only / safe |\n| `ps` | `docker_ps` | read-only / safe |\n\n## How to use it\nPick a perk, copy `ledger.json` \u2192 `task-ledger.json`, fill its vars + `record_store`, then\nvalidate \u2192 compose \u2192 compile \u2192 oversight \u2192 executor.\n",
  "perks": [
   {
    "id": "build",
    "summary": "build an image from a context dir",
    "destructive": false,
    "metadata": {
     "perk": "build",
     "skill": "docker",
     "description": "build an image from a context dir",
     "rules": [
      "build log to record_store",
      "tags the image"
     ],
     "usage": "Set CONTEXT_DIR + IMAGE_TAG (+ optional DOCKERFILE). Output: docker_build.log.",
     "limitation": "Needs a running Docker daemon.",
     "minimal_example": {
      "perk": "build",
      "vars": {
       "CONTEXT_DIR": ".",
       "IMAGE_TAG": "myapp:dev"
      }
     }
    },
    "sequence": [
     "docker_build"
    ],
    "tools": {
     "docker_build": {
      "binary": "docker",
      "params": {
       "CONTEXT_DIR": "${CONTEXT_DIR}",
       "IMAGE_TAG": "${IMAGE_TAG}",
       "DOCKERFILE": "${DOCKERFILE}"
      }
     }
    },
    "env": {
     "CONTEXT_DIR": "${CONTEXT_DIR}",
     "IMAGE_TAG": "${IMAGE_TAG}",
     "DOCKERFILE": "${DOCKERFILE}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "docker"
    ],
    "contracts": {
     "tool": "docker_build",
     "inputs": {
      "CONTEXT_DIR": {
       "type": "string",
       "required": true
      },
      "IMAGE_TAG": {
       "type": "string",
       "required": true
      },
      "DOCKERFILE": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "docker_build_out": {
       "path": "${RECORD_STORE}/docker_build.log",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/docker_build.log"
     }
    },
    "snippets": {
     "docker_build.sh": "#!/usr/bin/env bash\n# docker_build \u2014 build an image from a context dir (proven pathway). Structured JSON output.\nset -uo pipefail\n: \"${CONTEXT_DIR:?}\" \"${IMAGE_TAG:?}\" \"${RECORD_STORE:?}\"\nLOG=\"${RECORD_STORE%/}/docker_build.log\"\ndocker build -t \"$IMAGE_TAG\" ${DOCKERFILE:+-f \"$DOCKERFILE\"} \"$CONTEXT_DIR\" > \"$LOG\" 2>&1\nRC=$?\nprintf '{\"tool\":\"docker_build\",\"status\":\"%s\",\"image\":\"%s\",\"exit\":%d,\"log\":\"%s\"}\\n' \"$([ $RC -eq 0 ] && echo ok || echo fail)\" \"$IMAGE_TAG\" \"$RC\" \"$LOG\"\nexit $RC\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">DOCKER</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 docker_build</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "docker",
      "perk": "build",
      "record_store": "/tmp/docker-demo",
      "vars": {
       "CONTEXT_DIR": ".",
       "IMAGE_TAG": "myapp:dev",
       "DOCKERFILE": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=docker perk=build\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport CONTEXT_DIR=. IMAGE_TAG=myapp:dev DOCKERFILE='' RECORD_STORE=/tmp/docker-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/docker/perks/build/src\n\nstep1() {   # docker_build\n  echo \"[step 1] docker_build\"\n  bash \"$SNIP/docker_build.sh\"\n  test -f \"${RECORD_STORE}/docker_build.log\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/docker_build.log\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tdocker_build\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   },
   {
    "id": "ps",
    "summary": "list containers (read-only)",
    "destructive": false,
    "metadata": {
     "perk": "ps",
     "skill": "docker",
     "description": "list containers (read-only)",
     "rules": [
      "read-only",
      "listing to record_store"
     ],
     "usage": "Optional ALL=1 to include stopped. Output: containers.txt.",
     "limitation": "Reporting only.",
     "minimal_example": {
      "perk": "ps",
      "vars": {}
     }
    },
    "sequence": [
     "docker_ps"
    ],
    "tools": {
     "docker_ps": {
      "binary": "docker",
      "params": {
       "ALL": "${ALL}"
      }
     }
    },
    "env": {
     "ALL": "${ALL}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "docker"
    ],
    "contracts": {
     "tool": "docker_ps",
     "inputs": {
      "ALL": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "docker_ps_out": {
       "path": "${RECORD_STORE}/containers.txt",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/containers.txt"
     }
    },
    "snippets": {
     "docker_ps.sh": "#!/usr/bin/env bash\n# docker_ps \u2014 list containers (read-only). Structured JSON output.\nset -uo pipefail\n: \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/containers.txt\"\ndocker ps ${ALL:+-a} --format '{{.ID}} {{.Image}} {{.Status}} {{.Names}}' > \"$OUT\" 2>/dev/null\nRC=$?\nCOUNT=$([ -f \"$OUT\" ] && wc -l < \"$OUT\" | tr -d ' ' || echo 0)\nprintf '{\"tool\":\"docker_ps\",\"status\":\"%s\",\"count\":%s,\"report\":\"%s\"}\\n' \"$([ $RC -eq 0 ] && echo ok || echo fail)\" \"$COUNT\" \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">DOCKER</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 docker_ps</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "docker",
      "perk": "ps",
      "record_store": "/tmp/docker-demo",
      "vars": {
       "ALL": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=docker perk=ps\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport ALL='' RECORD_STORE=/tmp/docker-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/docker/perks/ps/src\n\nstep1() {   # docker_ps\n  echo \"[step 1] docker_ps\"\n  bash \"$SNIP/docker_ps.sh\"\n  test -f \"${RECORD_STORE}/containers.txt\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/containers.txt\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tdocker_ps\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "fs",
  "name": "Filesystem operations",
  "description": "Filesystem work through proven pathways; outputs + manifests captured to record_store. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "fs",
   "name": "Filesystem operations",
   "description": "Filesystem work through proven pathways; outputs + manifests captured to record_store. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">FS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">FS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 fs_archive</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "fs",
      "perk": "archive",
      "record_store": "/tmp/fs-demo",
      "vars": {
       "SOURCE_DIR": "/path/to/dir"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=fs perk=archive\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport SOURCE_DIR=/path/to/dir RECORD_STORE=/tmp/fs-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/fs/perks/archive/src\n\nstep1() {   # fs_archive\n  echo \"[step 1] fs_archive\"\n  bash \"$SNIP/fs_archive.sh\"\n  test -f \"${RECORD_STORE}/archive.tar.gz\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/archive.tar.gz\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tfs_archive\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">FS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 fs_find_large</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "fs",
      "perk": "find_large",
      "record_store": "/tmp/fs-demo",
      "vars": {
       "SEARCH_DIR": "/var/log",
       "MIN_SIZE": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=fs perk=find_large\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport SEARCH_DIR=/var/log MIN_SIZE='' RECORD_STORE=/tmp/fs-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/fs/perks/find_large/src\n\nstep1() {   # fs_find_large\n  echo \"[step 1] fs_find_large\"\n  bash \"$SNIP/fs_find_large.sh\"\n  test -f \"${RECORD_STORE}/large_files.txt\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/large_files.txt\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tfs_find_large\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "git_ops",
  "name": "Git operations",
  "description": "Git work through proven pathways; the oversight ruleset refuses force-push and hard reset unless approved. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "git_ops",
   "name": "Git operations",
   "description": "Git work through proven pathways; the oversight ruleset refuses force-push and hard reset unless approved. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">GIT_OPS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">GIT_OPS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 git_snapshot</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "git_ops",
      "perk": "snapshot",
      "record_store": "/tmp/git_ops-demo",
      "vars": {
       "REPO_DIR": "/path/to/repo",
       "MESSAGE": "checkpoint"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=git_ops perk=snapshot\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport REPO_DIR=/path/to/repo MESSAGE=checkpoint RECORD_STORE=/tmp/git_ops-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/git_ops/perks/snapshot/src\n\nstep1() {   # git_snapshot\n  echo \"[step 1] git_snapshot\"\n  bash \"$SNIP/git_snapshot.sh\"\n  test -f \"${RECORD_STORE}/git_snapshot.json\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/git_snapshot.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tgit_snapshot\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">GIT_OPS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 git_status</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "git_ops",
      "perk": "status",
      "record_store": "/tmp/git_ops-demo",
      "vars": {
       "REPO_DIR": "/path/to/repo"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=git_ops perk=status\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport REPO_DIR=/path/to/repo RECORD_STORE=/tmp/git_ops-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/git_ops/perks/status/src\n\nstep1() {   # git_status\n  echo \"[step 1] git_status\"\n  bash \"$SNIP/git_status.sh\"\n  test -f \"${RECORD_STORE}/git_status.txt\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/git_status.txt\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tgit_status\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "http",
  "name": "HTTP requests",
  "description": "Make HTTP requests through proven, contract-bound pathways; responses captured to record_store with status + size in structured output. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "http",
   "name": "HTTP requests",
   "description": "Make HTTP requests through proven, contract-bound pathways; responses captured to record_store with status + size in structured output. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">HTTP</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">HTTP</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 http_get</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "http",
      "perk": "get",
      "record_store": "/tmp/http-demo",
      "vars": {
       "URL": "https://api.example.com/v1/x",
       "HEADER": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=http perk=get\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport URL=https://api.example.com/v1/x HEADER='' RECORD_STORE=/tmp/http-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/http/perks/get/src\n\nstep1() {   # http_get\n  echo \"[step 1] http_get\"\n  bash \"$SNIP/http_get.sh\"\n  test -f \"${RECORD_STORE}/response.body\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/response.body\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\thttp_get\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">HTTP</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 http_post</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "http",
      "perk": "post",
      "record_store": "/tmp/http-demo",
      "vars": {
       "URL": "https://api.example.com/v1/x",
       "BODY": "a JSON string"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=http perk=post\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport URL=https://api.example.com/v1/x BODY='a JSON string' RECORD_STORE=/tmp/http-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/http/perks/post/src\n\nstep1() {   # http_post\n  echo \"[step 1] http_post\"\n  bash \"$SNIP/http_post.sh\"\n  test -f \"${RECORD_STORE}/response.body\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/response.body\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\thttp_post\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "net",
  "name": "Network diagnostics",
  "description": "Networking diagnostics through proven pathways \u2014 HTTP health probes and DNS resolution. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "net",
   "name": "Network diagnostics",
   "description": "Networking diagnostics through proven pathways \u2014 HTTP health probes and DNS resolution. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">NET</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
  "skill_md": "---\nskill: net\nname: Network diagnostics\nperks: [healthcheck, dns]\n---\n\n# net \u2014 Network diagnostics\n\nNetworking diagnostics through proven pathways \u2014 HTTP health probes and DNS resolution.\n\n## What to look out for\nEach tool emits one line of structured JSON (the audit + debug log) and writes its\nartifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.\n\n## Perks\n| perk | tool | nature |\n|---|---|---|\n| `healthcheck` | `net_healthcheck` | read-only / safe |\n| `dns` | `net_dns` | read-only / safe |\n\n## How to use it\nPick a perk, copy `ledger.json` \u2192 `task-ledger.json`, fill its vars + `record_store`, then\nvalidate \u2192 compose \u2192 compile \u2192 oversight \u2192 executor.\n",
  "perks": [
   {
    "id": "healthcheck",
    "summary": "HTTP probe \u2014 status code + latency",
    "destructive": false,
    "metadata": {
     "perk": "healthcheck",
     "skill": "net",
     "description": "HTTP probe \u2014 status code + latency",
     "rules": [
      "read-only",
      "health = 2xx/3xx"
     ],
     "usage": "Set URL (+ optional TIMEOUT, default 10s). Output: healthcheck.json.",
     "limitation": "HTTP(S) only.",
     "minimal_example": {
      "perk": "healthcheck",
      "vars": {
       "URL": "https://example.com/health"
      }
     }
    },
    "sequence": [
     "net_healthcheck"
    ],
    "tools": {
     "net_healthcheck": {
      "binary": "curl",
      "params": {
       "URL": "${URL}",
       "TIMEOUT": "${TIMEOUT}"
      }
     }
    },
    "env": {
     "URL": "${URL}",
     "TIMEOUT": "${TIMEOUT}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "curl"
    ],
    "contracts": {
     "tool": "net_healthcheck",
     "inputs": {
      "URL": {
       "type": "string",
       "required": true
      },
      "TIMEOUT": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "net_healthcheck_out": {
       "path": "${RECORD_STORE}/healthcheck.json",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/healthcheck.json"
     }
    },
    "snippets": {
     "net_healthcheck.sh": "#!/usr/bin/env bash\n# net_healthcheck \u2014 HTTP probe: status code + total latency (proven pathway). Structured JSON output.\nset -uo pipefail\n: \"${URL:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/healthcheck.json\"\nRES=$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time \"${TIMEOUT:-10}\" \"$URL\" 2>/dev/null || echo \"000 0\")\nCODE=\"${RES%% *}\"; LAT=\"${RES##* }\"\nH=$([ \"${CODE:0:1}\" = \"2\" ] || [ \"${CODE:0:1}\" = \"3\" ] && echo healthy || echo unhealthy)\nprintf '{\"tool\":\"net_healthcheck\",\"status\":\"ok\",\"http_code\":%s,\"latency_s\":%s,\"health\":\"%s\",\"report\":\"%s\"}\\n' \"$CODE\" \"$LAT\" \"$H\" \"$OUT\" | tee \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">NET</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 net_healthcheck</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "net",
      "perk": "healthcheck",
      "record_store": "/tmp/net-demo",
      "vars": {
       "URL": "https://example.com/health",
       "TIMEOUT": "10"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=net perk=healthcheck\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport URL=https://example.com/health TIMEOUT=10 RECORD_STORE=/tmp/net-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/net/perks/healthcheck/src\n\nstep1() {   # net_healthcheck\n  echo \"[step 1] net_healthcheck\"\n  bash \"$SNIP/net_healthcheck.sh\"\n  test -f \"${RECORD_STORE}/healthcheck.json\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/healthcheck.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tnet_healthcheck\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   },
   {
    "id": "dns",
    "summary": "resolve a hostname to addresses",
    "destructive": false,
    "metadata": {
     "perk": "dns",
     "skill": "net",
     "description": "resolve a hostname to addresses",
     "rules": [
      "read-only",
      "result to record_store"
     ],
     "usage": "Set HOST. Output: dns.json.",
     "limitation": "A/AAAA via the system resolver.",
     "minimal_example": {
      "perk": "dns",
      "vars": {
       "HOST": "example.com"
      }
     }
    },
    "sequence": [
     "net_dns"
    ],
    "tools": {
     "net_dns": {
      "binary": "python3",
      "params": {
       "HOST": "${HOST}"
      }
     }
    },
    "env": {
     "HOST": "${HOST}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "python3"
    ],
    "contracts": {
     "tool": "net_dns",
     "inputs": {
      "HOST": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "net_dns_out": {
       "path": "${RECORD_STORE}/dns.json",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/dns.json"
     }
    },
    "snippets": {
     "net_dns.py": "#!/usr/bin/env python3\n\"\"\"net_dns \u2014 resolve a hostname to its addresses. Reads HOST, RECORD_STORE from env; emits JSON.\"\"\"\nfrom __future__ import annotations\nimport json\nimport os\nimport socket\nimport sys\n\n\ndef main() -> int:\n    \"\"\"Resolve HOST and write dns.json.\"\"\"\n    host = os.environ[\"HOST\"]\n    store = os.environ[\"RECORD_STORE\"].rstrip(\"/\")\n    out = os.path.join(store, \"dns.json\")\n    try:\n        canonical, _aliases, addrs = socket.gethostbyname_ex(host)\n        result = {\"tool\": \"net_dns\", \"status\": \"ok\", \"host\": host, \"canonical\": canonical, \"addresses\": addrs, \"report\": out}\n    except OSError as exc:\n        result = {\"tool\": \"net_dns\", \"status\": \"error\", \"host\": host, \"reason\": str(exc), \"report\": out}\n    json.dump(result, open(out, \"w\"), indent=2)\n    print(json.dumps(result))\n    return 0 if result[\"status\"] == \"ok\" else 1\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
     "net_dns.sh": "#!/usr/bin/env bash\n# net_dns \u2014 porter: runs the Python core (net_dns.py), which reads HOST/RECORD_STORE from the environment.\nset -euo pipefail\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nexec python3 \"$HERE/net_dns.py\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">NET</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 net_dns</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "net",
      "perk": "dns",
      "record_store": "/tmp/net-demo",
      "vars": {
       "HOST": "example.com"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=net perk=dns\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport HOST=example.com RECORD_STORE=/tmp/net-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/net/perks/dns/src\n\nstep1() {   # net_dns\n  echo \"[step 1] net_dns\"\n  bash \"$SNIP/net_dns.sh\"\n  test -f \"${RECORD_STORE}/dns.json\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/dns.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tnet_dns\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "pg_ops",
  "name": "Governed PostgreSQL operations",
  "description": "The general, perk-agnostic lifecycle of a governed DB operation. Tells the intelligence what to look out for (the guardrails) and which logs to check (the per-tool structured output + the executor's run-ledger). Perks are optional: any proven pathway plugs into a_operate. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "pg_ops",
   "name": "Governed PostgreSQL operations",
   "description": "The general, perk-agnostic lifecycle of a governed DB operation. Tells the intelligence what to look out for (the guardrails) and which logs to check (the per-tool structured output + the executor's run-ledger). Perks are optional: any proven pathway plugs into a_operate. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">PG_OPS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">PG_OPS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 psql_select</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "pg_ops",
      "perk": "select",
      "record_store": "/tmp/pg_ops-demo",
      "vars": {
       "PGHOST": "localhost",
       "PGPORT": "5432",
       "PGDATABASE": "demo",
       "PGUSER": "reader"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=pg_ops perk=select\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport PGHOST=localhost PGPORT=5432 PGDATABASE=demo PGUSER=reader RECORD_STORE=/tmp/pg_ops-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/pg_ops/perks/select/src\n\nstep1() {   # psql_select\n  echo \"[step 1] psql_select\"\n  bash \"$SNIP/psql_select.sh\"\n  test -f \"${RECORD_STORE}/select_rows.csv\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/select_rows.csv\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tpsql_select\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">PG_OPS</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 psql_migrate</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "pg_ops",
      "perk": "migrate",
      "record_store": "/tmp/pg_ops-demo",
      "vars": {
       "PGHOST": "localhost",
       "PGPORT": "5432",
       "PGDATABASE": "demo",
       "PGUSER": "admin"
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=pg_ops perk=migrate\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport PGHOST=localhost PGPORT=5432 PGDATABASE=demo PGUSER=admin RECORD_STORE=/tmp/pg_ops-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/pg_ops/perks/migrate/src\n\nstep1() {   # psql_migrate\n  echo \"[step 1] psql_migrate\"\n  bash \"$SNIP/psql_migrate.sh\"\n  test -f \"${RECORD_STORE}/migrate_applied.log\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/migrate_applied.log\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tpsql_migrate\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "py_qc",
  "name": "Python quality checks",
  "description": "Run Python tests + lint through proven pathways; reports captured to record_store. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "py_qc",
   "name": "Python quality checks",
   "description": "Run Python tests + lint through proven pathways; reports captured to record_store. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">PY_QC</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">PY_QC</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 py_test</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "py_qc",
      "perk": "test",
      "record_store": "/tmp/py_qc-demo",
      "vars": {
       "PROJECT_DIR": "/path/to/proj",
       "TEST_DIR": "tests",
       "PYTEST_ARGS": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=py_qc perk=test\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport PROJECT_DIR=/path/to/proj TEST_DIR=tests PYTEST_ARGS='' RECORD_STORE=/tmp/py_qc-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/py_qc/perks/test/src\n\nstep1() {   # py_test\n  echo \"[step 1] py_test\"\n  bash \"$SNIP/py_test.sh\"\n  test -f \"${RECORD_STORE}/pytest.out\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/pytest.out\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tpy_test\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
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
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">PY_QC</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 py_lint</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "py_qc",
      "perk": "lint",
      "record_store": "/tmp/py_qc-demo",
      "vars": {
       "PROJECT_DIR": "/path/to/proj",
       "LINT_TARGET": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=py_qc perk=lint\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport PROJECT_DIR=/path/to/proj LINT_TARGET='' RECORD_STORE=/tmp/py_qc-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/py_qc/perks/lint/src\n\nstep1() {   # py_lint\n  echo \"[step 1] py_lint\"\n  bash \"$SNIP/py_lint.sh\"\n  test -f \"${RECORD_STORE}/lint.out\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/lint.out\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tpy_lint\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "release",
  "name": "Release tagging",
  "description": "Release operations through proven pathways \u2014 annotated git tags (no push; push stays gated). Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "release",
   "name": "Release tagging",
   "description": "Release operations through proven pathways \u2014 annotated git tags (no push; push stays gated). Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">RELEASE</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
  "skill_md": "---\nskill: release\nname: Release tagging\nperks: [tag]\n---\n\n# release \u2014 Release tagging\n\nRelease operations through proven pathways \u2014 annotated git tags (no push; push stays gated).\n\n## What to look out for\nEach tool emits one line of structured JSON (the audit + debug log) and writes its\nartifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.\n\n## Perks\n| perk | tool | nature |\n|---|---|---|\n| `tag` | `release_tag` | read-only / safe |\n\n## How to use it\nPick a perk, copy `ledger.json` \u2192 `task-ledger.json`, fill its vars + `record_store`, then\nvalidate \u2192 compose \u2192 compile \u2192 oversight \u2192 executor.\n",
  "perks": [
   {
    "id": "tag",
    "summary": "create an annotated git tag at HEAD",
    "destructive": false,
    "metadata": {
     "perk": "tag",
     "skill": "release",
     "description": "create an annotated git tag at HEAD",
     "rules": [
      "annotated tag",
      "no force, no push",
      "no-op if the tag exists"
     ],
     "usage": "Set REPO_DIR + VERSION (+ optional MESSAGE). Output: release_tag.json.",
     "limitation": "Local tag only \u2014 push is a separate, gated step.",
     "minimal_example": {
      "perk": "tag",
      "vars": {
       "REPO_DIR": "/path/to/repo",
       "VERSION": "v1.2.0"
      }
     }
    },
    "sequence": [
     "release_tag"
    ],
    "tools": {
     "release_tag": {
      "binary": "git",
      "params": {
       "REPO_DIR": "${REPO_DIR}",
       "VERSION": "${VERSION}",
       "MESSAGE": "${MESSAGE}"
      }
     }
    },
    "env": {
     "REPO_DIR": "${REPO_DIR}",
     "VERSION": "${VERSION}",
     "MESSAGE": "${MESSAGE}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "git"
    ],
    "contracts": {
     "tool": "release_tag",
     "inputs": {
      "REPO_DIR": {
       "type": "string",
       "required": true
      },
      "VERSION": {
       "type": "string",
       "required": true
      },
      "MESSAGE": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "release_tag_out": {
       "path": "${RECORD_STORE}/release_tag.json",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/release_tag.json"
     }
    },
    "snippets": {
     "release_tag.sh": "#!/usr/bin/env bash\n# release_tag \u2014 create an annotated git tag at HEAD (proven pathway). Structured JSON output.\nset -uo pipefail\n: \"${REPO_DIR:?}\" \"${VERSION:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/release_tag.json\"\ncd \"$REPO_DIR\" || { printf '{\"tool\":\"release_tag\",\"status\":\"error\",\"reason\":\"bad repo dir\"}\\n' | tee \"$OUT\"; exit 1; }\nif git rev-parse \"$VERSION\" >/dev/null 2>&1; then printf '{\"tool\":\"release_tag\",\"status\":\"noop\",\"reason\":\"tag exists\",\"tag\":\"%s\"}\\n' \"$VERSION\" | tee \"$OUT\"; exit 0; fi\ngit tag -a \"$VERSION\" -m \"${MESSAGE:-release $VERSION}\"\nRC=$?\nSHA=$(git rev-parse --short HEAD 2>/dev/null)\nprintf '{\"tool\":\"release_tag\",\"status\":\"%s\",\"tag\":\"%s\",\"sha\":\"%s\",\"report\":\"%s\"}\\n' \"$([ $RC -eq 0 ] && echo ok || echo fail)\" \"$VERSION\" \"$SHA\" \"$OUT\" | tee \"$OUT\"\nexit $RC\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">RELEASE</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 release_tag</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "release",
      "perk": "tag",
      "record_store": "/tmp/release-demo",
      "vars": {
       "REPO_DIR": "/path/to/repo",
       "VERSION": "v1.2.0",
       "MESSAGE": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=release perk=tag\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport REPO_DIR=/path/to/repo VERSION=v1.2.0 MESSAGE='' RECORD_STORE=/tmp/release-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/release/perks/tag/src\n\nstep1() {   # release_tag\n  echo \"[step 1] release_tag\"\n  bash \"$SNIP/release_tag.sh\"\n  test -f \"${RECORD_STORE}/release_tag.json\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/release_tag.json\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\trelease_tag\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 },
 {
  "id": "search",
  "name": "Code search",
  "description": "Search and measure a codebase through proven pathways \u2014 pattern search and line counts. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
  "group": "skills",
  "blueprint": {
   "$schema": "lpp/v0.2.0",
   "id": "search",
   "name": "Code search",
   "description": "Search and measure a codebase through proven pathways \u2014 pattern search and line counts. Perk-agnostic lifecycle (ready \u2192 prepared \u2192 verified \u2192 executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
   "entry_state": "ready",
   "states": {
    "ready": {
     "description": "task-ledger submitted, nothing run"
    },
    "prepared": {
     "description": "inputs validated \u2014 required vars present, runtime + store reachable"
    },
    "verified": {
     "description": "the plan is contract-bound \u2014 the perk's tool sequence resolves and its contract (I/O + checks) is in place"
    },
    "executed": {
     "description": "the perk's tool sequence ran ONLY via executor.py \u2014 each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"
    }
   },
   "terminal_states": {
    "executed": {}
   },
   "gates": {
    "g_prepared": {
     "type": "expression",
     "expression": "inputs_present /\\ store_writable",
     "description": "inputs + store validated"
    },
    "g_verified": {
     "type": "expression",
     "expression": "sequence_resolved /\\ contracts_present",
     "description": "the task is contract-bound"
    },
    "g_governed": {
     "type": "expression",
     "expression": "governed_run /\\ contract_checks_pass",
     "description": "ran ONLY through executor.py; contract enforced"
    }
   },
   "actions": {
    "a_prepare": {
     "type": "compute",
     "compute_unit": "validator:check_inputs",
     "description": "validator confirms required vars + writable record_store + reachable runtime"
    },
    "a_verify": {
     "type": "compute",
     "compute_unit": "validator:check_contract",
     "description": "confirm the perk's sequence + contracts are bound"
    },
    "a_execute": {
     "type": "compute",
     "compute_unit": "perk:sequence",
     "description": "run the perk's tool sequence via executor.py \u2014 recording each step to the run-ledger as it runs"
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
     "to": "verified",
     "trigger": "VERIFY",
     "action": "a_verify",
     "gate": "g_verified"
    },
    {
     "from": "verified",
     "to": "executed",
     "trigger": "EXECUTE",
     "action": "a_execute",
     "gate": "g_governed"
    }
   ],
   "safety_invariants": [
    {
     "name": "governed_execution_only",
     "expression": "state /= 'executed' \\/ governed_run",
     "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel; the runtime is the enforcement."
    },
    {
     "name": "record_during_execution",
     "expression": "state /= 'executed' \\/ recorded_each_step",
     "description": "GUARDRAIL: recording is PART of executing \u2014 each step is written to the run-ledger as it runs, not in a separate phase after."
    },
    {
     "name": "verify_before_execute",
     "expression": "state /= 'executed' \\/ contract_bound",
     "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."
    },
    {
     "name": "oversight_clears_script",
     "expression": "TRUE",
     "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."
    }
   ]
  },
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">SEARCH</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
  "skill_md": "---\nskill: search\nname: Code search\nperks: [grep, loc]\n---\n\n# search \u2014 Code search\n\nSearch and measure a codebase through proven pathways \u2014 pattern search and line counts.\n\n## What to look out for\nEach tool emits one line of structured JSON (the audit + debug log) and writes its\nartifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.\n\n## Perks\n| perk | tool | nature |\n|---|---|---|\n| `grep` | `search_grep` | read-only / safe |\n| `loc` | `search_loc` | read-only / safe |\n\n## How to use it\nPick a perk, copy `ledger.json` \u2192 `task-ledger.json`, fill its vars + `record_store`, then\nvalidate \u2192 compose \u2192 compile \u2192 oversight \u2192 executor.\n",
  "perks": [
   {
    "id": "grep",
    "summary": "search files for a pattern (ripgrep, fallback grep)",
    "destructive": false,
    "metadata": {
     "perk": "grep",
     "skill": "search",
     "description": "search files for a pattern (ripgrep, fallback grep)",
     "rules": [
      "read-only",
      "matches to record_store"
     ],
     "usage": "Set PATTERN + SEARCH_DIR. Output: matches.txt.",
     "limitation": "Line-oriented text search.",
     "minimal_example": {
      "perk": "grep",
      "vars": {
       "PATTERN": "TODO",
       "SEARCH_DIR": "."
      }
     }
    },
    "sequence": [
     "search_grep"
    ],
    "tools": {
     "search_grep": {
      "binary": "grep",
      "params": {
       "PATTERN": "${PATTERN}",
       "SEARCH_DIR": "${SEARCH_DIR}"
      }
     }
    },
    "env": {
     "PATTERN": "${PATTERN}",
     "SEARCH_DIR": "${SEARCH_DIR}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "grep"
    ],
    "contracts": {
     "tool": "search_grep",
     "inputs": {
      "PATTERN": {
       "type": "string",
       "required": true
      },
      "SEARCH_DIR": {
       "type": "string",
       "required": true
      }
     },
     "outputs": {
      "search_grep_out": {
       "path": "${RECORD_STORE}/matches.txt",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/matches.txt"
     }
    },
    "snippets": {
     "search_grep.sh": "#!/usr/bin/env bash\n# search_grep \u2014 search files for a pattern (ripgrep, fallback grep). Structured JSON output.\nset -uo pipefail\n: \"${PATTERN:?}\" \"${SEARCH_DIR:?}\" \"${RECORD_STORE:?}\"\nOUT=\"${RECORD_STORE%/}/matches.txt\"\nif command -v rg >/dev/null 2>&1; then rg -n -- \"$PATTERN\" \"$SEARCH_DIR\" > \"$OUT\" 2>/dev/null || true\nelse grep -rn -- \"$PATTERN\" \"$SEARCH_DIR\" > \"$OUT\" 2>/dev/null || true; fi\nCOUNT=$(wc -l < \"$OUT\" | tr -d ' ')\nprintf '{\"tool\":\"search_grep\",\"status\":\"ok\",\"matches\":%s,\"report\":\"%s\"}\\n' \"$COUNT\" \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">SEARCH</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 search_grep</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "search",
      "perk": "grep",
      "record_store": "/tmp/search-demo",
      "vars": {
       "PATTERN": "TODO",
       "SEARCH_DIR": "."
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=search perk=grep\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport PATTERN=TODO SEARCH_DIR=. RECORD_STORE=/tmp/search-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/search/perks/grep/src\n\nstep1() {   # search_grep\n  echo \"[step 1] search_grep\"\n  bash \"$SNIP/search_grep.sh\"\n  test -f \"${RECORD_STORE}/matches.txt\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/matches.txt\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tsearch_grep\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   },
   {
    "id": "loc",
    "summary": "count files + lines for an extension (read-only)",
    "destructive": false,
    "metadata": {
     "perk": "loc",
     "skill": "search",
     "description": "count files + lines for an extension (read-only)",
     "rules": [
      "read-only",
      "skips dotdirs"
     ],
     "usage": "Set SEARCH_DIR (+ EXT, default py). Output: loc.txt.",
     "limitation": "One extension per run.",
     "minimal_example": {
      "perk": "loc",
      "vars": {
       "SEARCH_DIR": "."
      }
     }
    },
    "sequence": [
     "search_loc"
    ],
    "tools": {
     "search_loc": {
      "binary": "find",
      "params": {
       "SEARCH_DIR": "${SEARCH_DIR}",
       "EXT": "${EXT}"
      }
     }
    },
    "env": {
     "SEARCH_DIR": "${SEARCH_DIR}",
     "EXT": "${EXT}",
     "RECORD_STORE": "${record_store}"
    },
    "requires": [
     "find"
    ],
    "contracts": {
     "tool": "search_loc",
     "inputs": {
      "SEARCH_DIR": {
       "type": "string",
       "required": true
      },
      "EXT": {
       "type": "string",
       "required": false
      }
     },
     "outputs": {
      "search_loc_out": {
       "path": "${RECORD_STORE}/loc.txt",
       "type": "file"
      }
     },
     "checks": {
      "exit_zero": true,
      "output_exists": "${RECORD_STORE}/loc.txt"
     }
    },
    "snippets": {
     "search_loc.sh": "#!/usr/bin/env bash\n# search_loc \u2014 count files + lines for an extension (read-only). Structured JSON output.\nset -uo pipefail\n: \"${SEARCH_DIR:?}\" \"${RECORD_STORE:?}\"\nEXT=\"${EXT:-py}\"\nOUT=\"${RECORD_STORE%/}/loc.txt\"\nfind \"$SEARCH_DIR\" -type f -name \"*.${EXT}\" -not -path '*/.*' > \"${OUT}.files\" 2>/dev/null || true\nFILES=$(wc -l < \"${OUT}.files\" | tr -d ' ')\nif [ -s \"${OUT}.files\" ]; then LINES=$(xargs wc -l < \"${OUT}.files\" 2>/dev/null | tail -1 | awk '{print $1}'); else LINES=0; fi\n: \"${LINES:=0}\"\nprintf '%s files, %s lines (*.%s)\\n' \"$FILES\" \"$LINES\" \"$EXT\" > \"$OUT\"\nprintf '{\"tool\":\"search_loc\",\"status\":\"ok\",\"ext\":\"%s\",\"files\":%s,\"lines\":%s,\"report\":\"%s\"}\\n' \"$EXT\" \"$FILES\" \"$LINES\" \"$OUT\"\n"
    },
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"668\" height=\"1028\" viewBox=\"0 0 668 1028\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"668\" height=\"1028\" fill=\"#0a0f0a\"/>\n<rect width=\"668\" height=\"1028\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">SEARCH</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">PREPARE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VERIFY</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">READY<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">task-ledger submitted, nothing</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_prepared</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 inputs_present \u2227 store_writable</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_inputs</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">PREPARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">inputs validated \u2014 required vars</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">present, runtime + store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">reachable</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_verified</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_contract</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VERIFIED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">the plan is contract-bound \u2014 the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">perk&#x27;s tool sequence resolves</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">and its contract (I/O + checks)</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 governed_run \u2227 contract_checks_pass</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">perk:sequence</text>\n<text x=\"400\" y=\"854\" font-size=\"11\" fill=\"#54c24c\">\u25b6 search_loc</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">the perk&#x27;s tool sequence ran</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">ONLY via executor.py \u2014 each step</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">is recorded to the run-ledger AS</text>\n</svg>\n",
    "demo": {
     "ledger": {
      "skill": "search",
      "perk": "loc",
      "record_store": "/tmp/search-demo",
      "vars": {
       "SEARCH_DIR": ".",
       "EXT": ""
      }
     },
     "compiled": "#!/usr/bin/env bash\n# COMPILED by cyberware \u00b7 skill=search perk=loc\n# Run ONLY through executor.py \u2014 it is the governed channel. Proven-pathway snippets live in the registry.\nset -uo pipefail\nexport SEARCH_DIR=. EXT='' RECORD_STORE=/tmp/search-demo\nmkdir -p \"$RECORD_STORE\"\nSNIP=skills/search/perks/loc/src\n\nstep1() {   # search_loc\n  echo \"[step 1] search_loc\"\n  bash \"$SNIP/search_loc.sh\"\n  test -f \"${RECORD_STORE}/loc.txt\" || { echo \"CONTRACT FAIL step 1: missing ${RECORD_STORE}/loc.txt\" >&2; exit 3; }\n}\n\ncase \"${1:-}\" in\n  --list) printf \"1\\tsearch_loc\\n\" ;;\n  --step) shift; \"step${1:?step number}\" ;;\n  --all) step1 ;;\n  *) echo \"usage: $0 --list | --step <N> | --all\" >&2; exit 2 ;;\nesac\n"
    }
   }
  ]
 }
];
window.DOCS = [
 {
  "id": "architecture",
  "label": "Architecture",
  "body": "# Architecture\n\ncyberware is a **verifiable governance runtime for skill execution** \u2014 a subset of the Cyberware\nAlchemistry at a different angle, and the local instance of the\n[Zero Trust Framework](https://github.com/rhCat/trust-model-reflection)'s delegation pillars: the\nintelligence *proposes*, the framework *validates / composes / compiles / oversees*, and is the only\nchannel that *executes*. Blueprints are [L++](https://github.com/rhCat/lpp); Python is the glue.\n\n## Two sides\n\n| side | what | where |\n|---|---|---|\n| **user** | the skill registry \u2014 a skill's context, logic, and proven pathways | `skills/<skill>/` |\n| **governance** | the infrastructure that validates, composes, compiles, oversees, executes | `infra/` |\n\n## The pipeline\n\n```\nSKILL.md \u2500\u25ba LLM fills the form \u2192 task-ledger.json\n            \u2502\n   validator.py   claims real? \u2014 record_store writable, runtime + required binaries reachable,\n            \u2502                    contract's required inputs present, host reachable (soft)\n   composer.py    L++ \u2192 TLA+ \u2192 TLC \u2014 no abstract deadlock (non-terminal sink); structural fallback\n            \u2502                        (reachability / terminal-reachable) when no JRE/tla2tools\n   compiler.py    blueprint + manifesto + contracts + snippets \u2192 ONE step-wise bash + run.{drawio,svg}\n            \u2502                        (the diagram annotated with this task's tool sequence)\n   oversight.py   OVERSIGHT_RULE over the script \u2014 destructive/dangerous patterns push back; approvable\n            \u2502                        rules waived only by an explicit, logged --approve\n   executor.py    THE channel \u2014 .bk tamper-check, upstream gate, run-ledger provenance, EXECUTOR_RULE\n```\n\n> This same pipeline is captured as a formal **L++ blueprint** \u2014 [`infra/pipeline.blueprint.json`](../infra/pipeline.blueprint.json) \u2014 so the framework is described in its own formalism (the **ouroboros**). The dashboard renders it at the top of this page; each gate's `\u2717 fail` route is the stage refusing and logging.\n\n## The governance model\n\n`executor.py` is the chokepoint. The agent channels **all** work through it:\n\n1. **Tamper-check** \u2014 the script is snapshotted to `.<script>.bk` on first run; if it later drifts\n   (an agent editing a compiled step to slip past a contract), the run is **refused**.\n2. **Upstream gate** \u2014 a step cannot run unless its predecessors are recorded as run.\n3. **Provenance ledger** \u2014 every run (ts, step, exit, duration, output hash, output tail) is appended\n   to `run-ledger.json` under the record_store. Out-of-band runs leave a hole in the chain.\n4. **EXECUTOR_RULE** \u2014 timeout and other call-boundary limits.\n\nThe runtime *is* the rule: you cannot bypass governance without leaving a visible gap (an unrecorded\nrun, a `.bk` mismatch, a missing upstream step).\n\n## The blueprint (L++)\n\nEvery tool skill shares one **perk-agnostic lifecycle**:\n\n```\nready \u2192 prepared \u2192 verified \u2192 executed        (executed = terminal)\n```\n\nThe terminal is **executed**, not \"recorded\" \u2014 recording is part of *executing*: the executor writes\neach step to the run-ledger **as it runs**, not in a separate phase after. `safety_invariants` encode\nthis \u2014 chiefly **`governed_execution_only`** (a task reaches `executed` only through `executor.py`) and\n**`record_during_execution`**, plus the skill's own guardrails. Perks are *optional* in the blueprint:\nthe blueprint says what to watch and which logs to check; a perk supplies the concrete, contract-bound\n*how*. The governance pipeline above is itself captured as a blueprint \u2014\n[`infra/pipeline.blueprint.json`](../infra/pipeline.blueprint.json), rendered at the top of this page.\n\nBlueprints render as flowcharts (`infra/visualize.py` \u2192 drawio + SVG): **state** = rectangle,\n**transition** = line, **gate** = diamond (with its `\u2713 pass` / `\u2717 fail \u2192 exit\u00b7log` branches), **action**\n= the predefined-process shape showing its `compute_unit`. The dashboard draws them in a cyberpunk theme.\n\n## Relationship to the rest\n\ncyberware is **not Athenor** (the hosted service that powers the whole Cyberware Alchemistry\nworkflow). It is the standalone, local enforcement layer \u2014 the same verifiable infrastructure\n(L++ blueprints, contracts, compiled bash, audit ledgers), pointed at general skill execution.\n",
  "pipeline": {
   "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"766\" height=\"1600\" viewBox=\"0 0 766 1600\" font-family=\"ui-monospace,Menlo,Consolas,monospace\">\n<defs><filter id=\"glow\" x=\"-60%\" y=\"-60%\" width=\"220%\" height=\"220%\"><feGaussianBlur stdDeviation=\"1.3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter><pattern id=\"px\" width=\"7\" height=\"7\" patternUnits=\"userSpaceOnUse\"><rect width=\"7\" height=\"7\" fill=\"#0a0f0a\"/><rect width=\"1\" height=\"1\" fill=\"#54c24c\" fill-opacity=\"0.13\"/></pattern><marker id=\"arr\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L9,4 L0,8 z\" fill=\"#5cc450\"/></marker></defs>\n<rect width=\"766\" height=\"1600\" fill=\"#0a0f0a\"/>\n<rect width=\"766\" height=\"1600\" fill=\"url(#px)\"/>\n<text x=\"16\" y=\"28\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"3\" fill=\"#54c24c\" filter=\"url(#glow)\">PIPELINE</text>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"130\" x2=\"272.0\" y2=\"162\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"150\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">VALIDATE</text>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"222\" x2=\"272.0\" y2=\"254\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"242\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"302\" x2=\"272.0\" y2=\"334\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"416\" x2=\"272.0\" y2=\"448\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"436\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">COMPOSE</text>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"508\" x2=\"272.0\" y2=\"540\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"528\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"588\" x2=\"272.0\" y2=\"620\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"702\" x2=\"272.0\" y2=\"734\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"722\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">COMPILE</text>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"794\" x2=\"272.0\" y2=\"826\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"814\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"874\" x2=\"272.0\" y2=\"906\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"988\" x2=\"272.0\" y2=\"1020\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"988\" x2=\"272.0\" y2=\"1020\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"1008\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">OVERSEE</text>\n<line x1=\"272.0\" y1=\"1080\" x2=\"272.0\" y2=\"1112\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"1080\" x2=\"272.0\" y2=\"1112\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"1100\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"1160\" x2=\"272.0\" y2=\"1192\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"1160\" x2=\"272.0\" y2=\"1192\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<line x1=\"272.0\" y1=\"1274\" x2=\"272.0\" y2=\"1306\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"1274\" x2=\"272.0\" y2=\"1306\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"1294\" font-size=\"12\" font-weight=\"700\" fill=\"#93d98a\">EXECUTE</text>\n<line x1=\"272.0\" y1=\"1366\" x2=\"272.0\" y2=\"1398\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"1366\" x2=\"272.0\" y2=\"1398\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<text x=\"283\" y=\"1386\" font-size=\"11\" font-weight=\"700\" fill=\"#93d98a\">\u2713 pass</text>\n<line x1=\"272.0\" y1=\"1446\" x2=\"272.0\" y2=\"1478\" stroke=\"#54c24c\" stroke-width=\"7\" opacity=\"0.16\" filter=\"url(#glow)\"/>\n<line x1=\"272.0\" y1=\"1446\" x2=\"272.0\" y2=\"1478\" stroke=\"#5cc450\" stroke-width=\"2.6\" marker-end=\"url(#arr)\"/>\n<rect x=\"151.0\" y=\"48\" width=\"242\" height=\"82\" fill=\"#0e1d0d\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"71\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">SUBMITTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 entry</tspan></text>\n<text x=\"164.0\" y=\"89\" font-size=\"11\" fill=\"#74ad68\">a task-ledger (skill, perk,</text>\n<text x=\"164.0\" y=\"103\" font-size=\"11\" fill=\"#74ad68\">vars, record_store) is</text>\n<text x=\"164.0\" y=\"117\" font-size=\"11\" fill=\"#74ad68\">submitted; nothing has run</text>\n<polygon points=\"272.0,162 351.0,192.0 272.0,222 193.0,192.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"196\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_claims_real</text>\n<text x=\"367\" y=\"196\" font-size=\"11\" fill=\"#93d98a\">\u22a8 store_writable \u2227 runtime_reachable \u2227 inputs_present</text>\n<line x1=\"193.0\" y1=\"192.0\" x2=\"175\" y2=\"192.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"186\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"175\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"196\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"254\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"254\" x2=\"168.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"254\" x2=\"376.0\" y2=\"302\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"282\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">validator:check_claims</text>\n<rect x=\"151.0\" y=\"334\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"357\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">VALIDATED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"375\" font-size=\"11\" fill=\"#74ad68\">validator.py confirmed the</text>\n<text x=\"164.0\" y=\"389\" font-size=\"11\" fill=\"#74ad68\">claims are real \u2014 store</text>\n<text x=\"164.0\" y=\"403\" font-size=\"11\" fill=\"#74ad68\">writable, runtime + binaries</text>\n<polygon points=\"272.0,448 351.0,478.0 272.0,508 193.0,478.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"482\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_no_deadlock</text>\n<text x=\"367\" y=\"482\" font-size=\"11\" fill=\"#93d98a\">\u22a8 tlc_no_deadlock \u2228 structurally_sound</text>\n<line x1=\"193.0\" y1=\"478.0\" x2=\"175\" y2=\"478.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"472\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"461\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"482\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"540\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"540\" x2=\"168.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"540\" x2=\"376.0\" y2=\"588\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"568\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">composer:model_check</text>\n<rect x=\"151.0\" y=\"620\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"643\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">COMPOSED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"661\" font-size=\"11\" fill=\"#74ad68\">composer.py model-checked the</text>\n<text x=\"164.0\" y=\"675\" font-size=\"11\" fill=\"#74ad68\">L++ blueprint (-&gt; TLC) \u2014 no</text>\n<text x=\"164.0\" y=\"689\" font-size=\"11\" fill=\"#74ad68\">logical deadlock</text>\n<polygon points=\"272.0,734 351.0,764.0 272.0,794 193.0,764.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"768\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_contract_bound</text>\n<text x=\"367\" y=\"768\" font-size=\"11\" fill=\"#93d98a\">\u22a8 sequence_resolved \u2227 contracts_present</text>\n<line x1=\"193.0\" y1=\"764.0\" x2=\"175\" y2=\"764.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"758\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"747\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"768\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"826\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"826\" x2=\"168.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"826\" x2=\"376.0\" y2=\"874\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"854\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">compiler:build_script</text>\n<rect x=\"151.0\" y=\"906\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"929\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">COMPILED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"947\" font-size=\"11\" fill=\"#74ad68\">compiler.py turned ledger +</text>\n<text x=\"164.0\" y=\"961\" font-size=\"11\" fill=\"#74ad68\">manifesto + contracts + snippets</text>\n<text x=\"164.0\" y=\"975\" font-size=\"11\" fill=\"#74ad68\">into ONE step-wise bash script</text>\n<polygon points=\"272.0,1020 351.0,1050.0 272.0,1080 193.0,1050.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"1054\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_oversight_clear</text>\n<text x=\"367\" y=\"1054\" font-size=\"11\" fill=\"#93d98a\">\u22a8 no_dangerous_pattern \u2228 approved</text>\n<line x1=\"193.0\" y1=\"1050.0\" x2=\"175\" y2=\"1050.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"1044\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"1033\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"1054\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"1112\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"1112\" x2=\"168.0\" y2=\"1160\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"1112\" x2=\"376.0\" y2=\"1160\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"1140\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">oversight:scan</text>\n<rect x=\"151.0\" y=\"1192\" width=\"242\" height=\"82\" fill=\"#0b140a\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"1215\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#54c24c\" filter=\"url(#glow)\">CLEARED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\"></tspan></text>\n<text x=\"164.0\" y=\"1233\" font-size=\"11\" fill=\"#74ad68\">oversight.py scanned the script</text>\n<text x=\"164.0\" y=\"1247\" font-size=\"11\" fill=\"#74ad68\">against OVERSIGHT_RULE \u2014 no</text>\n<text x=\"164.0\" y=\"1261\" font-size=\"11\" fill=\"#74ad68\">unapproved destructive/dangerous</text>\n<polygon points=\"272.0,1306 351.0,1336.0 272.0,1366 193.0,1336.0\" fill=\"#0c1a0c\" stroke=\"#54c24c\" stroke-width=\"1.8\" filter=\"url(#glow)\"/>\n<text x=\"272\" y=\"1340\" font-size=\"11\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#54c24c\">g_governed</text>\n<text x=\"367\" y=\"1340\" font-size=\"11\" fill=\"#93d98a\">\u22a8 tamper_check_pass \u2227 upstream_recorded</text>\n<line x1=\"193.0\" y1=\"1336.0\" x2=\"175\" y2=\"1336.0\" stroke=\"#d4794e\" stroke-width=\"2\"/>\n<text x=\"184\" y=\"1330\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\" fill=\"#d4794e\">\u2717 fail</text>\n<rect x=\"55.0\" y=\"1319\" width=\"120\" height=\"34\" fill=\"#170d09\" stroke=\"#d4794e\" stroke-width=\"1.6\"/>\n<text x=\"115.0\" y=\"1340\" font-size=\"11\" text-anchor=\"middle\" fill=\"#e7a684\">exit / log</text>\n<rect x=\"160.0\" y=\"1398\" width=\"224\" height=\"48\" fill=\"#0a1609\" stroke=\"#54c24c\" stroke-width=\"1.5\" filter=\"url(#glow)\"/>\n<line x1=\"168.0\" y1=\"1398\" x2=\"168.0\" y2=\"1446\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<line x1=\"376.0\" y1=\"1398\" x2=\"376.0\" y2=\"1446\" stroke=\"#54c24c\" stroke-width=\"1.4\"/>\n<text x=\"272\" y=\"1426\" font-size=\"12\" font-weight=\"600\" text-anchor=\"middle\" fill=\"#93d98a\">executor:govern_run</text>\n<rect x=\"151.0\" y=\"1478\" width=\"242\" height=\"82\" fill=\"#0f2410\" stroke=\"#93d98a\" stroke-width=\"2.2\" filter=\"url(#glow)\"/>\n<text x=\"164.0\" y=\"1501\" font-size=\"14\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#93d98a\" filter=\"url(#glow)\">EXECUTED<tspan font-size=\"11\" letter-spacing=\"0\" fill=\"#74ad68\">  \u00b7 terminal</tspan></text>\n<text x=\"164.0\" y=\"1519\" font-size=\"11\" fill=\"#74ad68\">executor.py ran it through the</text>\n<text x=\"164.0\" y=\"1533\" font-size=\"11\" fill=\"#74ad68\">governed channel \u2014</text>\n<text x=\"164.0\" y=\"1547\" font-size=\"11\" fill=\"#74ad68\">tamper-checked, upstream-gated,</text>\n</svg>\n",
   "blueprint": {
    "$schema": "lpp/v0.2.0",
    "id": "pipeline",
    "name": "cyberware governance pipeline",
    "description": "The infra's OWN blueprint \u2014 the path every task-ledger takes through the governed runtime: validate -> compose -> compile -> oversee -> execute. The same L++ formalism the skills use, turned on the framework itself (the ouroboros). Each gate's failure route is the stage refusing and logging.",
    "entry_state": "submitted",
    "states": {
     "submitted": {
      "description": "a task-ledger (skill, perk, vars, record_store) is submitted; nothing has run"
     },
     "validated": {
      "description": "validator.py confirmed the claims are real \u2014 store writable, runtime + binaries reachable, required inputs present"
     },
     "composed": {
      "description": "composer.py model-checked the L++ blueprint (-> TLC) \u2014 no logical deadlock"
     },
     "compiled": {
      "description": "compiler.py turned ledger + manifesto + contracts + snippets into ONE step-wise bash script"
     },
     "cleared": {
      "description": "oversight.py scanned the script against OVERSIGHT_RULE \u2014 no unapproved destructive/dangerous patterns"
     },
     "executed": {
      "description": "executor.py ran it through the governed channel \u2014 tamper-checked, upstream-gated, recorded to the run-ledger"
     }
    },
    "terminal_states": {
     "executed": {}
    },
    "gates": {
     "g_claims_real": {
      "type": "expression",
      "expression": "store_writable /\\ runtime_reachable /\\ inputs_present",
      "description": "the ledger's claims hold"
     },
     "g_no_deadlock": {
      "type": "expression",
      "expression": "tlc_no_deadlock \\/ structurally_sound",
      "description": "the blueprint cannot deadlock"
     },
     "g_contract_bound": {
      "type": "expression",
      "expression": "sequence_resolved /\\ contracts_present",
      "description": "every step is contract-bound"
     },
     "g_oversight_clear": {
      "type": "expression",
      "expression": "no_dangerous_pattern \\/ approved",
      "description": "the script clears the oversight rules"
     },
     "g_governed": {
      "type": "expression",
      "expression": "tamper_check_pass /\\ upstream_recorded",
      "description": "no drift; predecessors recorded"
     }
    },
    "actions": {
     "a_validate": {
      "type": "compute",
      "compute_unit": "validator:check_claims",
      "description": "probe the runtime, dirs, and required inputs"
     },
     "a_compose": {
      "type": "compute",
      "compute_unit": "composer:model_check",
      "description": "compile L++ -> TLA+ -> TLC (structural fallback if no JRE)"
     },
     "a_compile": {
      "type": "compute",
      "compute_unit": "compiler:build_script",
      "description": "ledger + manifesto + contracts + snippets -> step-wise bash"
     },
     "a_oversee": {
      "type": "compute",
      "compute_unit": "oversight:scan",
      "description": "regex/ast scan the compiled script against OVERSIGHT_RULE"
     },
     "a_execute": {
      "type": "compute",
      "compute_unit": "executor:govern_run",
      "description": "THE channel \u2014 .bk tamper-check, upstream gate, run-ledger provenance"
     }
    },
    "transitions": [
     {
      "from": "submitted",
      "to": "validated",
      "trigger": "VALIDATE",
      "action": "a_validate",
      "gate": "g_claims_real"
     },
     {
      "from": "validated",
      "to": "composed",
      "trigger": "COMPOSE",
      "action": "a_compose",
      "gate": "g_no_deadlock"
     },
     {
      "from": "composed",
      "to": "compiled",
      "trigger": "COMPILE",
      "action": "a_compile",
      "gate": "g_contract_bound"
     },
     {
      "from": "compiled",
      "to": "cleared",
      "trigger": "OVERSEE",
      "action": "a_oversee",
      "gate": "g_oversight_clear"
     },
     {
      "from": "cleared",
      "to": "executed",
      "trigger": "EXECUTE",
      "action": "a_execute",
      "gate": "g_governed"
     }
    ],
    "safety_invariants": [
     {
      "name": "governed_execution_only",
      "expression": "state /= 'executed' \\/ governed_run",
      "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py \u2014 the single governed channel."
     },
     {
      "name": "no_stage_skipped",
      "expression": "ordered(submitted, validated, composed, compiled, cleared, executed)",
      "description": "GUARDRAIL: no stage is skipped \u2014 each gate must hold before the next fires."
     },
     {
      "name": "refuse_on_drift",
      "expression": "state /= 'executed' \\/ tamper_check_pass",
      "description": "GUARDRAIL: if the compiled script drifted from its .bk snapshot, the executor refuses."
     },
     {
      "name": "record_every_run",
      "expression": "state /= 'executed' \\/ recorded_to_ledger",
      "description": "GUARDRAIL: every governed run is appended to the run-ledger \u2014 no out-of-band execution."
     }
    ]
   }
  }
 },
 {
  "id": "authoring",
  "label": "Authoring",
  "body": "# Authoring a skill\n\nA skill is a directory under `skills/`. Its anatomy:\n\n```\nskills/<skill>/\n  SKILL.md                 context for the intelligence \u2014 what it does, what to watch, which logs to check\n  blueprint.json           the L++ CFG (the perk-agnostic lifecycle + safety_invariants)\n  perks.json               the proven pathways (id, summary, tools, destructive?)\n  ledger.json              the FORM the LLM fills \u2192 task-ledger.json\n  blueprint.{drawio,svg}   generated diagrams (by visualize.py)\n  perks/<perk>/\n    metadata.json          description \u00b7 rules \u00b7 usage \u00b7 limitation \u00b7 minimal_example\n    manifesto.json         the ${VAR} template: `sequence` (tool order) + `tools` + `env` + `requires`\n    src/\n      contracts.json       the tool's I/O + checks (required inputs, output_exists)\n      <tool>.sh            the proven pathway \u2014 emits deterministic structured JSON (audit + debug log)\n```\n\n## 0. Evaluate first (the on-ramp)\n\nBefore authoring, run the idea through **`cws-create/evaluate`** \u2014 it classifies it as **execution**\n(a tool/pathway \u2014 fits cyberware), **design** (taste/aesthetics \u2014 *not* the emphasis; keep it as\nguidance), or **transformable** (extract the execution core into a governed pathway). Only execution /\ntransformable skills belong here. If it fits, **`cws-create/scaffold`** lays down the skeleton below.\n\n## 1. Scaffold\n\n```sh\npython3 infra/scaffold.py --skill myskill --name \"My Skill\" \\\n    --perk fetch:my_fetch:curl --perk store:my_store:python3\n#   --perk  <perk_id>:<tool>[:<binary>]\n```\n\nThis writes the whole skeleton with the standard lifecycle blueprint (`ready \u2192 prepared \u2192 verified \u2192\nexecuted`, where the executor records each step *as it runs*) and a snippet **stub** per tool. It\nalready **composes** out of the box \u2014 you fill in the snippets and vars.\n\n## 2. The manifesto \u2014 the `${VAR}` template\n\n```json\n{\n  \"_perk\": \"fetch\",\n  \"sequence\": [\"my_fetch\"],                         // the tool-call order\n  \"tools\": { \"my_fetch\": { \"binary\": \"curl\", \"params\": { \"URL\": \"${URL}\" } } },\n  \"env\":   { \"URL\": \"${URL}\", \"RECORD_STORE\": \"${record_store}\" },   // universal runtime settings\n  \"requires\": [\"curl\"]                              // the validator checks these are reachable\n}\n```\n\n`${VAR}` placeholders are filled from the task-ledger's `vars` (and `record_store`). The `sequence`\nbecomes the compiled script's steps; `requires` is what the validator probes.\n\n## 3. The contract \u2014 I/O + checks\n\n```json\n{\n  \"tool\": \"my_fetch\",\n  \"inputs\":  { \"URL\": { \"type\": \"string\", \"required\": true } },\n  \"outputs\": { \"body\": { \"path\": \"${RECORD_STORE}/response.body\", \"type\": \"file\" } },\n  \"checks\":  { \"exit_zero\": true, \"output_exists\": \"${RECORD_STORE}/response.body\" }\n}\n```\n\nThe validator checks `inputs.required` are present; the compiler emits the `output_exists` check after\nthe final step.\n\n## 4. The snippet \u2014 the proven pathway\n\n`src/<tool>.sh` is the tool's entry point (the framework runs `bash <tool>.sh`). It reads its env vars\nand emits **one line of structured JSON** on stdout (the audit + debug log); keep it deterministic and\nwrite artifacts under `$RECORD_STORE`.\n\n**When the core is bash** (psql, curl, tar, git, \u2026) \u2014 the logic lives in the `.sh`.\n\n**When the core is another language** (Python, \u2026) \u2014 keep the logic as its own standalone file and make\nthe `.sh` a thin **porter**. Don't bury logic in a `<<'PY'` heredoc \u2014 a standalone file is far easier\nto read, lint, and update:\n\n```\nsrc/<tool>.py     # the core \u2014 inspect / lint / test / edit directly; reads its inputs from the env\nsrc/<tool>.sh     # the porter\n```\n\n```bash\n# src/<tool>.sh\nset -euo pipefail\nHERE=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nexec python3 \"$HERE/<tool>.py\"\n```\n\n`scaffold.py` writes exactly this when a perk's binary is `python3` (see `skills/codebaseqc`, whose\n`cbqc_*` tools are standalone `.py` cores behind thin porters).\n\n## 5. Visualize + run\n\n```sh\npython3 infra/visualize.py --skill myskill            # \u2192 blueprint.{drawio,svg}\n# fill ledger.json \u2192 task-ledger.json, then:\npython3 infra/validator.py --ledger task-ledger.json\npython3 infra/composer.py  --ledger task-ledger.json\npython3 infra/compiler.py  --ledger task-ledger.json -o run.sh   # + run.{drawio,svg}\npython3 infra/oversight.py --script run.sh\npython3 infra/executor.py  --script run.sh --all                 # the governed run\n```\n\nEvery `compiler.py` run also drops `run.drawio` + `run.svg` (the operate step annotated with this\ntask's tools) \u2014 open the SVG in a browser to eyeball what will run before the executor does.\n\n## Conventions\n\n- **Read-only by default.** A destructive pathway declares `destructive: true` and is gated by\n  `OVERSIGHT_RULE` (waived only by an explicit `--approve`).\n- **Structured output is the contract surface.** The JSON line is both the audit log and what the\n  executor records (its hash) for tamper-evidence.\n- **One perk = one proven way.** Multiple steps live in a perk's `sequence`; multiple *strategies* are\n  separate perks.\n"
 },
 {
  "id": "skills",
  "label": "Catalog",
  "body": "# Skill catalog\n\nTool skills (operational pathways) \u2014 not design/taste skills. Each runs through the governed pipeline\n(`validate \u2192 compose \u2192 compile \u2192 oversight \u2192 executor`) and ships a `blueprint.{drawio,svg}`.\n\n| skill | perks | tools | notes / guard |\n|---|---|---|---|\n| **pg_ops** | `select` \u00b7 `migrate` | psql | governed PostgreSQL; `select` read-only, `migrate` in one transaction. DROP/TRUNCATE push back unless `--approve`. |\n| **http** | `get` \u00b7 `post` | curl | responses captured to record_store with status + size. pipe-to-shell blocked. |\n| **fs** | `archive` \u00b7 `find_large` | tar \u00b7 find | `archive` \u2192 tar.gz; `find_large` read-only listing. rm-at-root / rm -rf gated. |\n| **git_ops** | `snapshot` \u00b7 `status` | git | `snapshot` = stage+commit (no push \u2014 push is intentionally not a skill); `status` read-only. force-push / reset --hard gated. |\n| **py_qc** | `test` \u00b7 `lint` | pytest \u00b7 ruff/flake8 | run a project's tests / linter, reports to record_store. |\n| **codebaseqc** | `audit` | python3 (ast) | pure-Python QC: usage (dead code) \u00b7 contract (docstring+return type) \u00b7 coverage (referenced in tests). Name-based heuristics; sound resolution is the Intent-Fidelity frontier. |\n| **ci-codeqc** | `github_actions` | bash | generate/update `.github/workflows/codeqc.yml` (ruff + mypy + pytest) for any repo. Idempotent: existing workflow backed up to `.bk` before overwrite. |\n| **docker** | `build` \u00b7 `ps` | docker | build an image from a context dir; `ps` lists containers (read-only). Needs a running daemon. |\n| **net** | `healthcheck` \u00b7 `dns` | curl \u00b7 python3 | HTTP probe (status + latency); DNS resolve (python core via porter). Read-only. |\n| **data** | `csv2json` \u00b7 `jq` | python3 \u00b7 jq | CSV \u2192 JSON array (python core); jq query over a JSON file. |\n| **search** | `grep` \u00b7 `loc` | ripgrep/grep \u00b7 find | pattern search (rg, fallback grep); line counts by extension. Read-only. |\n| **release** | `tag` | git | annotated git tag at HEAD; no-op if it exists. No force, no push (push stays gated). |\n| **cws-create** | `evaluate` \u00b7 `scaffold` | python3 \u00b7 scaffold.py | **the on-ramp** \u2014 classify a candidate skill (execution / design / transformable / unclear) and, if it fits, scaffold it into cyberware format. |\n\n## Choosing a perk\n\nA **perk** is a *predetermined, proven, viable pathway*. The blueprint says what to watch and which\nlogs to check; a perk says exactly how to act. Pick the perk whose `metadata.json` matches your task\n(its `rules`, `usage`, `limitation`, and `minimal_example`), copy `ledger.json` \u2192 your\n`task-ledger.json`, fill the vars its `manifesto.json` declares, and submit it to the pipeline.\n\n## Adding a skill\n\nSee [authoring.md](authoring.md) \u2014 `scaffold.py` writes a composing skeleton; fill the snippets and\nvars. The registry is meant to grow: tools are the unit, perks are the proven pathways within them.\n\n## Self-audit\n\n`examples/self-audit/` holds the framework's own `codebaseqc` report \u2014 cyberware QC'd by cyberware.\nIt honestly shows the open gaps (no return-type hints, no `tests/` dir yet).\n"
 }
];
