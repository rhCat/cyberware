# Self-audit — cyberware QC'd by cyberware

`codebaseqc` (this repo's own skill) run on `infra/` through the full governed pipeline
(validator → composer → compiler → oversight → executor — 3 governed steps). **The framework
analyzes itself, and commits the result through its own `git_ops` skill.**

| dimension | result |
|---|---|
| **usage** (dead code, name-based) | 0 unused / 26 defined |
| **contract** (docstring + return type, ast) | 33 gaps / 33 public |
| **coverage** (referenced in tests, name-based) | 25 uncovered / 25 public (has_tests: False) |

Reports: [`usage_gaps.json`](usage_gaps.json) · [`contract_gaps.json`](contract_gaps.json) · [`coverage_gaps.json`](coverage_gaps.json).

> Honest caveat: usage/coverage are name-based heuristics (the pure-Python pathway); the contract
> check is sound (ast). The contract + coverage gaps are real — `infra/` has no return-type hints and
> no `tests/` dir yet. Generated 2026-06-11 by codebaseqc on itself.
