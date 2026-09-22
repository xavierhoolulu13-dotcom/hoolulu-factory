#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Hoolulu Ecosystem Hub — structure initializer.
#
#   ./ops/scaffold.sh            create anything that is missing, touch nothing else
#   ./ops/scaffold.sh --force    overwrite placeholder files with fresh stubs
#   ./ops/scaffold.sh --check    exit 1 if the tree is incomplete (used by doctor)
#
# Idempotent: existing files are never clobbered unless --force is passed.
# Roots at the hub directory (the parent of ops/), so it can be run from anywhere.
# ---------------------------------------------------------------------------
set -euo pipefail

HUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=0
CHECK=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --check) CHECK=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

MISSING=0

# dir <path> [purpose...]
dir() {
  local path="$1"; shift
  local full="$HUB_ROOT/$path"
  if [[ ! -d "$full" ]]; then
    if [[ "$CHECK" == "1" ]]; then
      echo "missing dir: $path"; MISSING=$((MISSING + 1)); return
    fi
    mkdir -p "$full"
  fi
  [[ -n "${1:-}" ]] && note "$path/.gitkeep" "keeps $*"
}

# note <relpath> <one-line purpose> -- writes a placeholder only if absent
note() {
  local path="$1"; shift
  local full="$HUB_ROOT/$path"
  if [[ -f "$full" && "$FORCE" == "0" ]]; then return; fi
  if [[ "$CHECK" == "1" ]]; then
    [[ -s "$full" ]] || { echo "missing file: $path"; MISSING=$((MISSING + 1)); }
    return
  fi
  printf '# %s\n\n%s\n' "$(basename "$path")" "$*" > "$full"
}

# ---------------------------------------------------------------------------
# root
# ---------------------------------------------------------------------------
dir ""                       "the hub itself"
dir "core/contracts"         "typed JSON schemas every subsystem signs"
dir "core/approvals"         "human-gate policy and approval ledger"
dir "core/event-log/loops"   "append-only loop events (runtime data)"

dir "market-intel/firecrawl/adapter"    "Firecrawl scrape/extract adapter (optional, network)"
dir "market-intel/search/searxng"       "SearXNG self-hosted search adapter (optional, network)"
dir "market-intel/browser/adapter"      "Playwright/browser-use adapter (optional)"
dir "market-intel/browser/browser-agent" "browser-agent session scripts"
dir "market-intel/monitoring/changedetection" "changedetection.io watch definitions"
dir "market-intel/archive/archivebox"   "ArchiveBox archival config"

dir "commercial-reasoning/evidence/schemas" "evidence record schemas per claim type"
dir "commercial-reasoning/reggie"           "Reggie: regulatory / compliance reasoning"
dir "commercial-reasoning/productizer"      "idea -> sellable product spec"
dir "commercial-reasoning/gap-engine"       "competitor gap + differentiation scoring"

dir "factory/agent-factory"                   "boots the YAML-defined workforce"
dir "factory/adapters/openhands"              "OpenHands coding agent adapter (optional)"
dir "factory/adapters/zerobuild"              "ZeroBuild scaffold adapter (optional)"
dir "factory/adapters/browser-agent"          "browser-agent adapter (optional)"
dir "factory/adapters/firecrawl"              "firecrawl adapter (optional)"
dir "factory/execution/sandbox"               "isolated execution of generated code"
dir "factory/execution/qa"                    "compile, smoke test and score gates"
dir "factory/templates"                       "product templates the builder instantiates"

dir "packaging/product-factory"               "turns a spec into a packaged product"
dir "packaging/deliverables"                  "zip/manifest/checksum output"
dir "packaging/qr-pipelines"                  "QR-driven intake pipelines"
dir "packaging/onboarding"                    "customer onboarding kits"
dir "packaging/monetization/stripe"           "Stripe price + checkout config"
dir "packaging/monetization/paypal"           "PayPal button + subscription config"
dir "packaging/monetization/cashapp"          "Cash App payout config"

dir "delivery/crm"            "contact + account records"
dir "delivery/fulfillment"    "what gets delivered, to whom, when"
dir "delivery/automations"    "post-delivery automation recipes"
dir "delivery/handoff"        "human handoff packets"

dir "revenue/receipts"        "immutable receipt records"
dir "revenue/analytics"       "MRR / conversion / cohort views"
dir "revenue/reconciliation"  "payout vs ledger reconciliation"

dir "offline/provider"        "llama.cpp OpenAI-compatible client"
dir "offline/runtime"         "model download, serve and health management"
dir "offline/models"          "model catalogue and quantization notes"
dir "offline/bridge"          "switches between offline model and deterministic fallback"

dir "mobile/termux"           "Termux bootstrap and launch scripts"
dir "mobile/acode"            "Acode editor project files"
dir "mobile/qr-launcher"      "QR intake launcher"

dir "procurement/sources"            "one file per evaluated third-party component"
dir "procurement/licenses"           "license text and obligations per component"
dir "procurement/compatibility"      "runtime + platform compatibility matrix"
dir "procurement/security"           "threat notes and review status"
dir "procurement/integration-status" "live status of each adapter"

dir "ops"                     "start / stop / status / backup / doctor"

# ---------------------------------------------------------------------------
# root files
# ---------------------------------------------------------------------------
note "README.md"        "Hub overview: map of every directory and how they connect."
note ".env.example"     "Every environment variable the hub understands, with defaults."
note "docker-compose.yml" "Optional container profile for the network adapters (SearXNG, Firecrawl, changedetection)."

# core
note "core/hub.md"        "The hub contract: how a request travels from intake to delivery."
note "core/constitution.md" "Non-negotiable rules: offline-first, human-gated, evidence-backed."
note "core/identity.md"   "Who the hub is, how it speaks, what it refuses to do."

for schema in research evidence product build delivery revenue loop; do
  note "core/contracts/${schema}.schema.json" \
    "JSON Schema for the ${schema} contract. Fields are typed so downstream stages can never silently lose data."
done

note "core/approvals/approval-policy.md" \
  "Which actions are gated, who can approve, and what counts as trace evidence."
note "core/event-log/loop-schema.json" \
  "Schema for one loop event: what ran, what it concluded, what it recommends next."

# procurement
note "procurement/manifest.json" \
  "Machine-readable list of every third-party component, its license and its integration status."
for source in openhands zerobuild browser-agent firecrawl searxng changedetection archivebox; do
  note "procurement/sources/${source}.json" \
    "${source}: upstream URL, license, required env vars, offline-capable flag and integration status."
done

if [[ "$CHECK" == "1" ]]; then
  if [[ "$MISSING" -gt 0 ]]; then
    echo "scaffold: $MISSING missing entr(ies)"
    exit 1
  fi
  echo "scaffold: complete"
  exit 0
fi

echo "Hoolulu Ecosystem Hub structure initialized successfully."
echo "  root: $HUB_ROOT"
