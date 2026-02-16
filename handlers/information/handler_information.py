import os

import wikipedia
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm
from prompts.information_prompt import informationIntentPrompt
from pydantic_types.information_intent_response import InformationIntentResponse
from utils.llm_structured_output import generate_structured_output


def _classify_intent(query: str) -> InformationIntentResponse:
    """Extract the search keyword from the user's query using structured output.

    Args:
        query: The user's original query

    Returns:
        InformationIntentResponse with the extracted keyword
    """
    return generate_structured_output(
        model_name=os.environ["MODEL_QWEN2.5"],
        user_prompt=query,
        system_prompt=informationIntentPrompt,
        pydantic_model=InformationIntentResponse,
    )


def _search_wiki(keyword: str) -> str:
    """Search Wikipedia for the given keyword.

    Args:
        keyword: The search term to look up on Wikipedia

    Returns:
        Wikipedia summary text, or an error message if not found
    """
    try:
        result = wikipedia.summary(keyword, sentences=5)
        logger.debug(f"Wikipedia result for '{keyword}': {result[:200]}...")
        return result
    except wikipedia.DisambiguationError as e:
        logger.warning(f"Disambiguation for '{keyword}', trying first option: {e.options[0]}")
        return wikipedia.summary(e.options[0], sentences=5)
    except wikipedia.PageError:
        logger.warning(f"No Wikipedia page found for '{keyword}'")
        return f"No Wikipedia article found for '{keyword}'."


async def handle_information_query(query: str) -> str:
    """Handle general knowledge and information lookup using Wikipedia and Qwen2.5.

    Args:
        query: The original user query

    Returns:
        Information response
    """

    intent = _classify_intent(query)
    logger.debug(f"Detected secondary intent: {query}, Extracted keyword: {intent.keyword}")

    wiki_content = _search_wiki(intent.keyword)

    llm = create_llm(
        model_name=os.environ.get("MODEL_QWEN2.5"),
        temperature=0.3,
        max_tokens=1024,
    )

    system_prompt = f"""You are a knowledgeable assistant that ONLY uses the provided Wikipedia content to answer questions.
        Wikipedia content:
        {wiki_content}

        IMPORTANT RULES:
        - You MUST answer ONLY using the Wikipedia content below. Do NOT use your own training data or prior knowledge.
        - If the Wikipedia content does not contain enough information to answer, say so.
        - Summarize the relevant information into a single concise paragraph.
        - Do NOT add any facts, details, or context that are not present in the Wikipedia content.
    """

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ])

    return response.content
