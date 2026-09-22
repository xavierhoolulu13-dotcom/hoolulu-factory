/* {{NAME}} — {{TAGLINE}}
   One job, offline, no account. State lives in localStorage. */
(function () {
  "use strict";

  var KEY = "{{SLUG}}-entries";
  var form = document.getElementById("entry");
  var whatEl = document.getElementById("what");
  var amountEl = document.getElementById("amount");
  var listEl = document.getElementById("list");
  var emptyEl = document.getElementById("empty");
  var countEl = document.getElementById("count");
  var totalEl = document.getElementById("total");
  var exportBtn = document.getElementById("export");
  var clearBtn = document.getElementById("clear");
  var entries = [];

  function load() {
    try {
      entries = JSON.parse(localStorage.getItem(KEY) || "[]");
    } catch (e) {
      entries = [];
    }
    if (!Array.isArray(entries)) entries = [];
  }

  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(entries));
    } catch (e) {
      /* private browsing: keep it in memory for this session */
    }
  }

  function money(value) {
    return "$" + Number(value || 0).toLocaleString(undefined, {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    });
  }

  function render() {
    listEl.innerHTML = "";
    var total = 0;
    entries.forEach(function (entry, index) {
      total += Number(entry.amount) || 0;
      var li = document.createElement("li");
      li.innerHTML =
        '<span class="what"></span>' +
        '<span class="amt"></span>' +
        '<button class="del" aria-label="remove">&times;</button>';
      li.querySelector(".what").textContent = entry.what;
      li.querySelector(".amt").textContent = money(entry.amount);
      li.querySelector(".del").addEventListener("click", function () {
        entries.splice(index, 1);
        save();
        render();
      });
      listEl.appendChild(li);
    });
    countEl.textContent = String(entries.length);
    totalEl.textContent = money(total);
    emptyEl.hidden = entries.length > 0;
    listEl.hidden = entries.length === 0;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var what = whatEl.value.trim();
    var amount = parseFloat(amountEl.value);
    if (!what || isNaN(amount)) return;
    entries.unshift({ what: what, amount: amount, at: new Date().toISOString() });
    save();
    render();
    whatEl.value = "";
    amountEl.value = "";
    whatEl.focus();
  });

  exportBtn.addEventListener("click", function () {
    if (!entries.length) return;
    var rows = [["what", "amount", "timestamp"]].concat(
      entries.map(function (e) { return [e.what, e.amount, e.at]; })
    );
    var csv = rows.map(function (row) {
      return row.map(function (cell) {
        return '"' + String(cell).replace(/"/g, '""') + '"';
      }).join(",");
    }).join("\n");
    var blob = new Blob([csv], { type: "text/csv" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "{{SLUG}}-export.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  });

  clearBtn.addEventListener("click", function () {
    if (!entries.length) return;
    if (!confirm("Delete all " + entries.length + " entries?")) return;
    entries = [];
    save();
    render();
  });

  load();
  render();
})();
