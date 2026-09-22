/* Hoolulu Factory Agent — front end. No dependencies, no CDN. */

"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child) node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
};

/* ------------------------------------------------------------------ *
 * Minimal markdown -> HTML (headings, tables, code, lists, quotes)
 * ------------------------------------------------------------------ */

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function inlineMd(text) {
  const codes = [];
  let out = escapeHtml(text).replace(/`([^`]+)`/g, (_, code) => {
    codes.push(code);
    return `\u0000${codes.length - 1}\u0000`;
  });
  out = out
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/_([^_\n]+)_/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return out.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${escapeHtml(codes[+i])}</code>`);
}

function renderMarkdown(src) {
  const lines = String(src || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;

  const isSpecial = (line) =>
    /^```/.test(line) || /^#{1,6}\s/.test(line) || /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) || /^>/.test(line) || /^\|/.test(line) ||
    /^\s*(-{3,}|\*{3,})\s*$/.test(line);

  while (i < lines.length) {
    const line = lines[i];

    if (/^```/.test(line)) {
      const buf = [];
      i += 1;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i += 1; }
      i += 1;
      out.push(`<pre><code>${escapeHtml(buf.join("\n"))}</code></pre>`);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = Math.min(heading[1].length, 4);
      out.push(`<h${level}>${inlineMd(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { out.push("<hr>"); i += 1; continue; }

    if (/^\|/.test(line) && /^\|[\s\-:|]+\|?\s*$/.test(lines[i + 1] || "")) {
      const cells = (row) => row.replace(/^\||\|\s*$/g, "").split("|").map((c) => c.trim());
      const head = cells(line);
      i += 2;
      const body = [];
      while (i < lines.length && /^\|/.test(lines[i])) { body.push(cells(lines[i])); i += 1; }
      out.push(
        "<table><thead><tr>" + head.map((c) => `<th>${inlineMd(c)}</th>`).join("") +
        "</tr></thead><tbody>" +
        body.map((r) => "<tr>" + r.map((c) => `<td>${inlineMd(c)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table>"
      );
      continue;
    }

    if (/^>/.test(line)) {
      const buf = [];
      while (i < lines.length && /^>/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, "")); i += 1; }
      out.push(`<blockquote>${inlineMd(buf.join("\n"))}</blockquote>`);
      continue;
    }

    const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+\.\s+(.*)$/);
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const items = [];
      const pattern = ordered ? /^\s*\d+\.\s+(.*)$/ : /^\s*[-*+]\s+(.*)$/;
      while (i < lines.length) {
        const match = lines[i].match(pattern);
        if (!match) break;
        items.push(match[1]);
        i += 1;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>${items.map((t) => `<li>${inlineMd(t)}</li>`).join("")}</${tag}>`);
      continue;
    }

    if (!line.trim()) { i += 1; continue; }

    const para = [];
    while (i < lines.length && lines[i].trim() && !isSpecial(lines[i])) {
      para.push(lines[i]);
      i += 1;
    }
    out.push(`<p>${inlineMd(para.join("\n")).replace(/\n/g, "<br>")}</p>`);
  }

  return out.join("\n");
}

/* ------------------------------------------------------------------ *
 * Chat
 * ------------------------------------------------------------------ */

const messages = $("#messages");
const input = $("#input");
let busy = false;

const SUGGESTIONS = [
  "status", "run the pipeline", "load demo data", "show leads",
  "add lead \"Sunset Tacos\" city=Kailua phone=808-555-0142 notes=no website",
  "write the message for Kailua Poke Shack", "build me an agent called Review Watcher",
  "check the code", "full report", "help",
];

function addMessage(role, html, trace) {
  const avatar = role === "user" ? "🧑‍💼" : "🤙";
  const bubble = el("div", { class: "bubble", html });
  if (trace && trace.length) bubble.appendChild(renderTrace(trace));
  const node = el("div", { class: `msg ${role}` }, [el("div", { class: "avatar", text: avatar }), bubble]);
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function renderTrace(actions) {
  const wrap = el("div", { class: "trace" });
  for (const action of actions) {
    const args = Object.entries(action.args || {})
      .filter(([k]) => k !== "content")
      .map(([k, v]) => `${k}=${String(v).slice(0, 40)}`)
      .join(" ");
    wrap.appendChild(el("div", { class: `trace-item${action.ok ? "" : " fail"}` }, [
      el("span", { class: "dot" }),
      el("span", { class: "tname", text: action.tool }),
      args ? el("span", { class: "targs", text: args }) : null,
      el("span", { class: "targs", text: action.ok ? "" : String(action.result?.error || "failed").slice(0, 60) }),
    ]));
  }
  return wrap;
}

function addTyping() {
  const bubble = el("div", { class: "bubble", html: '<span class="typing"><i></i><i></i><i></i></span>' });
  const node = el("div", { class: "msg agent" }, [el("div", { class: "avatar", text: "🤙" }), bubble]);
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function toast(text, isError) {
  const node = $("#toast");
  node.textContent = text;
  node.className = `toast${isError ? " err" : ""}`;
  node.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { node.hidden = true; }, 4200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function send(text) {
  const message = (text ?? input.value).trim();
  if (!message || busy) return;
  input.value = "";
  autosize();
  addMessage("user", inlineMd(message));
  const typing = addTyping();
  busy = true;
  $("#send").disabled = true;
  try {
    const data = await api("/api/chat", { method: "POST", body: { message } });
    typing.remove();
    addMessage("agent", renderMarkdown(data.reply || ""), data.actions);
    renderState(data.state);
    pushLog(data.actions);
  } catch (error) {
    typing.remove();
    addMessage("agent", renderMarkdown(`⚠️ Could not reach the agent: \`${error.message}\``));
    toast("Agent unreachable — is the server still running?", true);
  } finally {
    busy = false;
    $("#send").disabled = false;
    input.focus();
  }
}

/* ------------------------------------------------------------------ *
 * State panel
 * ------------------------------------------------------------------ */

let lastState = null;

const STAT_DEFS = [
  { key: "leads", label: "Leads", hot: true },
  { key: "BOOKED", label: "Booked", from: "status" },
  { key: "clients", label: "Clients" },
  { key: "proposals", label: "Proposals" },
  { key: "opportunities", label: "Opps" },
  { key: "tasks_open", label: "Open tasks" },
];

function renderState(state) {
  if (!state) return;
  lastState = state;
  const status = state.status || {};
  const totals = status.totals || {};
  const by = status.by_status || {};

  $("#brain-badge").textContent = `brain: ${state.brain}`;
  $("#brain-badge").className = `badge ${state.llm_configured ? "on" : ""}`;
  const online = status.database_online !== false;
  $("#db-badge").textContent = `db: ${online ? "online" : "missing"}`;
  $("#db-badge").className = `badge ${online ? "on" : "off"}`;

  const values = {
    leads: totals.leads || 0,
    BOOKED: by.BOOKED || 0,
    clients: totals.clients || 0,
    proposals: totals.proposals || 0,
    opportunities: totals.opportunities || 0,
    tasks_open: (status.open_tasks || []).length,
  };
  const stats = $("#stats");
  stats.innerHTML = "";
  for (const def of STAT_DEFS) {
    stats.appendChild(el("div", { class: `stat${def.hot ? " hot" : ""}` }, [
      el("div", { class: "n", text: String(values[def.key] ?? 0) }),
      el("div", { class: "l", text: def.label }),
    ]));
  }

  const pills = $("#pipeline");
  pills.innerHTML = "";
  for (const stage of state.pipeline || []) {
    const count = by[stage] || 0;
    const pill = el("button", {
      class: `stage-pill${count ? "" : " zero"}`,
      title: `Show ${stage} leads`,
      onclick: () => runTool("leads_list", { status: stage, limit: 25 }, `Leads: ${stage}`),
    }, [document.createTextNode(stage.toLowerCase()), el("b", { text: String(count) })]);
    pills.appendChild(pill);
  }

  const top = $("#top-leads");
  top.innerHTML = "";
  const leads = status.top_leads || [];
  if (leads.length) {
    const box = el("div", { class: "leads-list" }, [el("h3", { text: "Top scored" })]);
    for (const lead of leads.slice(0, 6)) {
      box.appendChild(el("div", { class: "lead-row" }, [
        el("span", { class: "nm", text: lead.business, title: lead.business }),
        el("span", { class: "sc", text: `${Math.round(lead.score || 0)}` }),
        el("span", { class: "st", text: (lead.status || "").toLowerCase() }),
      ]));
    }
    top.appendChild(box);
  }

  renderActions(state.tools || []);
}

/* ------------------------------------------------------------------ *
 * One-click actions
 * ------------------------------------------------------------------ */

const ICONS = {
  factory_status: "📊", factory_report: "📄", factory_init: "🏗️", pipeline_run: "▶️",
  seed_demo: "🌱", reset_factory: "🧹", leads_list: "📇", lead_add: "➕", lead_import: "📥",
  lead_status: "🔀", mark_replied: "💬", outreach_draft: "✉️", code_list: "🗂️", code_read: "📖",
  code_write: "💾", code_patch: "🩹", code_search: "🔍", run_script: "🚀", repo_check: "🧪",
  build_agent: "🛠️", git_status: "🌿", git_diff: "🔬", git_log: "🕐", git_commit: "✅",
};

const GROUP_ORDER = ["factory", "leads", "code", "git"];
const GROUP_LABEL = { factory: "Factory", leads: "Leads", code: "Build & code", git: "Git" };
const QUICK = new Set([
  "factory_status", "pipeline_run", "factory_report", "seed_demo", "leads_list", "lead_add",
  "lead_import", "outreach_draft", "mark_replied", "build_agent", "code_read", "run_script",
  "code_search", "repo_check", "git_status", "git_commit", "reset_factory", "factory_init",
]);

function renderActions(tools) {
  const wrap = $("#actions");
  wrap.innerHTML = "";
  for (const group of GROUP_ORDER) {
    const groupTools = tools.filter((tool) => tool.group === group && QUICK.has(tool.name));
    if (!groupTools.length) continue;
    const row = el("div", { class: "action-row" });
    for (const tool of groupTools) {
      const needsArgs = Object.keys(tool.params || {}).length > 0;
      const button = el("button", {
        class: `abtn${tool.confirm ? " danger" : ""}`,
        title: tool.description,
        onclick: () => onActionClick(tool, button),
      }, [el("span", { class: "ico", text: ICONS[tool.name] || "⚙️" }),
          el("span", { text: needsArgs ? `${tool.label}…` : tool.label })]);
      row.appendChild(button);
    }
    wrap.appendChild(el("div", { class: "action-group" }, [
      el("h3", { text: GROUP_LABEL[group] }), row,
    ]));
  }
}

function onActionClick(tool, button) {
  const hasParams = Object.keys(tool.params || {}).length > 0;
  if (tool.confirm && !hasParams) {
    if (!window.confirm(`${tool.label}\n\n${tool.description}`)) return;
    runToolFromButton(tool.name, {}, button, tool.label);
    return;
  }
  if (hasParams) { openModal(tool, button); return; }
  runToolFromButton(tool.name, {}, button, tool.label);
}

async function runToolFromButton(name, args, button, label) {
  if (button) button.classList.add("busy");
  const typing = addTyping();
  try {
    const data = await api("/api/tool", { method: "POST", body: { tool: name, args } });
    typing.remove();
    const result = data.result || {};
    const body = result.ok
      ? formatToolResult(name, result)
      : `⚠️ ${result.error || "that failed"}`;
    addMessage("agent", renderMarkdown(body), [{ tool: name, args, result, ok: Boolean(result.ok) }]);
    renderState(data.state);
    pushLog([{ tool: name, args, ok: Boolean(result.ok), result }]);
    if (result.ok) toast(`${label || name} done`);
  } catch (error) {
    typing.remove();
    toast(`Failed: ${error.message}`, true);
  } finally {
    if (button) button.classList.remove("busy");
  }
}

function formatToolResult(name, result) {
  if (result.report) return result.report;
  const copy = { ...result };
  delete copy.ok;
  if (name === "code_read" && copy.content) {
    const body = copy.content.length > 4000 ? `${copy.content.slice(0, 4000)}\n… truncated` : copy.content;
    return `**${copy.path}** (${copy.lines} lines)\n\n\`\`\`python\n${body}\n\`\`\``;
  }
  if (name === "run_script") {
    const flag = copy.exit_code === 0 ? "✅" : "❌";
    const body = (copy.output || "(no output)").slice(-4000);
    return `${flag} \`${copy.script}\` exited **${copy.exit_code}**\n\n\`\`\`\n${body}\n\`\`\``;
  }
  return "```json\n" + JSON.stringify(copy, null, 2).slice(0, 6000) + "\n```";
}

async function runTool(name, args, label) {
  const typing = addTyping();
  try {
    const data = await api("/api/tool", { method: "POST", body: { tool: name, args } });
    typing.remove();
    addMessage("agent", renderMarkdown(formatToolResult(name, data.result || {})),
      [{ tool: name, args, result: data.result, ok: Boolean(data.result?.ok) }]);
    renderState(data.state);
  } catch (error) {
    typing.remove();
    toast(`Failed: ${error.message}`, true);
  }
}

/* ------------------------------------------------------------------ *
 * Argument modal
 * ------------------------------------------------------------------ */

let modalTarget = null;

function openModal(tool, button) {
  modalTarget = { tool, button };
  $("#modal-title").textContent = tool.label;
  $("#modal-desc").textContent = tool.description;
  const form = $("#modal-form");
  form.innerHTML = "";
  for (const [name, description] of Object.entries(tool.params)) {
    const [kind] = String(description).split(":");
    const required = /required/i.test(description);
    form.appendChild(el("label", { for: `f-${name}`, text: `${name}${required ? " *" : ""}` }));
    const wide = /csv|content|message|reply|notes/i.test(name);
    const field = wide
      ? el("textarea", { id: `f-${name}`, name, rows: "6", placeholder: String(description) })
      : el("input", { id: `f-${name}`, name, placeholder: String(description) });
    if (kind.trim().toLowerCase() === "boolean") {
      field.value = tool.confirm ? "true" : "";
    }
    form.appendChild(field);
  }
  $("#modal-wrap").hidden = false;
  const first = form.querySelector("input, textarea");
  if (first) first.focus();
}

function closeModal() {
  $("#modal-wrap").hidden = true;
  modalTarget = null;
}

function submitModal() {
  if (!modalTarget) return;
  const { tool, button } = modalTarget;
  const args = {};
  for (const [name, description] of Object.entries(tool.params)) {
    const field = document.getElementById(`f-${name}`);
    let value = field ? field.value.trim() : "";
    if (!value) continue;
    const kind = String(description).split(":")[0].trim().toLowerCase();
    if (kind === "boolean") value = /^(true|1|yes|on)$/i.test(value);
    else if (kind === "integer" || kind === "number") value = Number(value);
    args[name] = value;
  }
  const missing = Object.keys(tool.params).filter(
    (name) => /required/i.test(tool.params[name]) && !(name in args)
  );
  if (missing.length) { toast(`Missing: ${missing.join(", ")}`, true); return; }
  closeModal();
  runToolFromButton(tool.name, args, button, tool.label);
}

/* ------------------------------------------------------------------ *
 * Activity log
 * ------------------------------------------------------------------ */

function pushLog(actions) {
  const list = $("#log");
  for (const action of actions || []) {
    const stamp = new Date().toLocaleTimeString();
    list.insertBefore(el("li", { html:
      `<span class="${action.ok ? "ok" : "err"}">${action.ok ? "OK" : "ERR"}</span> ` +
      `<span class="tl">${escapeHtml(stamp)}</span> ${escapeHtml(action.tool)}` }), list.firstChild);
  }
  while (list.children.length > 60) list.removeChild(list.lastChild);
}

/* ------------------------------------------------------------------ *
 * Wiring
 * ------------------------------------------------------------------ */

function autosize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 170)}px`;
}

$("#composer").addEventListener("submit", (event) => { event.preventDefault(); send(); });
input.addEventListener("input", autosize);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); }
});

const chips = $("#chips");
for (const suggestion of SUGGESTIONS) {
  chips.appendChild(el("button", {
    class: "chip", type: "button", text: suggestion.length > 34 ? `${suggestion.slice(0, 32)}…` : suggestion,
    title: suggestion, onclick: () => send(suggestion),
  }));
}

$("#refresh").addEventListener("click", refresh);
$("#clear-chat").addEventListener("click", () => {
  messages.innerHTML = "";
  greet();
});
$("#clear-log").addEventListener("click", () => { $("#log").innerHTML = ""; });
$("#modal-cancel").addEventListener("click", closeModal);
$("#modal-run").addEventListener("click", submitModal);
$("#modal-wrap").addEventListener("click", (event) => {
  if (event.target.id === "modal-wrap") closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
  if (event.key === "Enter" && !$("#modal-wrap").hidden && event.target.tagName !== "TEXTAREA") submitModal();
});

function greet() {
  addMessage("agent", renderMarkdown(
    "**Aloha 🤙** I'm your Hoolulu factory agent — I can run the whole pipeline, work your leads, " +
    "and write code in this repo.\n\n" +
    "Click a button on the right, tap a suggestion below, or just type. " +
    "Start with `status` to see where the factory stands."
  ));
}

async function refresh() {
  try {
    // /api/state returns the snapshot itself; /api/chat wraps it in .state
    renderState(await api("/api/state"));
  } catch (error) {
    toast(`Could not load state: ${error.message}`, true);
  }
}

(async function boot() {
  greet();
  try {
    const data = await api("/api/state");
    renderState(data);
  } catch (error) {
    addMessage("agent", renderMarkdown(
      `⚠️ Could not load factory state: \`${error.message}\`\n\n` +
      "Start the server with `./start.sh`."));
  }
  input.focus();
})();
