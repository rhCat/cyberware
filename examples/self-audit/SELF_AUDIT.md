# Self-audit — cyberware QC'd by cyberware

`codebaseqc` (this repo's own skill) run on `infra/` through the full governed pipeline
(validator → composer → compiler → oversight → executor). The framework analyzes itself.

| dimension | result |
|---|---|
| **usage** (dead code, name-based) | 0 unused / 36 defined |
| **contract** (docstring + return type, ast) | 38 gaps / 43 public |
| **coverage** (referenced in tests, name-based) | 33 uncovered / 33 public (has_tests: False) |

Reports: [`usage_gaps.json`](usage_gaps.json) · [`contract_gaps.json`](contract_gaps.json) · [`coverage_gaps.json`](coverage_gaps.json).

> Honest caveat: usage/coverage are name-based heuristics; the contract check is sound (ast). Generated
> 2026-06-11 by codebaseqc on itself.
