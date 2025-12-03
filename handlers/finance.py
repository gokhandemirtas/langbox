import os
import time
from typing import Optional

import yfinance as yf
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm_agent
from prompts.finance_prompt import finance_intent_prompt

# Lazy initialization of finance agent
_finance_agent = None

def _get_finance_agent():
    """Get or create the finance agent."""
    global _finance_agent
    if _finance_agent is None:
        _finance_agent = create_llm_agent(
            model_name=os.environ['MODEL_CONVERSATIONAL'],
        )
    return _finance_agent


def _classify_intent(query: str) -> str:
    """Classify user intent and extract ticker, data type, and time period.

    Args:
        query: The user's financial query

    Returns:
        Formatted string: TICKER/DATA_TYPE/TIME_PERIOD

    Example:
        >>> _classify_intent("What's Apple stock price?")
        'AAPL/CURRENT'
    """
    messages = [
        SystemMessage(content=finance_intent_prompt),
        HumanMessage(content=query)
    ]

    agent = _get_finance_agent()
    response = agent.invoke({
        "messages": messages
    })

    # Extract the response content
    result = response["messages"][-1].content.strip()
    logger.debug(f"Intent classification result: {result}")

    return result


def _comment_on_data(data: any) -> str:
    """Comment on the financial data.

    Args:
        data: Anything coming back from yFinance

    Returns:
        Formatted string: Markdown
    """
    messages = [
        SystemMessage(content="""
            Comment on the financial data you're given. This data is provided by Yahoo,
            and you will likely get tabular format data for historical record.
            Your job is to make it understandable by the user
        """),
        HumanMessage(content=data)
    ]

    agent = _get_finance_agent()
    response = agent.invoke({
        "messages": messages
    })

    result = response["messages"][-1].content.strip()

    return result


def handle_finance_stocks(query: str) -> None:
    """Handle stock prices and financial information.

    Args:
        query: The original user query
    """
    # Classify the intent
    intent = _classify_intent(query)
    logger.debug(f"Extracted intent: {intent} from {query}")

    # Parse the intent by splitting on forward slash
    parts = intent.split('/')

    # Extract variables based on number of parts
    tickerSymbol = parts[0] if len(parts) > 0 else None
    isHistorical = parts[1] == "HISTORICAL" if len(parts) > 1 else False
    period = parts[2] if len(parts) > 2 else None

    logger.debug(f"Parsed - ticker: {tickerSymbol}, isHistorical: {isHistorical}, period: {period}")

    # Validate that required variables are present
    if not tickerSymbol:
        logger.error("Missing ticker symbol - cannot retrieve stock price")
        return

    if isHistorical is None:
        logger.error("Missing isHistorical flag - cannot determine data type")
        return

    _retrieve_stock_price(tickerSymbol = tickerSymbol, isHistorical=isHistorical, period=period)
    # TODO: Implement data fetching based on classified intent


def _retrieve_stock_price(
    tickerSymbol: str, isHistorical: bool, period: Optional[str] = None
) -> str:
    """Retrieve stock price for a given ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        period: Optional time period for historical data (e.g., '1d', '5d', '1mo', '1y')

    Returns:
        Dictionary containing stock price data

    Example:
        data = await _retrieve_stock_price('AAPL')
        data = await _retrieve_stock_price('AAPL', period='1mo')
    """
    start_time = time.time()
    ticker_symbol = tickerSymbol
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        if isHistorical:
            data = ticker.history(period=period)
            # Convert DataFrame to string for the agent
            data_str = data.to_string()
        else:
            data = ticker.fast_info
            # Convert dict to formatted string for the agent
            data_str = str(data)

        logger.debug(f"Data received for {ticker_symbol}, calling commentor")
        comment = _comment_on_data(data_str)
        logger.debug(f"Comment finished in {time.time() - start_time}s")
        logger.info(comment)

    except any as error:
        logger.error(f"An error occurred: {error}")
        return error

    return comment
        
    
