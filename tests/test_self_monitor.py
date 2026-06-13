"""The fast self-monitor gates — run on every push via pytest.

Every chip blueprint AND the engine's own pipeline blueprint must be deadlock-free, and the mutation
ratchet policy must be well-formed (real modules + slices, sane floors). The expensive part — actually
mutating the enforcement surface against its floors — runs as its own CI job
(`python3 -m infra.tool.selfmonitor`), not inline here.
"""
import json
import os

from infra.tool import selfmonitor


def test_every_blueprint_is_deadlock_free():
    n, bad = selfmonitor.check_blueprints()
    assert n > 0
    assert not bad, f"blueprints with deadlock/unreachable: {bad}"


def test_mutation_ratchet_policy_is_well_formed():
    pol = json.load(open(selfmonitor.POLICY))
    assert pol["enforcement_surface"], "policy must name at least one gate module"
    for e in pol["enforcement_surface"]:
        assert os.path.isfile(os.path.join(selfmonitor.ROOT, e["module"])), f"missing module {e['module']}"
        assert os.path.isfile(os.path.join(selfmonitor.ROOT, e["slice"])), f"missing slice {e['slice']}"
        assert 0.0 <= e["floor"] <= 1.0 and 0.0 <= e.get("target", 0.90) <= 1.0
