export function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function domainOf(value) {
  const name = String(value || "").trim();
  return name || "default";
}

export function pretty(doc) {
  return JSON.stringify(doc, null, 2);
}

export function highlightJson(text) {
  const src = String(text ?? "");
  const re = /("(?:\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g;
  let out = "";
  let last = 0;
  let match;
  while ((match = re.exec(src))) {
    out += esc(src.slice(last, match.index));
    const token = match[0];
    let cls = "cfg-jn";
    if (token.startsWith("\"")) cls = /:$/.test(token) ? "cfg-jk" : "cfg-js";
    else if (/true|false/.test(token)) cls = "cfg-jb";
    else if (/null/.test(token)) cls = "cfg-ju";
    let tokenHtml = esc(token);
    if (cls === "cfg-js") {
      tokenHtml = tokenHtml.replace(/\{[A-Za-z_][A-Za-z0-9_-]*\.[A-Za-z_][A-Za-z0-9_]*\}/g, (bit) => `<span class="cfg-jvar">${bit}</span>`);
    }
    out += `<span class="${cls}">${tokenHtml}</span>`;
    last = match.index + token.length;
  }
  return out + esc(src.slice(last));
}

export function toast(message) {
  let el = document.getElementById("cfgToast");
  if (!el) {
    el = document.createElement("div");
    el.id = "cfgToast";
    el.style.cssText = [
      "position:fixed", "bottom:24px", "right:24px", "z-index:9999",
      "background:var(--surface)", "border:1px solid var(--border)",
      "padding:10px 14px", "border-radius:10px", "font-size:12.5px",
      "box-shadow:var(--shadow)", "opacity:0", "transition:opacity .2s",
    ].join(";");
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.style.opacity = "1";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.style.opacity = "0"; }, 2400);
}
