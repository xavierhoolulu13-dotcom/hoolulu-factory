"""Export the Hoolulu Agent so other platforms can drive it.

Two artefacts, both written to ``generated/``:

``openapi.json``
    An OpenAPI 3.0 description of every agent tool, served by this repo's
    ``/api/tool`` endpoint. This is the file you point Dify's "Custom Tool",
    ChatGPT's Actions, or any MCP/function-calling host at. Verified against
    the live tool registry every time it is generated.

``dify-hoolulu-agent.yml``
    A Dify DSL (``kind: app``, ``mode: agent-chat``) that imports as an agent
    app carrying the same system prompt. Note: Dify's DSL schema moves between
    releases — treat this as a starting point and re-check it against the
    version you run. The OpenAPI file above is the stable contract.

Run it with::

    python -m agent.dify_export
"""

import json
import os
from datetime import datetime, timezone

from . import __version__, config
from .brain import SYSTEM_PROMPT
from .tools import public_specs

OUT_DIR = os.path.join(config.REPO_ROOT, "generated")

# Wherever this agent ends up being hosted. Override with HOOLULU_PUBLIC_URL.
PUBLIC_URL = os.environ.get("HOOLULU_PUBLIC_URL", "http://127.0.0.1:8000")


def _json_schema(description):
    """'string: required business name' -> (schema, required?)"""
    kind, _, detail = (description or "").partition(":")
    kind, detail = kind.strip().lower(), detail.strip()
    required = detail.lower().startswith("required")
    detail = detail[8:].strip() if required else detail
    mapping = {"string": "string", "integer": "integer", "number": "number",
               "boolean": "boolean", "int": "integer", "bool": "boolean"}
    return {"type": mapping.get(kind, "string"), "description": detail or description or ""}, required


def build_openapi(base_url=None):
    """OpenAPI 3.0 document exposing every agent tool as one POST route."""
    base_url = (base_url or PUBLIC_URL).rstrip("/")

    paths = {
        "/api/health": {
            "get": {
                "operationId": "hooluluHealth",
                "summary": "Check the agent is alive",
                "responses": {"200": {"description": "Agent is running"}},
            }
        },
        "/api/state": {
            "get": {
                "operationId": "hooluluState",
                "summary": "Live factory state: pipeline counts, leads, open tasks",
                "responses": {"200": {"description": "Factory snapshot"}},
            }
        },
        "/api/chat": {
            "post": {
                "operationId": "hooluluChat",
                "summary": "Send a natural-language instruction to the agent",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string",
                                                   "description": "What the agent should do"}},
                        "required": ["message"],
                    }}},
                },
                "responses": {"200": {"description": "Agent reply plus the tools it called"}},
            }
        },
    }

    for spec in public_specs():
        properties, required = {}, []
        for name, description in spec["params"].items():
            prop, is_required = _json_schema(description)
            properties[name] = prop
            if is_required:
                required.append(name)
        paths[f"/api/tool/{spec['name']}"] = {
            "post": {
                "operationId": f"hoolulu_{spec['name']}",
                "summary": spec["label"],
                "description": spec["description"],
                "tags": [spec["group"]],
                "requestBody": {
                    "required": bool(required),
                    "content": {"application/json": {"schema": {
                        "type": "object", "properties": properties, "required": required,
                    }}},
                },
                "responses": {"200": {"description": "Tool result"}},
            }
        }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Hoolulu Factory Agent",
            "version": __version__,
            "description": (
                "Control the Hoolulu lead-generation factory: run pipeline stages, "
                "work leads, and read/write/run code in the repository. Every tool "
                "is also reachable through POST /api/tool with "
                '{"tool": "<name>", "args": {...}}.'
            ),
        },
        "servers": [{"url": base_url, "description": "Hoolulu Factory Agent"}],
        "paths": paths,
        # The agent itself also accepts the generic form.
        "x-hoolulu-generic-endpoint": {
            "path": "/api/tool",
            "body": {"tool": "string (tool name)", "args": "object (tool arguments)"},
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def build_dify_dsl(base_url=None):
    """Dify agent-chat DSL. Hand-rolled YAML (no PyYAML dependency)."""
    base_url = (base_url or PUBLIC_URL).rstrip("/")
    prompt = SYSTEM_PROMPT.replace("\n", "\n      ")
    tools_yaml = []
    for spec in public_specs():
        tools_yaml.append(
            f"    - provider_name: hoolulu\n"
            f"      provider_id: hoolulu\n"
            f"      provider_type: api\n"
            f"      tool_name: hoolulu_{spec['name']}\n"
            f"      tool_label: {spec['label']}\n"
            f"      tool_parameters: {{}}\n"
            f"      enabled: true"
        )
    tools_block = "\n".join(tools_yaml)

    return f"""# Hoolulu Factory Agent - Dify DSL
# Import: Dify -> Studio -> Create from DSL -> upload this file.
# Then add the OpenAPI custom tool (generated/openapi.json) so the agent can
# actually reach the factory at {base_url}.
#
# NOTE: Dify's DSL schema changes between releases. If this version refuses the
# file, create an empty Agent app in your Dify and paste the prompt below.
app:
  description: Coding and operations agent for the Hoolulu lead-generation factory.
  icon: "\U0001F919"
  icon_background: '#0B1015'
  mode: agent-chat
  name: Hoolulu Factory Agent
  use_icon_as_answer_icon: false
kind: app
version: 0.1.5
model_config:
  agent_mode:
    enabled: true
    max_iteration: 5
    strategy: function_call
    tools:
{tools_block}
  annotation_reply: null
  completion_params:
    max_tokens: 2048
    stop: []
    temperature: 0.2
    top_p: 0.9
  dataset_configs:
    datasets:
      datasets: []
    retrieval_model: single
  external_retrieval_model: null
  file_upload:
    enabled: false
  model:
    completion_params:
      stop: []
    mode: chat
    name: gpt-4o-mini
    provider: openai
  more_like_this:
    enabled: false
  opening_statement: "Aloha \U0001F919 I'm your Hoolulu factory agent. Say `status`,
    `run the pipeline`, or ask me to build something."
  pre_prompt: "
      {prompt}

      The factory API lives at {base_url}. Call tools instead of guessing."
  prompt_type: advanced-chat
  retriever_resource:
    enabled: false
  sensitive_word_avoidance:
    enabled: false
  speech_to_text:
    enabled: false
  suggested_questions:
    - status
    - run the pipeline
    - show leads
    - check the code
    - build me an agent called Review Watcher
  suggested_questions_after_answer:
    enabled: false
  text_to_speech:
    enabled: false
"""


def export(base_url=None, out_dir=None):
    """Write both artefacts and return their paths + a sanity check."""
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    openapi = build_openapi(base_url)
    openapi_path = os.path.join(out_dir, "openapi.json")
    with open(openapi_path, "w") as handle:
        json.dump(openapi, handle, indent=2)

    dsl = build_dify_dsl(base_url)
    dsl_path = os.path.join(out_dir, "dify-hoolulu-agent.yml")
    with open(dsl_path, "w") as handle:
        handle.write(dsl)

    # Sanity check the OpenAPI contract against the live registry.
    missing = [spec["name"] for spec in public_specs()
               if f"/api/tool/{spec['name']}" not in openapi["paths"]]
    return {
        "openapi": openapi_path,
        "dsl": dsl_path,
        "tools_exported": len(public_specs()),
        "paths": len(openapi["paths"]),
        "missing_tools": missing,
        "base_url": (base_url or PUBLIC_URL),
    }


if __name__ == "__main__":
    result = export()
    print("Hoolulu Agent export")
    print(f"  OpenAPI : {result['openapi']} ({result['tools_exported']} tools, {result['paths']} paths)")
    print(f"  Dify DSL: {result['dsl']}")
    print(f"  base url: {result['base_url']}")
    if result["missing_tools"]:
        print(f"  WARNING missing tools: {result['missing_tools']}")
    else:
        print("  every registered tool is exported")
