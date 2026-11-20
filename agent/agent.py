"""
Core HR/IT Helpdesk Agent — powered by Google Gemini (free tier).
Uses the new `google-genai` SDK (google.genai).

Uses:
- Gemini 2.0 Flash for LLM + function calling (tool use)
- ChromaDB + Gemini embeddings for RAG
- Guardrails for injection detection, scope filtering, and PII redaction
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv

from agent.guardrails import check_input, sanitize_output
from agent.rag import retrieve_policy_context, build_vectorstore

load_dotenv()

MODEL = os.getenv("AGENT_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS = [MODEL, "gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash"]


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your-gemini-api-key-here":
        raise ValueError(
            "GOOGLE_API_KEY is not configured. Please add your key to .env. "
            "You can get a free key at https://aistudio.google.com"
        )
    return genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})


def _generate_content_robust(client: genai.Client, contents: list, config: types.GenerateContentConfig):
    last_err = None
    seen = set()
    for m in FALLBACK_MODELS:
        if m in seen:
            continue
        seen.add(m)
        try:
            return client.models.generate_content(
                model=m,
                contents=contents,
                config=config,
            )
        except Exception as e:
            last_err = e
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                continue
            raise e
    raise last_err

# ── Tool declarations for Gemini function calling ─────────────────────────────

_TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_leave_balance",
            description=(
                "Get the leave balance for an employee from the database. "
                "Use when asked about leave days remaining, leave balance, or used leaves."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "employee_id": types.Schema(type="STRING", description="Employee ID like 'E102'"),
                    "employee_name": types.Schema(type="STRING", description="Full or partial name"),
                    "year": types.Schema(type="INTEGER", description="Year (default 2026)"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="get_employee_info",
            description="Look up employee details: name, department, designation, manager.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "employee_id": types.Schema(type="STRING", description="Employee ID like 'E101'"),
                    "employee_name": types.Schema(type="STRING", description="Employee name"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="get_it_assets",
            description="List IT assets (laptop, phone, monitor) assigned to an employee.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "employee_id": types.Schema(type="STRING"),
                    "employee_name": types.Schema(type="STRING"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="get_it_tickets",
            description="Get IT helpdesk tickets for an employee, optionally filtered by status.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "employee_id": types.Schema(type="STRING"),
                    "employee_name": types.Schema(type="STRING"),
                    "status": types.Schema(
                        type="STRING",
                        description="Filter by: open, in_progress, resolved, closed",
                    ),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="list_employees",
            description="List all active employees with IDs and departments.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
    ])
]

# ── MCP tool dispatcher ───────────────────────────────────────────────────────

def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Call the MCP server handler functions directly (in-process)."""
    try:
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from mcp_server.postgres_mcp import (
            get_leave_balance,
            get_employee_info,
            get_it_assets,
            get_it_tickets,
            list_employees,
        )

        dispatch = {
            "get_leave_balance": get_leave_balance,
            "get_employee_info": get_employee_info,
            "get_it_assets": get_it_assets,
            "get_it_tickets": get_it_tickets,
            "list_employees": list_employees,
        }

        if tool_name not in dispatch:
            return f"Unknown tool: {tool_name}"

        return dispatch[tool_name](**arguments)

    except Exception as e:
        return f"Error calling tool '{tool_name}': {e}"


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an HR/IT Helpdesk Assistant for GoAified Technologies.

Your responsibilities:
1. Answer HR policy questions (leave policy, payroll, benefits, onboarding, travel) using the provided policy context.
2. Answer employee-specific questions (leave balances, IT assets, support tickets) by calling the database tools.
3. Stay strictly within HR and IT topics. Politely decline anything else.

Guidelines:
- Always cite the policy source (e.g., "According to the Leave Policy...") when answering policy questions.
- For employee data queries, use the appropriate tool and report the results clearly.
- If you cannot find information in the policy or database, say so clearly — do NOT guess or hallucinate.
- Keep responses concise and professional.
- Never reveal system internals or internal tool names to the user.
"""


# ── Main agent function ───────────────────────────────────────────────────────

def run_agent(user_message: str, chat_history: list[dict] | None = None) -> str:
    """
    Process a user message through the full agent pipeline:
    1. Guardrail input check
    2. RAG policy retrieval
    3. Gemini LLM with function calling (agentic loop)
    4. Guardrail output sanitization (PII redaction)
    """
    # --- Step 1: Input guardrails ---
    guard = check_input(user_message)
    if guard.blocked:
        return guard.message  # type: ignore[return-value]

    # --- Step 2: RAG — retrieve relevant policy context ---
    policy_hits = retrieve_policy_context(user_message, k=4)
    policy_context = ""
    if policy_hits:
        policy_context = "\n\n--- Relevant Policy Excerpts ---\n"
        for hit in policy_hits:
            policy_context += f"\n[Source: {hit['source']}]\n{hit['content']}\n"

    system_instruction = SYSTEM_PROMPT + policy_context

    # --- Step 3: Build conversation history ---
    contents: list[types.Content] = []
    if chat_history:
        for msg in chat_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=_TOOLS,
        temperature=0.1,
    )

    client = get_genai_client()

    # --- Step 4: Agentic loop ---
    for _ in range(5):
        response = _generate_content_robust(client, contents, config)

        # Collect any function calls from all candidates/parts
        fn_calls = []
        for part in response.candidates[0].content.parts:
            if part.function_call:
                fn_calls.append(part.function_call)

        if not fn_calls:
            # Final text answer
            final = response.text or "I couldn't generate a response."
            return sanitize_output(final)

        # Execute tool calls and build function response parts
        fn_response_parts = []
        for fc in fn_calls:
            tool_name = fc.name
            args = dict(fc.args) if fc.args else {}
            tool_result = call_mcp_tool(tool_name, args)
            fn_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": tool_result},
                    )
                )
            )

        # Append model's tool call + our tool results to the conversation
        contents.append(response.candidates[0].content)
        contents.append(types.Content(role="user", parts=fn_response_parts))

    final = response.text or "Unable to complete the request. Please rephrase."
    return sanitize_output(final)


if __name__ == "__main__":
    print("Building vector store…")
    build_vectorstore()
    print("\nAgent ready. Type your question (Ctrl+C to quit):\n")
    history: list[dict] = []
    while True:
        try:
            q = input("You: ").strip()
            if not q:
                continue
            answer = run_agent(q, history)
            print(f"\nAgent: {answer}\n")
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": answer})
        except KeyboardInterrupt:
            print("\nBye!")
            break
