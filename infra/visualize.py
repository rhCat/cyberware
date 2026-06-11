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


def _pretty(expr):
    """L++ operators → readable glyphs for the diagram."""
    return expr.replace("/\\", "∧").replace("\\/", "∨").replace("/=", "≠").replace("~", "¬")


# theme
_NEON, _ON, _DIM, _BG, _EDGE = "#39ff14", "#aaff7a", "#5cc746", "#0a0f0a", "#7dff4d"
_SIZE = {"state": (228, 70), "gate": (150, 56), "action": (212, 46)}


def _sequence(bp, gates):
    """Walk the chain from entry → a vertical list of (kind, id, trigger-into-this-node)."""
    trans, seq, visited, cur = bp["transitions"], [], set(), bp["entry_state"]
    while cur and cur not in visited:
        visited.add(cur)
        seq.append(("state", cur, None))
        outs = [t for t in trans if t["from"] == cur]
        if not outs:
            break
        t = outs[0]
        if t.get("gate") and t["gate"] in gates:
            seq.append(("gate", t["gate"], t.get("trigger", "")))
            seq.append(("action", t.get("action", ""), None))
        else:
            seq.append(("action", t.get("action", ""), t.get("trigger", "")))
        cur = t["to"]
    for s in bp["states"]:
        if s not in visited:
            seq.append(("state", s, None))
    return seq


def svg(bp, perk_steps=None):
    """Flowchart SVG (cyberpunk): states=rectangles, transitions=lines, gates=diamonds, actions=predefined-process."""
    states, terms, entry = bp["states"], set(bp.get("terminal_states", {})), bp["entry_state"]
    gates, actions = bp.get("gates", {}), bp.get("actions", {})
    seq = _sequence(bp, gates)
    CX, GAP, SIDE = 162, 30, 296

    def side_of(kind, ident):
        if kind == "gate":
            return "⊨ " + _pretty(gates.get(ident, {}).get("expression", ""))
        if kind == "action":
            cu = actions.get(ident, {}).get("compute_unit", ident)
            return "▶ " + " → ".join(perk_steps) if (perk_steps and "perk:sequence" in cu) else ""
        return ""

    y, nodes, maxside = 46, [], 0
    for kind, ident, trig in seq:
        w, h = _SIZE[kind]
        nodes.append((kind, ident, CX - w / 2, y, w, h, trig))
        maxside = max(maxside, len(side_of(kind, ident)))
        y += h + GAP
    height, width = y + 8, max(540, SIDE + maxside * 6 + 24)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
         'font-family="ui-monospace,Menlo,Consolas,monospace">',
         '<defs>'
         '<filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="1.8" result="b"/>'
         '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
         f'<pattern id="px" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="{_BG}"/>'
         f'<rect width="1" height="1" fill="{_NEON}" fill-opacity="0.16"/></pattern>'
         f'<marker id="arr" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 z" fill="{_EDGE}"/></marker>'
         '</defs>',
         f'<rect width="{width}" height="{height}" fill="{_BG}"/>',
         f'<rect width="{width}" height="{height}" fill="url(#px)"/>',
         f'<text x="14" y="26" font-size="14" font-weight="700" letter-spacing="3" fill="{_NEON}" filter="url(#glow)">{E(bp.get("id","skill")).upper()}</text>']

    # transitions = lines (drawn first; bright + crisp so they read clearly)
    for k in range(len(nodes) - 1):
        a, b = nodes[k], nodes[k + 1]
        ax, ay, bx, by = a[2] + a[4] / 2, a[3] + a[5], b[2] + b[4] / 2, b[3]
        o.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="{_NEON}" stroke-width="5" opacity="0.22" filter="url(#glow)"/>')
        o.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="{_EDGE}" stroke-width="1.8" marker-end="url(#arr)"/>')
        if b[6]:
            o.append(f'<text x="{ax+12:.0f}" y="{(ay+by)/2+4:.0f}" font-size="11" font-weight="700" fill="{_ON}">{E(b[6])}</text>')

    for kind, ident, x, y, w, h, _trig in nodes:
        cx = x + w / 2
        if kind == "state":
            is_term, is_entry = ident in terms, ident == entry
            border = _ON if (is_entry or is_term) else _NEON
            fill = "#0f2410" if is_term else ("#0e1d0d" if is_entry else "#0b140a")
            o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{border}" stroke-width="{2 if (is_term or is_entry) else 1.4}" filter="url(#glow)"/>')
            tag = "  ▶ entry" if is_entry else ("  ■ terminal" if is_term else "")
            o.append(f'<text x="{x+12}" y="{y+20}" font-size="13" font-weight="700" letter-spacing="1" fill="{border}" filter="url(#glow)">{E(ident).upper()}<tspan font-size="8" letter-spacing="0" fill="{_DIM}">{tag}</tspan></text>')
            for j, line in enumerate(wrap(states[ident].get("description", ""), 33)[:3]):
                o.append(f'<text x="{x+12}" y="{y+37+j*12}" font-size="9.5" fill="{_DIM}">{E(line)}</text>')
        elif kind == "gate":
            o.append(f'<polygon points="{cx},{y} {x+w},{y+h/2} {cx},{y+h} {x},{y+h/2}" fill="#0c1a0c" stroke="{_NEON}" stroke-width="1.7" filter="url(#glow)"/>')
            o.append(f'<text x="{cx:.0f}" y="{y+h/2-1:.0f}" font-size="9" text-anchor="middle" fill="{_NEON}">{E(ident)}</text>')
            o.append(f'<text x="{cx:.0f}" y="{y+h/2+9:.0f}" font-size="7" text-anchor="middle" fill="{_DIM}">GATE</text>')
            o.append(f'<text x="{x+w+14:.0f}" y="{y+h/2+3:.0f}" font-size="10" fill="{_ON}">{E(side_of("gate", ident))}</text>')
        else:  # action — predefined-process (rectangle with double vertical rules at each end)
            o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#0a1609" stroke="{_NEON}" stroke-width="1.4" filter="url(#glow)"/>')
            o.append(f'<line x1="{x+7}" y1="{y}" x2="{x+7}" y2="{y+h}" stroke="{_NEON}" stroke-width="1.2"/>')
            o.append(f'<line x1="{x+w-7}" y1="{y}" x2="{x+w-7}" y2="{y+h}" stroke="{_NEON}" stroke-width="1.2"/>')
            cu = actions.get(ident, {}).get("compute_unit", ident)
            o.append(f'<text x="{cx:.0f}" y="{y+h/2-2:.0f}" font-size="10" font-weight="600" text-anchor="middle" fill="{_ON}">{E(cu)}</text>')
            o.append(f'<text x="{cx:.0f}" y="{y+h/2+10:.0f}" font-size="7.5" text-anchor="middle" fill="{_DIM}">{E(ident)} · action</text>')
            sd = side_of("action", ident)
            if sd:
                o.append(f'<text x="{x+w+14:.0f}" y="{y+h/2+3:.0f}" font-size="10" fill="{_NEON}">{E(sd)}</text>')
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
