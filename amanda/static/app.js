/* Amanda — operator console. No framework, no build step. */

const els = {
  messages: document.getElementById("messages"),
  input: document.getElementById("input"),
  form: document.getElementById("composer"),
  send: document.getElementById("send"),
  chips: document.getElementById("chips"),
  clear: document.getElementById("clear-chat"),
  refresh: document.getElementById("refresh"),
  brain: document.getElementById("brain-badge"),
  tier: document.getElementById("tier-badge"),
  deployments: document.getElementById("deployments"),
  approvals: document.getElementById("approvals"),
  factory: document.getElementById("factory"),
  events: document.getElementById("events"),
};

const CHIPS = [
  "build me a snake game and host it",
  "spec a booking page for a surf school",
  "status",
  "maintain",
  "doctor",
  "report",
  "swarm",
];

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

/* links inside a reply become clickable, everything else stays text */
function linkify(text) {
  return escapeHtml(text).replace(
    /(https?:\/\/[^\s<]+)/g,
    (url) => `<a href="${url}" target="_blank" rel="noopener">${url}</a>`
  );
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `<div class="bubble">${linkify(text).replace(/\n/g, "<br>")}</div>`;
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
  return div;
}

function addThinking() {
  return addMessage("bot", "working…");
}

async function send(text) {
  if (!text.trim()) return;
  addMessage("user", text);
  els.input.value = "";
  const thinking = addThinking();
  els.send.disabled = true;
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await response.json();
    thinking.remove();
    addMessage("bot", data.reply || "(no reply)");
    refresh();
  } catch (error) {
    thinking.remove();
    addMessage("bot", `that did not work: ${error}`);
  } finally {
    els.send.disabled = false;
    els.input.focus();
  }
}

async function refresh() {
  try {
    const response = await fetch("/api/state");
    const state = await response.json();
    render(state);
  } catch (error) {
    els.factory.innerHTML = `<div class="row muted">state unavailable: ${error}</div>`;
  }
}

function render(state) {
  els.brain.textContent = state.brain === "offline-model"
    ? `brain: offline model`
    : "brain: deterministic";
  els.brain.className = `badge ${state.brain === "offline-model" ? "ok" : "warn"}`;
  els.brain.title = state.brain_detail && state.brain_detail.ok
    ? `${state.brain_detail.url} — ${(state.brain_detail.models || []).join(", ")}`
    : "no local model reachable; deterministic reasoning in use";
  els.tier.textContent = `tier: ${state.tier}`;

  // deployments
  const deployments = state.deployments || [];
  els.deployments.innerHTML = deployments.length
    ? deployments.map((d) => `
        <div class="row">
          <a href="${d.url}" target="_blank" rel="noopener">${escapeHtml(d.slug)}</a>
          <span class="tag">${escapeHtml(d.status || "?")}</span>
          <span class="tag ghost">${escapeHtml(d.tier || "?")}</span>
          ${d.qa_score !== null && d.qa_score !== undefined ? `<span class="tag ok">qa ${d.qa_score}</span>` : ""}
        </div>`).join("")
    : `<div class="row muted">nothing deployed yet</div>`;

  // approvals
  const approvals = state.approvals || [];
  els.approvals.innerHTML = approvals.length
    ? approvals.map((a) => `
        <div class="row wrap">
          <code>${escapeHtml(a.id)}</code>
          <span>${escapeHtml(a.action)}</span>
          <span class="tag warn">${escapeHtml(a.slug || "-")}</span>
        </div>
        <div class="row muted small">approve: python -m amanda gate approve ${escapeHtml(a.id)} --evidence &lt;path&gt;</div>
      `).join("")
    : `<div class="row muted">nothing waiting</div>`;

  // factory facts
  const builds = state.builds || [];
  const skills = state.skills || [];
  els.factory.innerHTML = `
    <div class="row"><span class="muted">builds</span><span>${builds.length ? escapeHtml(builds.join(", ")) : "none"}</span></div>
    <div class="row"><span class="muted">skills</span><span>${skills.length}</span></div>
    <div class="row"><span class="muted">model</span><span class="small">${escapeHtml(state.runtime && state.runtime.url)}</span></div>
    ${state.runtime && state.runtime.models_found && state.runtime.models_found.length
      ? `<div class="row"><span class="muted">gguf</span><span class="small">${escapeHtml(state.runtime.models_found[0].split("/").pop())}</span></div>`
      : ""}
  `;

  return fetch("/api/events?limit=8")
    .then((r) => r.json())
    .then((events) => {
      els.events.innerHTML = events.length
        ? events.map((e) => `
            <div class="row small">
              <span class="${e.status === "ok" ? "ok" : e.status === "blocked" ? "warn" : "bad"}">
                ${e.status === "ok" ? "✓" : e.status === "blocked" ? "⏸" : "✗"}
              </span>
              <span>${escapeHtml(e.stage)}</span>
              <span class="muted">${escapeHtml(e.message || "")}</span>
            </div>`).join("")
        : `<div class="row muted">no runs yet</div>`;
    });
}

// --- wiring ---------------------------------------------------------------
els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  send(els.input.value);
});

els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    send(els.input.value);
  }
});

els.clear.addEventListener("click", () => { els.messages.innerHTML = ""; });
els.refresh.addEventListener("click", refresh);

CHIPS.forEach((text) => {
  const button = document.createElement("button");
  button.className = "chip";
  button.textContent = text;
  button.addEventListener("click", () => send(text));
  els.chips.appendChild(button);
});

addMessage("bot",
  "Aloha. Tell me what to build and I will research it, scope it, build it, test it, "
  + "package it and put it online — then keep checking it. Try a chip below, or just "
  + "say something like “build me a snake game and host it”.");
refresh();
