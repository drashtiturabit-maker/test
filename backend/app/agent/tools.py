import logging
import re
from datetime import datetime
from typing import Annotated, Literal, Optional, Union
from zoneinfo import ZoneInfo

import httpx
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import StructuredTool, tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from app.agent.state import CXGraphState
from app.services.pinecone_store import vector_store

logger = logging.getLogger(__name__)


# ── RAG Retrieval Tool ────────────────────────────────────────────────────

class RetrieveKnowledgeSchema(BaseModel):
    query_text: str = Field(..., description="Search query to find relevant knowledge")
    state: Annotated[dict, InjectedState]
    config: Annotated[RunnableConfig, InjectedState]


def retrieve_knowledge_func(query_text: str, state: dict, config: RunnableConfig):
    namespace = config.get("configurable", {}).get("pinecone_namespace", "")
    if not namespace:
        return "Knowledge base not configured for this client.", {"retrieved_sources": []}

    results = vector_store.query(namespace=namespace, query_text=query_text, top_k=5)
    if not results:
        return "No relevant information found. Try a different search query.", {"retrieved_sources": []}

    feedback = "Retrieved Knowledge:\n\n"
    sources = []
    for i, r in enumerate(results, 1):
        feedback += f"### Result {i} (score: {r['score']:.2f})\n"
        feedback += f"Source: {r.get('source_name', 'unknown')}\n"
        if r.get("source_url"):
            feedback += f"URL: {r['source_url']}\n"
            sources.append(r["source_url"])
        feedback += f"{r['text']}\n\n"

    return feedback.strip(), {"retrieved_sources": sources}


retrieve_knowledge_tool = StructuredTool.from_function(
    func=retrieve_knowledge_func,
    name="retrieve_knowledge",
    description=(
        "Search the company's knowledge base for relevant information. "
        "ALWAYS use this tool FIRST when answering any user question."
    ),
    args_schema=RetrieveKnowledgeSchema,
)


# ── Math Evaluator ────────────────────────────────────────────────────────

@tool
def math_expression_evaluator(expression: str) -> str:
    """Safely evaluate basic math expressions."""
    allowed = re.compile(r"^[\d\s+\-*/().%]+$")
    if not allowed.match(expression):
        return "Invalid expression."
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


# ── Lead Capture (simplified from existing CX agent) ────────────────────────

class Information(BaseModel):
    key: str
    value: Optional[Union[str, int, float]] = None


class CaptureLeads(BaseModel):
    action: Literal["save_information", "get_remaining_fields"]
    information: Optional[list[Information]] = None
    lead_collection_intent: Optional[str] = "General Interest"
    explanation: str = ""
    state: Annotated[dict, InjectedState]
    config: Annotated[RunnableConfig, InjectedState]


LEAD_FIELDS = {
    "name": {"db_key": "name", "preference": "medium", "optional": True},
    "email": {"db_key": "email", "preference": "high", "optional": False},
    "company name": {"db_key": "company_name", "preference": "low", "optional": True},
    "mobile": {"db_key": "mobile_no", "preference": "low", "optional": True},
}


def capture_lead_func(action, information, lead_collection_intent, explanation, state, config):
    lead_config = config.get("configurable", {}).get("lead_generation_config", {})
    if not lead_config.get("status"):
        return "Lead capture is disabled.", {}

    mapper = state.get("lead_generation_obj_mapper") or {
        k: {"name": k, "value": "", **v} for k, v in LEAD_FIELDS.items()
    }
    state_update = {"lead_generation_obj_mapper": mapper}

    if action == "get_remaining_fields":
        remaining = [f"`{k}`" for k, v in mapper.items() if not v.get("value")]
        return f"Fields still needed: {', '.join(remaining) or 'none'}", state_update

    for item in information or []:
        if item.key in mapper:
            mapper[item.key]["value"] = str(item.value) if item.value else ""

    intents = state.get("lead_collection_intents", [])
    if lead_collection_intent and lead_collection_intent not in intents:
        intents.append(lead_collection_intent)

    state_update["lead_collection_intents"] = intents
    state_update["lead_data_for_save"] = {
        mapper[k]["db_key"]: mapper[k]["value"]
        for k in mapper
        if mapper[k].get("value")
    }
    return "Lead information saved.", state_update


capture_lead_information_tool = StructuredTool.from_function(
    func=capture_lead_func,
    name="capture_lead_information",
    description="Collect and save lead contact information from potential customers.",
    args_schema=CaptureLeads,
)


# ── Meeting Scheduling (from existing CX agent) ───────────────────────────

CAL_CFG = {
    "api_base": "https://api.cal.com/v2",
    "api_key": "",
    "username": "",
    "event_type_slug": "",
    "integration_platform": "google-meet",
    "user_timezone": "Asia/Kolkata",
}


class MeetingAction(str):
    SCHEDULE = "schedule"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"


class MeetingSchedulingRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    scheduling_date: Optional[str] = None
    scheduling_time: Optional[str] = None
    action: str
    reschedule_booking_uid: Optional[str] = None
    state: Annotated[dict, InjectedState]
    config: Annotated[RunnableConfig, InjectedState]


def meeting_scheduling_func(name, email, scheduling_date, scheduling_time, action, reschedule_booking_uid, state, config):
    meeting_info = dict(state.get("meeting_info") or {})
    if name:
        meeting_info["name"] = name.strip()
    if email:
        meeting_info["email"] = email.strip().lower()
    if scheduling_date:
        meeting_info["scheduling_date"] = scheduling_date.strip()
    if scheduling_time:
        meeting_info["scheduling_time"] = scheduling_time.strip()

    state_update = {"meeting_info": meeting_info}
    required = ["name", "email", "scheduling_date", "scheduling_time"]
    missing = [f for f in required if not meeting_info.get(f)]

    if action == "schedule" and missing:
        return f"Please provide: {', '.join(missing)}", state_update

    if action == "schedule":
        if not CAL_CFG.get("api_key"):
            return (
                f"Meeting request recorded for {meeting_info.get('name')} "
                f"on {meeting_info.get('scheduling_date')} at {meeting_info.get('scheduling_time')}. "
                "Our team will confirm shortly."
            ), state_update
        try:
            tz = ZoneInfo(CAL_CFG["user_timezone"])
            dt = datetime.strptime(
                f"{meeting_info['scheduling_date']} {meeting_info['scheduling_time']}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=tz)
            start_utc = dt.astimezone(ZoneInfo("UTC")).isoformat()
            headers = {"Authorization": f"Bearer {CAL_CFG['api_key']}", "cal-api-version": "2024-08-13"}
            payload = {
                "attendee": {"name": meeting_info["name"], "email": meeting_info["email"], "timeZone": CAL_CFG["user_timezone"]},
                "start": start_utc,
                "eventTypeSlug": CAL_CFG["event_type_slug"],
                "username": CAL_CFG["username"],
            }
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{CAL_CFG['api_base']}/bookings", json=payload, headers=headers)
            data = resp.json()
            if resp.status_code >= 400:
                return f"Slot unavailable. Please try a different time.", state_update
            uid = data.get("data", {}).get("uid", "N/A")
            meet = data.get("data", {}).get("meetingUrl", "N/A")
            meeting_info["booking_uid"] = uid
            return f"MEETING_BOOKED|uid={uid}|meet_link={meet}", {"meeting_info": meeting_info}
        except Exception as e:
            return f"Scheduling error: {e}", state_update

    return f"Action '{action}' noted.", state_update


meeting_scheduling_tool = StructuredTool.from_function(
    func=meeting_scheduling_func,
    name="meeting_scheduling",
    description="Schedule, reschedule, or cancel meetings with the sales team.",
    args_schema=MeetingSchedulingRequest,
)

_TOOL_REGISTRY = {
    "retrieve_knowledge": retrieve_knowledge_tool,
    "capture_lead_information": capture_lead_information_tool,
    "meeting_scheduling": meeting_scheduling_tool,
    "math_expression_evaluator": math_expression_evaluator,
}
