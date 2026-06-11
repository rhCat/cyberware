#!/usr/bin/env python3
"""visualize.py — render a skill's L++ blueprint as draw.io XML (the state machine).

Lays states out by BFS depth from the entry state (layered top-down), draws every transition as a
labeled edge (trigger / action / ⊨ gate), and colours the entry (blue) and terminal (green) states.
Open the `.drawio` file in app.diagrams.net / the draw.io desktop app or the VS Code extension.

  visualize.py --skill pg_ops [-o pg_ops.drawio]
  visualize.py --blueprint path/to/blueprint.json -o out.drawio
"""
from __future__ import annotations
import argparse, html, json, os, sys
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def esc(t):  # draw.io value: HTML-escaped, \n → line break
    return html.escape(str(t)).replace("\n", "&#10;")


def depths(bp):
    adj = {}
    for t in bp["transitions"]:
        adj.setdefault(t["from"], []).append(t["to"])
    d = {bp["entry_state"]: 0}
    q = deque([bp["entry_state"]])
    while q:
        s = q.popleft()
        for to in adj.get(s, []):
            if to not in d:
                d[to] = d[s] + 1
                q.append(to)
    md = max(d.values(), default=0)
    for s in bp["states"]:
        d.setdefault(s, md + 1)   # unreachable states sink to the bottom
    return d


def drawio(bp):
    states = list(bp["states"])
    terms = set(bp.get("terminal_states", {}))
    entry = bp["entry_state"]
    gates = bp.get("gates", {})
    d = depths(bp)
    by_layer = {}
    for s in states:
        by_layer.setdefault(d[s], []).append(s)
    W, H, VSPACE, HSPACE = 200, 72, 132, 240
    pos = {}
    for layer, ss in sorted(by_layer.items()):
        for i, s in enumerate(ss):
            pos[s] = (40 + i * HSPACE, 40 + layer * VSPACE)

    cells = []
    for s in states:
        x, y = pos[s]
        fill, stroke = ("#d5e8d4", "#82b366") if s in terms else (("#dae8fc", "#6c8ebf") if s == entry else ("#f5f5f5", "#666666"))
        style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};align=left;verticalAlign=top;spacing=6;spacingTop=4;fontSize=11;"
        val = esc(f"{s}\n{bp['states'][s].get('description','')}")
        cells.append(f'<mxCell id="s_{s}" value="{val}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="{W}" height="{H}" as="geometry"/></mxCell>')
    for i, t in enumerate(bp["transitions"]):
        sub = [t.get("action")]
        if t.get("gate"):
            sub.append("⊨ " + t["gate"])
        label = esc(t.get("trigger", "") + ("\n" + " / ".join(x for x in sub if x) if any(sub) else ""))
        cells.append(f'<mxCell id="t_{i}" value="{label}" '
                     f'style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;fontSize=10;endArrow=block;strokeColor=#444444;" '
                     f'edge="1" parent="1" source="s_{t["from"]}" target="s_{t["to"]}">'
                     f'<mxGeometry relative="1" as="geometry"/></mxCell>')

    body = "\n        ".join(cells)
    return (f'<mxfile host="cyberware">\n'
            f'  <diagram name="{esc(bp.get("id", "skill"))}">\n'
            f'    <mxGraphModel dx="900" dy="700" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
            f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100" math="0" shadow="0">\n'
            f'      <root>\n        <mxCell id="0"/>\n        <mxCell id="1" parent="0"/>\n        {body}\n'
            f'      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n')


def main():
    ap = argparse.ArgumentParser(description="render an L++ blueprint as draw.io XML")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--skill")
    g.add_argument("--blueprint")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    path = a.blueprint or os.path.join(ROOT, "skills", a.skill, "blueprint.json")
    bp = json.load(open(path))
    xml = drawio(bp)
    if a.out:
        open(a.out, "w").write(xml)
        print(f"wrote {a.out}  ({len(bp['states'])} states, {len(bp['transitions'])} transitions)")
    else:
        sys.stdout.write(xml)


if __name__ == "__main__":
    main()
