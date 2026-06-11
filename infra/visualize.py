#!/usr/bin/env python3
"""visualize.py — render a skill's L++ blueprint as draw.io XML *and* self-contained SVG.

The SVG is the quick-look — it renders in any browser, no draw.io needed. States are laid out by BFS
depth from entry (layered), transitions are labeled (trigger / action), entry is blue and terminals
green. Pass `--ledger` and the *operate* state is annotated with the chosen perk's actual tool
sequence, so each compiled task shows exactly what it will run.

  visualize.py --skill pg_ops [-o base]              # base.drawio + base.svg
  visualize.py --ledger task-ledger.json -o run      # annotated with the perk's steps
  visualize.py --blueprint path -o out --format svg  # one format only
"""
from __future__ import annotations
import argparse, html, json, os
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def E(t):  # XML/HTML escape
    return html.escape(str(t))


def wrap(text, n):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


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
        d.setdefault(s, md + 1)
    return d


def annotated_states(bp, perk_steps):
    """states dict with the operate-target state's description appended with the perk's steps."""
    states = {s: dict(m) for s, m in bp["states"].items()}
    if perk_steps:
        op_to = None
        for t in bp["transitions"]:
            cu = bp.get("actions", {}).get(t.get("action", ""), {}).get("compute_unit", "")
            if "perk:sequence" in cu or t.get("action") == "a_operate":
                op_to = t["to"]
        if op_to and op_to in states:
            states[op_to]["description"] = states[op_to]["description"] + "  ▶ " + " → ".join(perk_steps)
    return states


def _layout(bp):
    d = depths(bp)
    by_layer = {}
    for s in bp["states"]:
        by_layer.setdefault(d[s], []).append(s)
    W, H, V, Hs, MX, MY = 210, 78, 150, 250, 30, 30
    pos = {s: (MX + i * Hs, MY + layer * V) for layer, ss in by_layer.items() for i, s in enumerate(ss)}
    width = MX * 2 + max(len(ss) for ss in by_layer.values()) * Hs
    height = MY * 2 + (max(by_layer) + 1) * V
    return pos, d, W, H, width, height


def drawio(bp, perk_steps=None):
    states = annotated_states(bp, perk_steps)
    terms, entry = set(bp.get("terminal_states", {})), bp["entry_state"]
    pos, d, W, H, _, _ = _layout(bp)
    cells = []
    for s in bp["states"]:
        x, y = pos[s]
        fill, stroke = ("#d5e8d4", "#82b366") if s in terms else (("#dae8fc", "#6c8ebf") if s == entry else ("#f5f5f5", "#666666"))
        val = E(f"{s}\n{states[s].get('description','')}").replace("\n", "&#10;")
        cells.append(f'<mxCell id="s_{s}" value="{val}" style="rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};align=left;verticalAlign=top;spacing=6;spacingTop=4;fontSize=11;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{W}" height="{H}" as="geometry"/></mxCell>')
    for i, t in enumerate(bp["transitions"]):
        sub = " / ".join(x for x in [t.get("action"), ("⊨ " + t["gate"]) if t.get("gate") else None] if x)
        label = E(t.get("trigger", "") + ("\n" + sub if sub else "")).replace("\n", "&#10;")
        cells.append(f'<mxCell id="t_{i}" value="{label}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;fontSize=10;endArrow=block;strokeColor=#444444;" edge="1" parent="1" source="s_{t["from"]}" target="s_{t["to"]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    body = "\n        ".join(cells)
    return (f'<mxfile host="cyberware">\n  <diagram name="{E(bp.get("id","skill"))}">\n'
            f'    <mxGraphModel dx="900" dy="700" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100">\n'
            f'      <root>\n        <mxCell id="0"/>\n        <mxCell id="1" parent="0"/>\n        {body}\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n')


def svg(bp, perk_steps=None):
    states = annotated_states(bp, perk_steps)
    terms, entry = set(bp.get("terminal_states", {})), bp["entry_state"]
    pos, d, W, H, width, height = _layout(bp)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">',
         '<defs><marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#444"/></marker></defs>',
         f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
         f'<text x="14" y="20" font-size="13" font-weight="700" fill="#333">{E(bp.get("id","skill"))}</text>']
    for t in bp["transitions"]:
        sx, sy = pos[t["from"]]; tx, ty = pos[t["to"]]
        if d[t["to"]] > d[t["from"]]:
            x1, y1, x2, y2 = sx + W / 2, sy + H, tx + W / 2, ty
            path = f'M{x1},{y1} C{x1},{y1+45} {x2},{y2-45} {x2},{y2}'
        else:
            x1, y1, x2, y2 = sx + W, sy + H / 2, tx + W, ty + H / 2
            path = f'M{x1},{y1} C{x1+70},{y1} {x2+70},{y2} {x2},{y2}'
        o.append(f'<path d="{path}" fill="none" stroke="#444" stroke-width="1.4" marker-end="url(#arr)"/>')
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        o.append(f'<text x="{mx+5:.0f}" y="{my-2:.0f}" font-size="11" font-weight="600" fill="#333">{E(t.get("trigger",""))}</text>')
        if t.get("action"):
            o.append(f'<text x="{mx+5:.0f}" y="{my+11:.0f}" font-size="9" fill="#999">{E(t["action"])}</text>')
    for s in bp["states"]:
        x, y = pos[s]
        fill, stroke = ("#d5e8d4", "#82b366") if s in terms else (("#dae8fc", "#6c8ebf") if s == entry else ("#f5f5f5", "#aaaaaa"))
        o.append(f'<rect x="{x}" y="{y}" width="{W}" height="{H}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        o.append(f'<text x="{x+11}" y="{y+20}" font-size="13" font-weight="700" fill="#222">{E(s)}</text>')
        for j, line in enumerate(wrap(states[s].get("description", ""), 33)[:4]):
            o.append(f'<text x="{x+11}" y="{y+37+j*12}" font-size="9.5" fill="#555">{E(line)}</text>')
    o.append("</svg>")
    return "\n".join(o) + "\n"


def render(bp, perk_steps, base, fmts):
    written = []
    if "drawio" in fmts:
        open(base + ".drawio", "w").write(drawio(bp, perk_steps)); written.append(base + ".drawio")
    if "svg" in fmts:
        open(base + ".svg", "w").write(svg(bp, perk_steps)); written.append(base + ".svg")
    return written


def main():
    ap = argparse.ArgumentParser(description="render an L++ blueprint as draw.io XML + SVG")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--skill")
    g.add_argument("--blueprint")
    g.add_argument("--ledger")
    ap.add_argument("-o", "--out", default=None, help="base path (writes <base>.drawio + <base>.svg)")
    ap.add_argument("--format", choices=["drawio", "svg", "both"], default="both")
    a = ap.parse_args()
    perk_steps = None
    if a.ledger:
        L = json.load(open(a.ledger)); skill = L["skill"]
        man = json.load(open(os.path.join(ROOT, "skills", skill, "perks", L["perk"], "manifesto.json")))
        perk_steps = man.get("sequence")
        bp = json.load(open(os.path.join(ROOT, "skills", skill, "blueprint.json")))
        default_base = os.path.join(ROOT, "skills", skill, "blueprint")
    else:
        path = a.blueprint or os.path.join(ROOT, "skills", a.skill, "blueprint.json")
        bp = json.load(open(path))
        default_base = os.path.join(ROOT, "skills", a.skill, "blueprint") if a.skill else path.rsplit(".", 1)[0]
    base = (a.out or default_base)
    base = base[:-7] if base.endswith(".drawio") else (base[:-4] if base.endswith(".svg") else base)
    fmts = ["drawio", "svg"] if a.format == "both" else [a.format]
    written = render(bp, perk_steps, base, fmts)
    print("wrote " + " + ".join(written) + f"  ({len(bp['states'])} states, {len(bp['transitions'])} transitions)")


if __name__ == "__main__":
    main()
