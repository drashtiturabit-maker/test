from typing_extensions import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class CXGraphState(TypedDict):
    user_query: list
    messages: Annotated[list[AnyMessage], add_messages]
    expense: dict
    client_key: str
    session_id: str
    assistant_name: str
    bot_name: str
    company_name: str
    tone_description: str
    custom_instructions: str
    fallback_message: str
    meeting_info: dict
    lead_generation_obj_mapper: dict
    lead_collection_intents: list
    all_lead_fields_collected: bool
    retrieved_sources: list
