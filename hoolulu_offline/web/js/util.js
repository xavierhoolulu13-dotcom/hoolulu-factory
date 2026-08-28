// Small dependency-free helpers shared by the whole app.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (k === 'style' && typeof v === 'object') Object.assign(node.style, v);
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const c of [].concat(children)) {
    if (c == null || c === false) continue;
    node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return node;
}

export function clear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export const uid = () =>
  (crypto.randomUUID ? crypto.randomUUID()
    : 'id-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10));

export const now = () => Date.now();

export function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function debounce(fn, ms = 300) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ---------------------------------------------------------------- formatting

export function money(n, currency = 'USD') {
  const v = Number(n) || 0;
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency', currency,
      maximumFractionDigits: Math.abs(v) < 100 && !Number.isInteger(v) ? 2 : 0,
    }).format(v);
  } catch { return '$' + v.toFixed(0); }
}

export function num(n) {
  return new Intl.NumberFormat().format(Number(n) || 0);
}

export function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function fmtTime(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

export function relTime(ts) {
  if (!ts) return 'never';
  const diff = Date.now() - ts;
  const s = Math.round(diff / 1000);
  if (s < 45) return 'just now';
  if (s < 3600) return Math.round(s / 60) + 'm ago';
  if (s < 86400) return Math.round(s / 3600) + 'h ago';
  return Math.round(s / 86400) + 'd ago';
}

export function hours(seconds) {
  const h = (Number(seconds) || 0) / 3600;
  return h >= 10 ? h.toFixed(0) : h.toFixed(2);
}

export function slug(s, fallback = 'item') {
  const out = String(s || '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48);
  return out || fallback;
}

export function download(filename, data, type = 'application/octet-stream') {
  const blob = data instanceof Blob ? data : new Blob([data], { type });
  const url = URL.createObjectURL(blob);
  const a = el('a', { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

// ------------------------------------------------------------------- toasts

let toastRoot = null;
export function toast(message, kind = 'info', ms = 3600) {
  if (!toastRoot) {
    toastRoot = el('div', { class: 'toast-root' });
    document.body.appendChild(toastRoot);
  }
  const t = el('div', { class: `toast toast-${kind}`, text: message });
  toastRoot.appendChild(t);
  requestAnimationFrame(() => t.classList.add('in'));
  setTimeout(() => {
    t.classList.remove('in');
    setTimeout(() => t.remove(), 300);
  }, ms);
}

// --------------------------------------------------- minimal ZIP (store) writer
// Enough to export a project as a real .zip with no dependencies.

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** files: [{ path, content }] -> Blob (zip, stored/uncompressed) */
export function makeZip(files) {
  const enc = new TextEncoder();
  const locals = [], centrals = [];
  let offset = 0;

  for (const f of files) {
    const nameBytes = enc.encode(f.path);
    const data = enc.encode(String(f.content ?? ''));
    const crc = crc32(data);
    const dosTime = (((new Date().getHours() & 31) << 11) |
      ((new Date().getMinutes() & 63) << 5) |
      ((new Date().getSeconds() / 2) & 31)) & 0xffff;
    const dosDate = (((new Date().getFullYear() - 1980) & 127) << 9) |
      (((new Date().getMonth() + 1) & 15) << 5) | (new Date().getDate() & 31);

    const local = new Uint8Array(30 + nameBytes.length + data.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(4, 20, true);        // version needed
    lv.setUint16(6, 0, true);         // flags
    lv.setUint16(8, 0, true);         // method: store
    lv.setUint16(10, dosTime, true);
    lv.setUint16(12, dosDate, true);
    lv.setUint32(14, crc, true);
    lv.setUint32(18, data.length, true);
    lv.setUint32(22, data.length, true);
    lv.setUint16(26, nameBytes.length, true);
    lv.setUint16(28, 0, true);        // extra len
    local.set(nameBytes, 30);
    local.set(data, 30 + nameBytes.length);
    locals.push(local);

    const central = new Uint8Array(46 + nameBytes.length);
    const cv = new DataView(central.buffer);
    cv.setUint32(0, 0x02014b50, true);
    cv.setUint16(4, 20, true);
    cv.setUint16(6, 20, true);
    cv.setUint16(8, 0, true);
    cv.setUint16(10, 0, true);
    cv.setUint16(12, dosTime, true);
    cv.setUint16(14, dosDate, true);
    cv.setUint32(16, crc, true);
    cv.setUint32(20, data.length, true);
    cv.setUint32(24, data.length, true);
    cv.setUint16(28, nameBytes.length, true);
    cv.setUint16(30, 0, true);
    cv.setUint16(32, 0, true);
    cv.setUint16(34, 0, true);
    cv.setUint16(36, 0, true);
    cv.setUint32(38, 0, true);
    cv.setUint32(42, offset, true);
    central.set(nameBytes, 46);
    centrals.push(central);

    offset += local.length;
  }

  const centralSize = centrals.reduce((n, c) => n + c.length, 0);
  const end = new Uint8Array(22);
  const ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, centrals.length, true);
  ev.setUint16(10, centrals.length, true);
  ev.setUint32(12, centralSize, true);
  ev.setUint32(16, offset, true);
  ev.setUint16(20, 0, true);

  return new Blob([...locals, ...centrals, end], { type: 'application/zip' });
}

// ------------------------------------------------------------- markdown

const splitRow = (line) =>
  line.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());

const isSeparatorRow = (line) => {
  const t = String(line).trim();
  return t.startsWith('|') && t.endsWith('|') && t.includes('-') && /^[\s|:-]+$/.test(t);
};

const alignOf = (cell) =>
  /^:-+:$/.test(cell) ? 'center' : /^-+:$/.test(cell) ? 'right' : /^:-+$/.test(cell) ? 'left' : '';

function renderTable(headers, aligns, rows) {
  const cell = (tag, text, idx) => {
    const a = aligns[idx] ? ` style="text-align:${aligns[idx]}"` : '';
    return `<${tag}${a}>${inline(text)}</${tag}>`;
  };
  const head = `<tr>${headers.map((h, i) => cell('th', h, i)).join('')}</tr>`;
  const body = rows.map(r =>
    `<tr>${headers.map((_, i) => cell('td', r[i] == null ? '' : r[i], i)).join('')}</tr>`).join('');
  return `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

const BLOCK_START = /^(```|\||>|-{3,}$|\*{3,}$|#{1,4}\s|[-*]\s|\d+[.)]\s)/;

/**
 * Small but correct markdown renderer: headings, fenced code, tables
 * (with alignment), ordered/unordered lists, blockquotes, rules, inline
 * code/bold/italic/links. Escapes HTML first, so untrusted text is safe.
 */
export function renderMarkdown(src) {
  const lines = String(src == null ? '' : src).split('\n');
  const out = [];
  let i = 0;

  while (i < lines.length) {
    const t = lines[i].trim();

    // fenced code -------------------------------------------------------
    if (t.startsWith('```')) {
      const buf = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) { buf.push(lines[i]); i++; }
      i++; // consume the closing fence
      out.push(`<pre><code>${escapeHtml(buf.join('\n'))}</code></pre>`);
      continue;
    }

    // table -------------------------------------------------------------
    if (t.startsWith('|') && i + 1 < lines.length && isSeparatorRow(lines[i + 1])) {
      const headers = splitRow(t);
      const aligns = splitRow(lines[i + 1].trim()).map(alignOf);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(splitRow(lines[i].trim()));
        i++;
      }
      out.push(renderTable(headers, aligns, rows));
      continue;
    }

    // heading -----------------------------------------------------------
    const h = t.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      const lvl = Math.min(6, h[1].length + 1); // # -> h2, ## -> h3, …
      out.push(`<h${lvl}>${inline(h[2])}</h${lvl}>`);
      i++;
      continue;
    }

    // blockquote --------------------------------------------------------
    if (t.startsWith('>')) {
      const buf = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        buf.push(lines[i].trim().replace(/^>\s?/, ''));
        i++;
      }
      out.push(`<blockquote>${renderMarkdown(buf.join('\n'))}</blockquote>`);
      continue;
    }

    // horizontal rule ---------------------------------------------------
    if (/^(-{3,}|\*{3,})$/.test(t)) { out.push('<hr>'); i++; continue; }

    // lists -------------------------------------------------------------
    if (/^[-*]\s+/.test(t) || /^\d+[.)]\s+/.test(t)) {
      const ordered = /^\d+[.)]\s+/.test(t);
      const items = [];
      while (i < lines.length) {
        const lt = lines[i].trim();
        const m = ordered ? lt.match(/^\d+[.)]\s+(.*)$/) : lt.match(/^[-*]\s+(.*)$/);
        if (!m) break;
        items.push(m[1]);
        i++;
      }
      const tag = ordered ? 'ol' : 'ul';
      out.push(`<${tag}>${items.map(x => `<li>${inline(x)}</li>`).join('')}</${tag}>`);
      continue;
    }

    // blank -------------------------------------------------------------
    if (!t) { i++; continue; }

    // paragraph ---------------------------------------------------------
    const buf = [];
    while (i < lines.length) {
      const lt = lines[i].trim();
      if (!lt || BLOCK_START.test(lt)) break;
      buf.push(lt);
      i++;
    }
    if (buf.length) out.push(`<p>${inline(buf.join(' '))}</p>`);
  }

  return out.join('\n');
}

function inline(s) {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|\W)_([^_]+)_(?=\W|$)/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
}
