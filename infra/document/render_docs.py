#!/usr/bin/env python3
"""render_docs — build the docs HUB (explore.html) + a rendered page per doc, for the static site.

The homepage stays a single page; this adds a topic hub and one standalone page per markdown doc so the
"tons of materials" become discoverable, deep-linkable routes. Each doc page is a thin shell that
client-side-renders its OWN already-published `.md` with the SAME tiny markdown renderer the registry
dashboard uses (so rendering is consistent and the prose never gets duplicated/stale). The hub groups the
docs by topic and links the two live tools (the registry dashboard + the intent atlas).

  python3 infra/document/render_docs.py --out _site        # writes _site/explore.html + _site/docs/<name>.html

Run it in the deploy AFTER the docs/*.md are copied into _site/docs/. Standard library only.
"""
from __future__ import annotations
import argparse
import html
import os
import sys

# --- the curated topic map: every group -> the docs it surfaces (name, title, blurb) ------------------
TOPICS = [
    {"group": "Start here", "blurb": "the thesis and the contract", "docs": [
        ("governed-vs-free", "Governed vs free", "free up to the gate, accountable past it — and why an agent is software's newest customer"),
        ("SPEC", "The specification", "the normative contract: the claim, the value-free plan, the wire"),
    ]},
    {"group": "Architecture", "blurb": "how the kernel is built", "docs": [
        ("architecture", "Architecture", "four planes, the value-free plan, the SV-3 boundary, key custody, supply-chain attestation, the store contract"),
        ("governance-service", "The governance server", "govd's HTTP + WebSocket oversight, authenticity, the dashboard, and the persistence backends"),
        ("containment-delegation", "Containment and delegation", "exod, the bwrap/gVisor sandbox, the closure time-of-use gate, cooperative vs delegated"),
        ("cyberware", "The local pipeline", "the server-less path: validator → composer → compiler → oversight → executor"),
    ]},
    {"group": "Security", "blurb": "the access-control and provenance surface", "docs": [
        ("per-actor-acl-design", "Per-actor ACL", "M0/M1/M2 — per-token capability scope, the operator attestation, the possession proof"),
    ]},
    {"group": "Economy", "blurb": "priced, metered, settled", "docs": [
        ("settlement", "Settlement", "exact-decimal money, funded-escrow admission, dual-signed payout, disputes, reputation, FMV, the capstone"),
    ]},
    {"group": "Build and author", "blurb": "writing the skills", "docs": [
        ("authoring", "Authoring", "scaffold a skill, the blueprint + perks, visualize the flow"),
        ("skills", "The skill catalog", "what each governed skill does"),
    ]},
    {"group": "Operate and roadmap", "blurb": "running it, and what is next", "docs": [
        ("DEVELOPMENT", "Development", "local loops, the fleet, the source-distribution model"),
        ("ROADMAP", "Roadmap", "what is deliberately deferred — org isolation, the Phase-B flip, settlement hardening"),
        ("pm-report", "Progress report", "the v1.1 milestone roll-up"),
    ]},
]

TOOLS = [
    ("dashboard.html", "Registry dashboard", "browse every governed skill — blueprint, perk flow, contracts, snippet code", "◉"),
    ("atlas.html", "Intent atlas", "319 functions + 53 flows, each linked to source; the documented-vs-left coverage", "▦"),
]

CSS = r"""
:root{--bg:#0a0e0d;--panel:#0f1614;--panel2:#0c1211;--edge:#1d2a26;--edge2:#243a33;--ink:#cfe9dd;
  --dim:#7fa394;--faint:#56756a;--green:#39FF6A;--cyan:#37e0e0;--mint:#9af5c0;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 var(--mono);
  background-image:radial-gradient(1100px 560px at 82% -12%,#0d1a16 0,transparent 60%);}
a{color:var(--cyan);text-decoration:none}a:hover{text-decoration:underline}
header{position:sticky;top:0;z-index:5;padding:14px 20px;border-bottom:1px solid var(--edge);
  background:linear-gradient(#0b1110ee,#0b1110cc);backdrop-filter:blur(6px);display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
header .crumb{color:var(--faint);font-size:13px}
header a.home{color:var(--green)} header .sep{color:var(--faint)}
.wrap{max-width:880px;margin:0 auto;padding:26px 20px 80px}
h1{font-size:22px;letter-spacing:.4px} .gsig{color:var(--green)}
.lead{color:var(--dim)}
.groups{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));margin-top:18px}
.grp{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:15px 17px}
.grp h2{font-size:13px;letter-spacing:.6px;text-transform:uppercase;color:var(--cyan);margin:0 0 2px}
.grp .gb{color:var(--faint);font-size:12px;margin-bottom:10px}
.grp a.item{display:block;padding:8px 10px;border:1px solid transparent;border-left:2px solid var(--edge2);
  border-radius:0 8px 8px 0;margin:6px 0;background:var(--panel2)}
.grp a.item:hover{border-color:var(--edge2);border-left-color:var(--green);text-decoration:none}
.grp a.item b{color:var(--mint);font-weight:600} .grp a.item span{display:block;color:var(--dim);font-size:12px}
.tools a.item b{color:var(--green)} .tools .ic{color:var(--cyan);margin-right:6px}
.doc h1,.doc h2,.doc h3,.doc h4{line-height:1.3;margin:1.5em 0 .5em} .doc h1{font-size:22px}
.doc h2{font-size:18px;color:var(--cyan);border-bottom:1px solid var(--edge);padding-bottom:.25em}
.doc h3{font-size:15.5px;color:var(--mint)} .doc h4{font-size:14px;color:var(--dim)}
.doc p{margin:.7em 0} .doc strong,.doc b{color:var(--mint)}
.doc code{background:#10201a;border:1px solid var(--edge2);border-radius:4px;padding:.05em .35em;font-size:.92em;color:var(--mint)}
.doc pre{background:var(--panel2);border:1px solid var(--edge);border-radius:9px;padding:13px 15px;overflow:auto;font-size:13px;line-height:1.5}
.doc pre code{background:none;border:none;padding:0}
.doc blockquote{border-left:3px solid var(--green);margin:.8em 0;padding:.2em 0 .2em 14px;color:var(--dim);background:#0d1512}
.doc ul,.doc ol{padding-left:22px} .doc li{margin:.3em 0}
.doc a{border-bottom:1px dotted var(--edge2)}
.doc table.mdt{border-collapse:collapse;width:100%;font-size:13px;margin:1em 0}
.doc table.mdt th{text-align:left;color:var(--faint);border-bottom:1px solid var(--edge2);padding:6px 10px;font-weight:500}
.doc table.mdt td{padding:6px 10px;border-bottom:1px solid var(--panel)}
.doc table.mdt tr:hover td{background:var(--panel2)}
.foot{margin-top:40px;padding-top:16px;border-top:1px solid var(--edge);color:var(--faint);font-size:12px}
.loading{color:var(--faint)}
"""

MD_JS = r"""
const esc=s=>(s==null?'':String(s)).replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
function md(src){
  src=src.replace(/^---[\s\S]*?---\s*/,"");
  const L=src.split("\n"),out=[];let i=0;
  const inline=t=>esc(t)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2">$1</a>')
    .replace(/\*\*(.+?)\*\*/g,"<b>$1</b>")
    .replace(/`([^`]+)`/g,"<code>$1</code>");
  const cells=l=>l.replace(/^\s*\|/,"").replace(/\|\s*$/,"").split("|").map(c=>c.trim());
  while(i<L.length){
    const line=L[i];
    if(line.startsWith("```")){const c=[];i++;while(i<L.length&&!L[i].startsWith("```"))c.push(L[i++]);i++;out.push("<pre><code>"+esc(c.join("\n"))+"</code></pre>");continue;}
    if(line.includes("|")&&i+1<L.length&&/^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/.test(L[i+1])){
      const head=cells(line);i+=2;const rows=[];
      while(i<L.length&&L[i].includes("|"))rows.push(cells(L[i++]));
      out.push('<table class="mdt"><thead><tr>'+head.map(c=>"<th>"+inline(c)+"</th>").join("")+"</tr></thead><tbody>"+rows.map(r=>"<tr>"+r.map(c=>"<td>"+inline(c)+"</td>").join("")+"</tr>").join("")+"</tbody></table>");continue;}
    let m;
    if((m=line.match(/^(#{1,6})\s+(.*)/))){const n=m[1].length;out.push("<h"+n+">"+inline(m[2])+"</h"+n+">");i++;continue;}
    if(/^[-*]\s+/.test(line)){const items=[];while(i<L.length&&/^[-*]\s+/.test(L[i])){let it=L[i++].replace(/^[-*]\s+/,"");while(i<L.length&&/^\s+\S/.test(L[i]))it+=" "+L[i++].trim();items.push("<li>"+inline(it)+"</li>");}out.push("<ul>"+items.join("")+"</ul>");continue;}
    if(/^\d+\.\s+/.test(line)){const items=[];while(i<L.length&&/^\d+\.\s+/.test(L[i])){let it=L[i++].replace(/^\d+\.\s+/,"");while(i<L.length&&/^\s+\S/.test(L[i]))it+=" "+L[i++].trim();items.push("<li>"+inline(it)+"</li>");}out.push("<ol>"+items.join("")+"</ol>");continue;}
    if(line.match(/^>\s?(.*)/)){out.push("<blockquote>"+inline(line.replace(/^>\s?/,""))+"</blockquote>");i++;continue;}
    if(/^([-*_])\1{2,}\s*$/.test(line.trim())){out.push("<hr>");i++;continue;}
    if(line.trim()===""){i++;continue;}
    out.push("<p>"+inline(line)+"</p>");i++;
  }
  return out.join("\n");
}
"""

DOC_TMPL = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · cyberware</title>
<style>__CSS__</style></head><body>
<header><a class="home" href="/">▸ cyberware</a><span class="sep">/</span>
<a href="/explore.html">explore</a><span class="sep">/</span><span class="crumb">__TITLE__</span></header>
<div class="wrap"><article class="doc md" id="doc"><p class="loading">loading __SRC__ …</p></article>
<div class="foot">Source: <a href="https://github.com/rhCat/cyberware/blob/main/__SRC__">__SRC__</a> ·
<a href="/explore.html">← all topics</a></div></div>
<script>__MDJS__
fetch("__MDURL__").then(r=>r.ok?r.text():Promise.reject(r.status))
 .then(t=>{document.getElementById("doc").innerHTML=md(t);})
 .catch(e=>{document.getElementById("doc").innerHTML='<p class="loading">could not load __SRC__ ('+e+')</p>';});
</script></body></html>
"""

HUB_TMPL = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Explore · cyberware</title>
<style>__CSS__</style></head><body>
<header><a class="home" href="/">▸ cyberware</a><span class="sep">/</span><span class="crumb">explore the docs</span></header>
<div class="wrap">
<h1><span class="gsig">▸</span> Explore</h1>
<p class="lead">The homepage is the pitch; this is the material. Every doc is its own page, and the two live tools below browse the running registry.</p>
<div class="groups">__GROUPS__</div>
<div class="foot">cyberware · built in the open · MIT · <a href="https://github.com/rhCat/cyberware">github.com/rhCat/cyberware</a></div>
</div></body></html>
"""


def hub_html() -> str:
    cards = []
    # live tools first
    tools = "".join(
        '<a class="item" href="/%s"><b><span class="ic">%s</span>%s</b><span>%s</span></a>' % (
            html.escape(href), ic, html.escape(title), html.escape(blurb))
        for href, title, blurb, ic in TOOLS)
    cards.append('<div class="grp tools"><h2>Live tools</h2><div class="gb">the running system, not a screenshot</div>%s</div>' % tools)
    for t in TOPICS:
        items = "".join(
            '<a class="item" href="/docs/%s.html"><b>%s</b><span>%s</span></a>' % (
                html.escape(name), html.escape(title), html.escape(blurb))
            for name, title, blurb in t["docs"])
        cards.append('<div class="grp"><h2>%s</h2><div class="gb">%s</div>%s</div>' % (
            html.escape(t["group"]), html.escape(t["blurb"]), items))
    return HUB_TMPL.replace("__CSS__", CSS).replace("__GROUPS__", "".join(cards))


def doc_html(name: str, title: str) -> str:
    src = "cyberware.md" if name == "cyberware" else "docs/%s.md" % name   # cyberware.md lives at the repo root
    return (DOC_TMPL.replace("__CSS__", CSS).replace("__MDJS__", MD_JS)
            .replace("__TITLE__", html.escape(title)).replace("__MDURL__", "/" + src).replace("__SRC__", src))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="build the docs hub (explore.html) + a page per doc")
    ap.add_argument("--out", required=True, help="site output dir (e.g. _site); writes explore.html + docs/<name>.html")
    a = ap.parse_args(argv)
    os.makedirs(os.path.join(a.out, "docs"), exist_ok=True)
    with open(os.path.join(a.out, "explore.html"), "w") as f:
        f.write(hub_html())
    n = 0
    for t in TOPICS:
        for name, title, _ in t["docs"]:
            with open(os.path.join(a.out, "docs", name + ".html"), "w") as f:
                f.write(doc_html(name, title))
            n += 1
    print('{"tool":"render_docs","hub":"%s/explore.html","doc_pages":%d}' % (a.out, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
