"""Unit: visualize.svg / drawio — diagrams are well-formed and reflect the task."""
import xml.dom.minidom as minidom

from infra import registry
from infra.govern import compiler
from infra.govern import runlog
from infra.tool import visualize


def _bp():
    import json
    return json.load(open(registry.SKILLCHIP + "/codebaseqc/blueprint.json"))


def test_svg_is_well_formed_xml():
    minidom.parseString(visualize.svg(_bp()))   # raises on malformed


def test_drawio_is_well_formed_xml():
    minidom.parseString(visualize.drawio(_bp()))


def test_general_blueprint_has_no_task_header():
    out = visualize.svg(_bp())
    assert "TASK ·" not in out


def test_task_blueprint_renders_header_and_gate_bindings(tmp_path):
    L = {"skill": "codebaseqc", "perk": "audit", "record_store": str(tmp_path),
         "vars": {"PROJECT_DIR": "/tmp/r", "SRC_DIR": "src", "TEST_DIR": "tests"}}
    bp = compiler.task_blueprint(L, runlog.run_dir(L))
    svg = visualize.svg(bp, bp["task"]["tools"])
    minidom.parseString(svg)                       # still well-formed
    assert "TASK ·" in svg                          # the settings header
    assert "PROJECT_DIR" in svg and "(dir, required)" in svg
    assert "↳" in svg                               # the resolved gate bindings


def test_drawio_task_note_present(tmp_path):
    L = {"skill": "codebaseqc", "perk": "audit", "record_store": str(tmp_path),
         "vars": {"PROJECT_DIR": "/tmp/r", "SRC_DIR": "src", "TEST_DIR": "tests"}}
    bp = compiler.task_blueprint(L, runlog.run_dir(L))
    dx = visualize.drawio(bp, bp["task"]["tools"])
    minidom.parseString(dx)
    assert "task_note" in dx
