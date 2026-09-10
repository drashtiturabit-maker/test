from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.agent.prompts import CX_AGENT_PROMPT, TONE_DESCRIPTIONS
from app.agent.tools import (
    capture_lead_information_tool,
    math_expression_evaluator,
    meeting_scheduling_tool,
    retrieve_knowledge_tool,
)
from app.core.config import get_settings

settings = get_settings()


def create_cx_agent(enable_leads: bool = True, enable_meetings: bool = True):
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.2,
    )

    tools = [retrieve_knowledge_tool, math_expression_evaluator]
    if enable_leads:
        tools.append(capture_lead_information_tool)
    if enable_meetings:
        tools.append(meeting_scheduling_tool)

    prompt = ChatPromptTemplate.from_messages([
        ("system", CX_AGENT_PROMPT),
        MessagesPlaceholder("messages"),
    ])

    return prompt | llm.bind_tools(tools, tool_choice="auto", parallel_tool_calls=False)


def build_system_vars(agent_config: dict) -> dict:
    tone = agent_config.get("tone", "professional")
    return {
        "bot_name": agent_config.get("bot_name", "Assistant"),
        "company_name": agent_config.get("company_name", "Company"),
        "tone_description": TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["professional"]),
        "custom_instructions": agent_config.get("custom_instructions", ""),
        "fallback_message": agent_config.get(
            "fallback_message",
            "I don't have that information right now.",
        ),
        "current_date": datetime.now().strftime("%a, %d %b %Y"),
    }
