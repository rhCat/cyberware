/* cyberware — the global site toolbar.
 * One self-contained file, included on every page: a system-bar-style strip at the top with cross-page
 * navigation, the current page, and a live status (pulse + version + clock). It AUTO-HIDES on scroll-down
 * and reveals on scroll-up, near the top, or when the pointer moves to the top edge. No dependencies. */
(function () {
  if (window.__cwbar) return;
  window.__cwbar = 1;

  var path = (location.pathname || "/").replace(/index\.html$/, "").replace(/\/+$/, "") || "/";
  var NAV = [["/", "home"], ["/explore.html", "explore"], ["/dashboard.html", "registry"], ["/atlas.html", "atlas"]];
  function active(href) {
    var h = href.replace(/\/+$/, "") || "/";
    return path === h || path === h.replace(/\.html$/, "");
  }
  // breadcrumb: the current page name on a sub-page (from <title>, before the " · cyberware" suffix)
  var crumb = "";
  if (path !== "/") {
    crumb = (document.title || "").split("·")[0].trim();
    if (crumb.length > 44) crumb = crumb.slice(0, 44) + "…";
  }

  var css =
    ".cw-bar{position:fixed;top:0;left:0;right:0;z-index:99999;display:flex;align-items:center;gap:16px;" +
    "height:36px;padding:0 14px;box-sizing:border-box;font:12.5px/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;" +
    "color:#cfe9dd;background:rgba(9,13,12,.86);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);" +
    "border-bottom:1px solid #1d2a26;transition:transform .26s cubic-bezier(.4,0,.2,1);}" +
    ".cw-bar.cw-hide{transform:translateY(-101%);}" +
    ".cw-bar a{text-decoration:none;}" +
    ".cw-mark{color:#39FF6A;font-weight:600;letter-spacing:.3px;}" +
    ".cw-nav{display:flex;gap:13px;}" +
    ".cw-nav a{color:#7fa394;}.cw-nav a:hover{color:#cfe9dd;}" +
    ".cw-nav a.cw-on{color:#37e0e0;text-shadow:0 0 8px rgba(55,224,224,.45);}" +
    ".cw-crumb{color:#56756a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.cw-crumb b{color:#9af5c0;font-weight:500;}" +
    ".cw-status{margin-left:auto;display:flex;align-items:center;gap:9px;color:#56756a;flex:none;}" +
    ".cw-dot{width:7px;height:7px;border-radius:50%;background:#39FF6A;box-shadow:0 0 7px #39FF6A;animation:cwpulse 2.4s ease-in-out infinite;}" +
    ".cw-ver{color:#7fa394;}.cw-clock{color:#9af5c0;font-variant-numeric:tabular-nums;letter-spacing:.5px;}" +
    "@keyframes cwpulse{0%,100%{opacity:1}50%{opacity:.35}}" +
    "@media(prefers-reduced-motion:reduce){.cw-bar{transition:none}.cw-dot{animation:none}}" +
    "@media(max-width:680px){.cw-crumb,.cw-ver{display:none}}" +
    "@media(max-width:430px){.cw-mark span{display:none}}";

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var bar = document.createElement("div");
  bar.className = "cw-bar";
  bar.setAttribute("role", "navigation");
  bar.setAttribute("aria-label", "site");
  bar.innerHTML =
    '<a class="cw-mark" href="/">▸ <span>cyberware</span></a>' +
    '<nav class="cw-nav">' +
    NAV.map(function (n) { return '<a href="' + n[0] + '"' + (active(n[0]) ? ' class="cw-on"' : "") + ">" + n[1] + "</a>"; }).join("") +
    "</nav>" +
    (crumb ? '<span class="cw-crumb">/ <b></b></span>' : "") +
    '<span class="cw-status"><span class="cw-dot" title="governed"></span><span class="cw-ver">v1.1</span><span class="cw-clock"></span></span>';
  document.body.insertBefore(bar, document.body.firstChild);
  if (crumb) bar.querySelector(".cw-crumb b").textContent = crumb;   // textContent: never inject the title as HTML

  var clk = bar.querySelector(".cw-clock");
  function tick() { clk.textContent = new Date().toTimeString().slice(0, 8); }
  tick();
  setInterval(tick, 1000);

  // auto-hide: hide while scrolling down, reveal on scroll-up / near the top / pointer at the top edge
  var last = window.scrollY || 0, queued = false;
  function update() {
    var y = window.scrollY || 0;
    if (y < 8) bar.classList.remove("cw-hide");
    else if (y > last + 5) bar.classList.add("cw-hide");
    else if (y < last - 5) bar.classList.remove("cw-hide");
    last = y;
    queued = false;
  }
  addEventListener("scroll", function () { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
  addEventListener("mousemove", function (e) { if (e.clientY < 52) bar.classList.remove("cw-hide"); }, { passive: true });
})();
