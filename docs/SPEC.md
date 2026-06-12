This is subset of the cyber alchemistry, same verifiable infrastructure but different angle. it is no the athenor, which power the entire cyber alchemistry workflow. It should be independent framework. This would all base on lpp 4 axiom but no need to explain alot. It is the cyberware. We would use python for the frame as ti is the great glue language, and glue it is we need. Create the independent repo that would have:
1. Skill registry
    In skill registry, each skill preserves skill.md to provide context for intelligence understanding and to formulate set of form to submit. Each skill while preserving the general informative forms, it has perks that are predetermiened proven viable pathways that directly handle certain tasks. Skill Registry has:
    1. SKILL.MD: The context and overall instruction. For each skill use, it will generate only the task-ledger.json that generated basing on the blueprint.json and related perks manifesto.json, the contract
    2. Perks.json: The metadata of perks of the skill.
    3. Perks folder: directory hosint each perk, and in eahc perk folder:
        1. metadata.json: metadata of the perk, having description, rules, usage, limitation and minimal example
        2. manifesto.json: the template form with mutable values in form of ${VAR NAME} to provide the overall environment variable or runtime setting that is universal to operation, this would be used as template to generate the specific snippets and related config. at top header would have a sequence field that contains sequence of tool calls, another expandable field that is expandable to register which tool and waht tool specific parameters to set.
        3. scr: Folder containing written subprocess snippits that is modular with 
            1. contracts.json: defines I/O and check criterial
            2. <tool name>: the script containing the actual code snippit to run basing on th I contract. 
    4. blueprint.json: The overall action CFG what this skill would generally behave despite waht perks does in lpp. perks would be optional in the blueprints. This is extremely important as skill + bluprint will tell what llm/intelligence what to look out for and what logs to chekc, tool run would have deterministic structured output/log that would serve as audit log and debug log.
    5. ledger.json: The ledger.json is a template form to contain only the neccesary field update options for LLM to output, that would later feed into composer to programmtically create the task bluep

2. Infrastructure:
    1. Validator.py: this would walk the task ledger, the blueprint and I/O to test certain validatable variables in the ledger clain exists, such as if python runtime is reachable, dir exists with right permission and all that.
    2. Composer.py: compile the lpp blueprint with all states and such from the ledger and the blueprint, then translate and run on tlc to check if there is any logical deadlock from absctract level.
    3. Compiler.py: After validation, takes the task-ledger.json and look into the blueprint, the contracts, the code snippit and so on to compile a bash script that is the executable for the skill use. The compuled bash script would have step wise option run flag. 
    4. OVERSIGHT_RULE: The rule for oversight, say fo not drop table, do not drop schema and so on 
    5. Oversight.py: enforce OVERSIGHT_RULE, use ast or regex, or optional pass to a subagent to check, if script does not pass oversight, push back
    6. EXECUTOR_RULE.json: any oversight rules like monitor usgae or so that need to be fiven to executor
    7. Executor.py: This is the tool call through the python, the executor is mainly the oversight by register the run metadata into the general json that would preserve how this task-skill-run had been used and what was latest changes. It would create a .<task-run-script>.bk when first ran and validate if anything changed, if changed would add information/warning to log. And the executor would check if upsream steps had been ran or not. This is the enforcement/governance layer. The agent will channel the work through executor.py only, and we always check if there is rogue use/call in script usage if the step output or sorts had been altered by agent bypassing the governance. It would also take the EXECUTOR_RULE.json that need to be enforced by the execor.

---

**Built since this founding spec** (see [architecture.md](architecture.md) for the current map):

- **The registry became a cartridge — the skillChip.** The skill registry is now its own repo,
  [**skillChip**](https://github.com/rhCat/skillChip) ("the feed-stock cartridge"), vendored here as the
  `skillChip/` submodule; the directory once called `skills/` is now `skillChip/`. cyberware is the
  *engine*, the chip is the *cartridge*: the infra locates it via `infra/registry.py`
  (`registry.SKILLCHIP` — default `<repo>/skillChip`, overridable with `$CYBERWARE_SKILLCHIP`), so pointing
  at another chip makes the same engine govern a different feed-stock. The chip is **self-describing** —
  `skillChip/index.json` is its manifest (every skill + `skill_sha`, plus a roll-up `chip_sha`).
- **The skill became a verifiable package.** Each skill now also pins an `index.json` (per-file sha256 +
  a roll-up `skill_sha` — its authenticity identity) and each perk carries a `test/case.json` that proves
  it through the real governed channel. A skill no longer relies on its `SKILL.md` prose and trust.
- **A service plane — `govd`** ([governance-service.md](governance-service.md)). The same governance,
  offered as a control/audit service where **no data crosses the boundary**: the agent sends a *claim*
  (skill, perk, var KEYS), govd blesses a value-free plan from its own registry, the agent runs locally
  and reports status. Discovery is `GET /catalog`; the agent's registry is checked against the blessed
  `skill_sha` (verified / drift / unverified). The Docker build gates on `skill_index --check --all`.
