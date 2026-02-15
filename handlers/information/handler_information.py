import os

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm


async def handle_information_query(query: str) -> str:
    """Handle general knowledge and information lookup using Qwen2.5.

    Args:
        query: The original user query

    Returns:
        Information response
    """
    logger.debug(f"ROUTE: INFORMATION_QUERY - Looking up information: {query}")

    llm = create_llm(
        model_name=os.environ.get("MODEL_QWEN2.5"),
        temperature=0.3,
        max_tokens=1024,
    )

    system_prompt = (
        "You are a knowledgeable assistant. "
        "Answer the user's question accurately and concisely."
    )

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ])

    return response.content
