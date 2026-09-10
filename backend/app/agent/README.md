# CX LangGraph Agent

Production CX agent adapted from `agents/agents/graphs/cx/`.

## Graph Structure

```
START → cx_node → conditional → cx_tool_node → cx_node → END
```

Same pattern as the original CX graph in `agents/agents/graphs/cx/graph.py`.

## Files

| File | Purpose |
|---|---|
| `graph.py` | StateGraph build & compile |
| `nodes.py` | `cx_node`, `cx_tool_node`, routing |
| `tools.py` | RAG retrieval, lead capture, meetings |
| `state.py` | `CXGraphState` typed dict |
| `runnables.py` | LLM + tool binding |
| `prompts.py` | System prompt with tone/instructions |
| `executor.py` | SSE streaming wrapper |

## Key Difference from Original

| Original | Production |
|---|---|
| `search_info` → Milvus API | `retrieve_knowledge` → Pinecone namespace |
| `list_files`, `inspect_files` | Removed (simple RAG) |
| `code_execution_tool` | Removed |
| `display_image` | Removed |
| Redis checkpointer | Stateless per request (history from PostgreSQL) |

## Tools

1. **retrieve_knowledge** — Queries Pinecone using client's namespace
2. **capture_lead_information** — Lead capture (from original CX tools)
3. **meeting_scheduling** — Cal.com scheduling (from original CX tools)
4. **math_expression_evaluator** — Safe math eval

## Runtime Config

Passed via LangGraph `configurable`:

```python
{
    "thread_id": session_id,
    "client_key": "ck_...",
    "pinecone_namespace": "client_uuid",
    "system_vars": { bot_name, company_name, tone, ... },
    "lead_generation_config": { "status": True },
}
```

## Agent Config Injection

Agent behavior is driven by `agent_configs` table:
- `bot_name`, `company_name`, `tone`
- `custom_instructions`, `fallback_message`

These map directly to the system prompt template in `prompts.py`.
