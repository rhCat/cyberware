---
skill: datadog
name: Datadog CI on GitHub
perks: [github_ci]
---

# datadog — set up Datadog CI on GitHub Actions

Writes a Datadog **CI Visibility** workflow (`.github/workflows/datadog-ci.yml`) into a target repo:
install `datadog-ci`, run the tests producing JUnit XML, and upload the results to Datadog (test
visibility). Idempotent — an existing workflow is backed up to `.bk` first, so the same perk both
creates and updates it.

## What to look out for
The tool emits `action` (`created | updated`), the resolved `service`, and the workflow path. **After it
runs:** add the **`DD_API_KEY`** secret to the repo, and (optionally) enable the **Datadog GitHub App**
for full pipeline visibility. LOGS TO CHECK: that line + `${record_store}/datadog-ci.yml`.

## How to use it
Fill `PROJECT_DIR` (+ optional `SERVICE`, `TEST_CMD`, `JUNIT_PATH`, `DD_SITE`, `BRANCH`), then
validate → compose → compile → oversight → executor. Commit the generated workflow to the target repo.
