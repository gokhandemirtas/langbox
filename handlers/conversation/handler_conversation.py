import os

from langchain_core.messages import HumanMessage, SystemMessage

from agents.agent_factory import create_llm_agent
from memory.session import checkpointer, config
from prompts.conversation_prompt import get_conversation_prompt

_agent = None


def _get_conversation_agent():
    global _agent
    if _agent is None:
        _agent = create_llm_agent(
            model_name=os.environ.get("MODEL_GENERALIST"),
            max_tokens=3000,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1,
            checkpointer=checkpointer,
        )
    return _agent


async def handle_conversation(user_query: str, handler_response: str) -> str:
    """Process handler response through conversational agent with session memory.

    Args:
        user_query: The original user question
        handler_response: The response from the specialized handler

    Returns:
        The conversational agent's natural language response
    """
    messages = [
        SystemMessage(content=get_conversation_prompt(handler_response)),
        HumanMessage(content=user_query),
    ]

    agent = _get_conversation_agent()
    response = agent.invoke({"messages": messages}, config=config)
    conversational_response = response["messages"][-1].content.strip()

    return conversational_response
