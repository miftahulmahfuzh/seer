(function () {
  var LUCIDE = 'https://unpkg.com/lucide@0.460.0/dist/umd/lucide.min.js';
  var NS = 'http://www.w3.org/2000/svg';
  var waiting = new Set();
  var pascal = function (s) { return s.replace(/(^|-)([a-z0-9])/g, function (m, a, b) { return b.toUpperCase(); }); };
  function ensure() {
    if (window.lucide) return true;
    if (!document.querySelector('script[data-lucide-loader]')) {
      var s = document.createElement('script');
      s.src = LUCIDE; s.setAttribute('data-lucide-loader', '1');
      s.onload = function () { waiting.forEach(function (el) { el.render(); }); waiting.clear(); };
      document.head.appendChild(s);
    }
    return false;
  }
  class LuIcon extends HTMLElement {
    static get observedAttributes() { return ['name', 'size', 'stroke']; }
    connectedCallback() { if (!this.shadowRoot) this.attachShadow({ mode: 'open' }); this.style.display = 'inline-flex'; this.style.flex = 'none'; this.render(); }
    attributeChangedCallback() { if (this.isConnected) this.render(); }
    render() {
      if (!this.shadowRoot) return;
      if (!ensure()) { waiting.add(this); return; }
      var size = this.getAttribute('size') || '20';
      var node = window.lucide.icons[pascal(this.getAttribute('name') || '')];
      if (!node) { this.shadowRoot.replaceChildren(); return; }
      if (node[0] === 'svg') node = node[2];
      var svg = document.createElementNS(NS, 'svg');
      var at = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': this.getAttribute('stroke') || '1.75', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' };
      for (var k in at) svg.setAttribute(k, at[k]);
      node.forEach(function (n) { var e = document.createElementNS(NS, n[0]); for (var a in n[1]) e.setAttribute(a, n[1][a]); svg.appendChild(e); });
      svg.style.display = 'block';
      this.shadowRoot.replaceChildren(svg);
    }
  }
  if (!customElements.get('lu-icon')) customElements.define('lu-icon', LuIcon);

  // Tooltips: hover on desktop, long-press on touch. Any element with data-tip.
  var tip, timer, longPressed = false;
  function show(el) {
    var t = el.getAttribute('data-tip'); if (!t) return;
    if (!tip) { tip = document.createElement('div'); tip.setAttribute('role', 'tooltip'); document.body.appendChild(tip); }
    var cs = getComputedStyle(el);
    Object.assign(tip.style, {
      position: 'fixed', zIndex: 9999, pointerEvents: 'none', left: '0px', top: '0px',
      background: cs.getPropertyValue('--ink').trim() || '#20211d', color: cs.getPropertyValue('--sheet').trim() || cs.getPropertyValue('--paper').trim() || '#ffffff',
      font: '500 13px/1.2 Outfit,system-ui,sans-serif', letterSpacing: '0.01em',
      padding: '9px 14px', borderRadius: '999px', whiteSpace: 'nowrap', opacity: '1', transition: 'opacity .12s'
    });
    tip.textContent = t;
    var r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    var x = Math.max(6, Math.min(innerWidth - w - 6, r.left + r.width / 2 - w / 2));
    var y = r.top - h - 8; if (y < 6) y = r.bottom + 8;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hide() { if (tip) tip.style.opacity = '0'; }
  document.addEventListener('mouseover', function (e) {
    var el = e.target.closest && e.target.closest('[data-tip]');
    if (el) show(el); else hide();
  });
  document.addEventListener('touchstart', function (e) {
    var el = e.target.closest && e.target.closest('[data-tip]'); if (!el) return;
    longPressed = false; clearTimeout(timer);
    timer = setTimeout(function () { longPressed = true; show(el); }, 450);
  }, { passive: true });
  document.addEventListener('touchmove', function () { clearTimeout(timer); }, { passive: true });
  document.addEventListener('touchend', function () { clearTimeout(timer); if (longPressed) setTimeout(hide, 1400); });
  document.addEventListener('contextmenu', function (e) { if (e.target.closest && e.target.closest('[data-tip]')) e.preventDefault(); });
  document.addEventListener('click', function (e) {
    if (longPressed) { e.preventDefault(); e.stopPropagation(); longPressed = false; return; }
    var el = e.target.closest && e.target.closest('[data-copy]'); if (!el) return;
    var v = el.getAttribute('data-copy');
    if (navigator.clipboard) navigator.clipboard.writeText(v).catch(function () {});
    var ic = el.querySelector('lu-icon'); if (ic) ic.setAttribute('name', 'check');
    var prev = el.getAttribute('data-tip');
    el.setAttribute('data-tip', 'Copied ' + v); show(el);
    setTimeout(function () { if (ic) ic.setAttribute('name', 'copy'); el.setAttribute('data-tip', prev); hide(); }, 1400);
  }, true);
})();
