from __future__ import annotations

import json
import os
import re
from collections import defaultdict, deque
from typing import Any

import httpx

NODE_TYPE_TEMPLATES: dict[str, str] = {
    "n8n-nodes-base.httpRequest": """
# HTTP Request: {node_name}
async with httpx.AsyncClient() as client:
    response = await client.{method}(
        "{url}",
        headers={headers},
        json={body},
        timeout=30.0,
    )
    {var_name} = response.json()
""",
    "n8n-nodes-base.code": """
# Code Execution: {node_name}
# Original JavaScript converted to Python
{python_code}
""",
    "n8n-nodes-base.postgres": """
# Database: {node_name}
db = next(get_db())
result = db.execute(
    text({query}),
    {params}
)
db.commit()
{var_name} = result
""",
    "n8n-nodes-base.sendEmail": """
# Send Email: {node_name}
email_service = EmailService()
await email_service.send_email(
    to={to_email},
    subject={subject},
    html_content={body}
)
{var_name} = {{"status": "queued"}}
""",
    "n8n-nodes-base.if": """
# Conditional: {node_name}
if {condition}:
    {var_name} = {{"branch": "true"}}
else:
    {var_name} = {{"branch": "false"}}
""",
}


class N8NWorkflowParser:
    """Parse and convert n8n workflow JSON into Summit Python agents."""

    def __init__(self) -> None:
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.credential_map = {
            "apolloApi": {
                "env_var": "APOLLO_API_KEY",
                "name": "Apollo.io API",
                "get_url": "https://apollo.io/settings/integrations/api",
            },
            "sendGridApi": {
                "env_var": "SENDGRID_API_KEY",
                "name": "SendGrid API",
                "get_url": "https://sendgrid.com/settings/api_keys",
            },
            "openAiApi": {
                "env_var": "OPENAI_API_KEY",
                "name": "OpenAI API",
                "get_url": "https://platform.openai.com/api-keys",
            },
            "anthropicApi": {
                "env_var": "ANTHROPIC_API_KEY",
                "name": "Anthropic API",
                "get_url": "https://console.anthropic.com/settings/keys",
            },
            "httpHeaderAuth": {
                "env_var": "CUSTOM_API_KEY",
                "name": "Custom API Key",
                "get_url": None,
            },
            "goHighLevelApi": {
                "env_var": "GOHIGHLEVEL_API_KEY",
                "name": "GoHighLevel API",
                "get_url": "https://marketplace.gohighlevel.com/oauth",
            },
            "twilioApi": {
                "env_var": "TWILIO_ACCOUNT_SID",
                "name": "Twilio API",
                "get_url": "https://console.twilio.com/",
            },
        }

    async def parse_workflow(self, n8n_json: dict[str, Any]) -> dict[str, Any]:
        workflow_name = n8n_json.get("name", "Imported Workflow")
        nodes = n8n_json.get("nodes", []) or []
        connections = n8n_json.get("connections", {}) or {}

        required_apis = self._detect_required_apis(nodes)
        execution_order = self._build_execution_order(nodes, connections)
        node_logic = [logic for node in nodes if (logic := self._extract_node_logic(node))]

        return {
            "workflow_name": workflow_name,
            "required_apis": required_apis,
            "execution_order": execution_order,
            "node_logic": node_logic,
            "original_json": n8n_json,
        }

    def _detect_required_apis(self, nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
        required_apis: list[dict[str, str]] = []
        seen: set[str] = set()
        for node in nodes:
            params = node.get("parameters", {}) or {}
            cred_type = params.get("nodeCredentialType") or params.get("authentication")
            if cred_type in self.credential_map and cred_type not in seen:
                required_apis.append(self.credential_map[cred_type])
                seen.add(cred_type)

            url = str(params.get("url", "")).lower()
            if "apollo.io" in url and "apolloApi" not in seen:
                required_apis.append(self.credential_map["apolloApi"])
                seen.add("apolloApi")
            if "sendgrid.com" in url and "sendGridApi" not in seen:
                required_apis.append(self.credential_map["sendGridApi"])
                seen.add("sendGridApi")
            if "api.openai.com" in url and "openAiApi" not in seen:
                required_apis.append(self.credential_map["openAiApi"])
                seen.add("openAiApi")
            if "gohighlevel.com" in url and "goHighLevelApi" not in seen:
                required_apis.append(self.credential_map["goHighLevelApi"])
                seen.add("goHighLevelApi")
        return required_apis

    def _build_execution_order(
        self,
        nodes: list[dict[str, Any]],
        connections: dict[str, Any],
    ) -> list[str]:
        names = [str(node.get("name", "")).strip() for node in nodes if node.get("name")]
        if not names:
            return []

        graph: dict[str, list[str]] = {name: [] for name in names}
        indegree: dict[str, int] = {name: 0 for name in names}

        for source, targets in connections.items():
            for lane in (targets or {}).get("main", []):
                for target in lane or []:
                    dest = target.get("node")
                    if source in graph and dest in graph:
                        graph[source].append(dest)
                        indegree[dest] += 1

        queue = deque([name for name in names if indegree[name] == 0])
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for nxt in graph[node]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        # If cycle exists, append remaining nodes in input order.
        if len(order) != len(names):
            seen = set(order)
            order.extend([n for n in names if n not in seen])
        return order

    def _extract_node_logic(self, node: dict[str, Any]) -> dict[str, Any]:
        node_type = node.get("type", "")
        node_name = node.get("name", "")
        params = node.get("parameters", {}) or {}
        logic: dict[str, Any] = {"name": node_name, "type": node_type, "params": params}

        if "httpRequest" in node_type:
            logic.update(
                {
                    "action": "http_request",
                    "url": params.get("url", ""),
                    "method": str(params.get("method", "GET")).upper(),
                    "headers": params.get("headerParameters", {}),
                    "body": params.get("bodyParameters", {}),
                }
            )
        elif "code" in node_type:
            logic.update(
                {
                    "action": "code_execution",
                    "language": params.get("language", "javascript"),
                    "code": params.get("jsCode") or params.get("pythonCode", ""),
                }
            )
        elif "postgres" in node_type or "mysql" in node_type:
            logic.update(
                {
                    "action": "database",
                    "operation": params.get("operation", ""),
                    "table": params.get("table", ""),
                    "query": params.get("query", ""),
                }
            )
        elif "sendEmail" in node_type or "emailSend" in node_type:
            logic.update(
                {
                    "action": "send_email",
                    "to": params.get("toEmail", ""),
                    "subject": params.get("subject", ""),
                    "body": params.get("text", ""),
                }
            )
        elif "if" in node_type.lower():
            logic.update({"action": "conditional", "conditions": params.get("conditions", {})})
        else:
            logic.update({"action": "generic", "details": params})

        return logic

    async def convert_to_python_agent(
        self,
        parsed_workflow: dict[str, Any],
        user_api_keys: dict[str, str] | None = None,
    ) -> str:
        user_api_keys = user_api_keys or {}
        prompt = self._build_conversion_prompt(parsed_workflow, user_api_keys)

        if not self.anthropic_key:
            return self._fallback_generate(parsed_workflow)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "X-API-Key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 8000,
                        "temperature": 0.2,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                response.raise_for_status()
                code = response.json()["content"][0]["text"]
                if "```python" in code:
                    code = code.split("```python", 1)[1].split("```", 1)[0].strip()
                return code.strip()
        except Exception:
            return self._fallback_generate(parsed_workflow)

    def _build_conversion_prompt(
        self,
        parsed_workflow: dict[str, Any],
        user_api_keys: dict[str, str],
    ) -> str:
        workflow_name = parsed_workflow.get("workflow_name", "Imported Workflow")
        execution_order = parsed_workflow.get("execution_order", [])
        node_logic = parsed_workflow.get("node_logic", [])
        return f"""
Convert this n8n workflow to production-ready async Python code.

Workflow name: {workflow_name}
Execution order:
{chr(10).join(f"{i+1}. {n}" for i, n in enumerate(execution_order))}

Node logic JSON:
{json.dumps(node_logic, indent=2)}

Requirements:
- async def execute(config: dict)
- use httpx for HTTP
- use sqlalchemy text() with get_db for DB writes
- include error handling, logging, and cost_usd in returned payload
- preserve business logic and data transformations
- convert JavaScript code nodes to Python
- do not output explanation; output code only

Configured env keys:
{chr(10).join(sorted(user_api_keys.keys()))}

Template imports:
import os
import httpx
import logging
from sqlalchemy import text
from app.database import get_db
logger = logging.getLogger(__name__)
"""

    def _fallback_generate(self, parsed_workflow: dict[str, Any]) -> str:
        workflow_name = parsed_workflow.get("workflow_name", "Imported Workflow")
        ordered = parsed_workflow.get("execution_order", [])
        node_logic = parsed_workflow.get("node_logic", [])
        by_name = {n["name"]: n for n in node_logic if n.get("name")}
        lines: list[str] = [
            "import os",
            "import logging",
            "import httpx",
            "from sqlalchemy import text",
            "from app.database import get_db",
            "",
            "logger = logging.getLogger(__name__)",
            "",
            f"# Auto-generated fallback converter for: {workflow_name}",
            "async def execute(config: dict):",
            "    cost_usd = 0.0",
            "    context = {}",
            "    try:",
        ]
        for idx, name in enumerate(ordered, start=1):
            node = by_name.get(name, {})
            action = node.get("action")
            params = node.get("params", {})
            var_name = self._safe_var(name)
            lines.append(f"        # Step {idx}: {name}")
            if action == "http_request":
                method = str(node.get("method", "GET")).lower()
                url = node.get("url", "")
                headers = self._normalize_header_params(params.get("headerParameters", {}))
                body = self._normalize_body_params(params.get("bodyParameters", {}))
                template = NODE_TYPE_TEMPLATES["n8n-nodes-base.httpRequest"].format(
                    node_name=name,
                    method=method if method in {"get", "post", "put", "patch", "delete"} else "get",
                    url=url,
                    headers=headers,
                    body=body,
                    var_name=var_name,
                )
                lines.extend([f"        {ln}" if ln else "" for ln in template.strip("\n").split("\n")])
                lines.append(f"        context[{name!r}] = {var_name}")
                lines.append("        cost_usd += 0.002")
            elif action == "database":
                query = node.get("query") or self._build_simple_sql(node)
                template = NODE_TYPE_TEMPLATES["n8n-nodes-base.postgres"].format(
                    node_name=name,
                    query=repr(query),
                    params="{}",
                    var_name=var_name,
                )
                lines.extend([f"        {ln}" if ln else "" for ln in template.strip("\n").split("\n")])
                lines.append("        cost_usd += 0.0005")
            elif action == "code_execution":
                code = self._convert_js_to_python(str(node.get("code", "")))
                template = NODE_TYPE_TEMPLATES["n8n-nodes-base.code"].format(
                    node_name=name,
                    python_code=code or "pass",
                )
                lines.extend([f"        {ln}" if ln else "" for ln in template.strip("\n").split("\n")])
                lines.append("        cost_usd += 0.0005")
            else:
                lines.append(f"        logger.info('Unhandled node type for {name}; stored raw params')")
                lines.append(f"        context[{name!r}] = {params!r}")

        lines.extend(
            [
                "        return {",
                "            'success': True,",
                "            'workflow_name': " + repr(workflow_name) + ",",
                "            'steps_executed': " + str(len(ordered)) + ",",
                "            'results': context,",
                "            'cost_usd': round(cost_usd, 4),",
                "        }",
                "    except Exception as exc:",
                "        logger.error('Imported n8n workflow failed: %s', exc)",
                "        return {'success': False, 'error': str(exc), 'cost_usd': round(cost_usd, 4)}",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _safe_var(name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip()).lower().strip("_")
        return cleaned or "node_result"

    @staticmethod
    def _normalize_body_params(body: dict[str, Any]) -> dict[str, Any]:
        params = body.get("parameters", []) if isinstance(body, dict) else []
        output: dict[str, Any] = {}
        for p in params:
            key = p.get("name")
            if key:
                output[key] = p.get("value")
        return output

    @staticmethod
    def _normalize_header_params(headers: dict[str, Any]) -> dict[str, Any]:
        params = headers.get("parameters", []) if isinstance(headers, dict) else []
        output: dict[str, Any] = {}
        for p in params:
            key = p.get("name")
            if not key:
                continue
            value = p.get("value")
            if isinstance(value, str) and "$credentials" in value:
                output[key] = os.getenv("CUSTOM_API_KEY", "")
            else:
                output[key] = value
        return output

    @staticmethod
    def _convert_js_to_python(js_code: str) -> str:
        if not js_code.strip():
            return "pass"
        lines: list[str] = [
            "# NOTE: This is an automated best-effort JS->Python conversion.",
            "# Review before production use.",
        ]
        if "items[0].json.people" in js_code:
            lines.extend(
                [
                    "people = context.get('HTTP Request', {}).get('people', [])",
                    "converted = []",
                    "for lead in people:",
                    "    converted.append({",
                    "        'name': lead.get('name'),",
                    "        'email': lead.get('email'),",
                    "        'company': (lead.get('organization') or {}).get('name'),",
                    "    })",
                    "context['code_result'] = converted",
                ]
            )
        else:
            cleaned = js_code.replace("const ", "").replace("let ", "")
            lines.append(f"logger.info('Original JS code: {cleaned[:240]!r}')")
            lines.append("context['code_result'] = context")
        return "\n".join(lines)

    @staticmethod
    def _build_simple_sql(node: dict[str, Any]) -> str:
        table = node.get("table") or "prospects"
        operation = node.get("operation", "").lower()
        if operation == "insert":
            return f"INSERT INTO {table} DEFAULT VALUES"
        if operation == "update":
            return f"UPDATE {table} SET updated_at = NOW()"
        return node.get("query") or "SELECT 1"


n8n_parser = N8NWorkflowParser()

