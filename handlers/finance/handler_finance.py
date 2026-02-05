import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import questionary
import yfinance as yf
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from agents.agent_factory import create_llm_agent
from prompts.finance_prompt import finance_comment_prompt, get_finance_intent_prompt

# Load tickers from fixtures
_tickers_path = Path(__file__).resolve().parent.parent.parent / "fixtures" / "tickers.json"
with open(_tickers_path) as f:
    _tickers_data = json.load(f)

_valid_tickers = {entry["ticker"].upper() for entry in _tickers_data}

def _get_finance_agent():
    """Create a finance agent. Previous LLM instances are freed by the factory."""
    return create_llm_agent(
        model_name=os.environ['MODEL_QWEN3'],
    )
    


def _classify_intent(query: str) -> dict:
    """Classify user intent and extract ticker, data type, and time period.

    Uses tickers.json to resolve company names to ticker symbols.

    Args:
        query: The user's financial query

    Returns:
        Dictionary with keys: ticker, dataType, period

    Example:
        >>> _classify_intent("What's Apple stock price?")
        {"ticker": "AAPL", "dataType": "CURRENT", "period": null}
    """
    messages = [
        SystemMessage(content=get_finance_intent_prompt(_tickers_data)),
        HumanMessage(content=query)
    ]

    agent = _get_finance_agent()
    response = agent.invoke({
        "messages": messages
    })

    # Extract the response content
    result = response["messages"][-1].content.strip()
    logger.debug(f"Raw LLM response for intent classification: {result}")

    # Try to parse JSON response
    try:
        # Strip <think>...</think> blocks (Qwen3 reasoning output)
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()

        # Remove markdown code blocks if present
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)

        intent_data = json.loads(result)

        # Validate required fields
        if "ticker" not in intent_data or "dataType" not in intent_data:
            logger.warning(f"Missing required fields in JSON response: {result}")
            return {"ticker": "UNKNOWN_TICKER", "dataType": "CURRENT", "period": None}

        # Validate ticker against tickers.json
        ticker = (intent_data.get("ticker") or "").upper()
        if ticker not in _valid_tickers:
            logger.warning(f"Ticker '{ticker}' not found in tickers.json")
            return {"ticker": "UNKNOWN_TICKER", "dataType": "CURRENT", "period": None, "error": "TICKER_NOT_IN_JSON"}

        return intent_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {result}. Error: {e}")
        return {"ticker": "UNKNOWN_TICKER", "dataType": "CURRENT", "period": None}


def _comment_on_data(query: str, data: any) -> str:
    """Comment on the financial data.

    Args:
        data: Anything coming back from yFinance

    Returns:
        Formatted string: Markdown
    """
    messages = [
        SystemMessage(content=finance_comment_prompt),
        HumanMessage(content={ query, data })
    ]

    agent = _get_finance_agent()
    response = agent.invoke({
        "messages": messages
    })

    result = response["messages"][-1].content.strip()

    return result


def handle_finance_stocks(query: str, retry_count: int = 0) -> str:
    """Handle stock prices and financial information.

    Args:
        query: The original user query
        retry_count: Number of retry attempts made (internal use)

    Returns:
        Natural language response about the stock/financial data
    """
    MAX_RETRIES = 3

    # Classify the intent
    intent = _classify_intent(query)
    logger.debug(f"Extracted intent: {intent} from {query} (attempt {retry_count + 1}/{MAX_RETRIES + 1})")

    # Extract values from JSON response
    tickerSymbol = intent.get("ticker")
    dataType = intent.get("dataType")
    period = intent.get("period")
    isHistorical = dataType == "HISTORICAL" if dataType else False

    logger.debug(f"Ticker: {tickerSymbol}, isHistorical: {isHistorical}, period: {period}")

    # Validate that required variables are present and retry if needed
    should_retry = (
        tickerSymbol == "UNKNOWN_TICKER" or
        not tickerSymbol or
        not dataType
    )

    # If the ticker was not found in tickers.json, return immediately without retrying
    if intent.get("error") == "TICKER_NOT_IN_JSON":
        return "I couldn't resolve the ticker symbol for that company. Please update tickers.json with the correct entry."

    if should_retry:
        if retry_count < MAX_RETRIES:
            logger.warning(
                f"Intent classification failed (ticker: {tickerSymbol}, dataType: {dataType}) - "
                f"retrying ({retry_count + 1}/{MAX_RETRIES})"
            )
            return handle_finance_stocks(query, retry_count + 1)
        else:
            logger.error(
                f"Failed to classify intent after {MAX_RETRIES} retries - "
                f"ticker: {tickerSymbol}, dataType: {dataType}"
            )
            return "I couldn't determine which stock you're asking about. Please try rephrasing your question."

    try:
        start_time = time.time()
        stock_data = _retrieve_stock_data(tickerSymbol, isHistorical, period)


    except any as error:
        logger.error(f"An error occurred: {error}")
        questionary.select(
            "Stock retrieval failed, want to retry?",
            choices=[
                "Order a pizza",
                "Make a reservation",
                "Ask for opening hours"
            ]
        ).ask()

        return "I encountered an error while retrieving stock data. Please try again."


    try:
        start_time = time.time()
        comment = _comment_on_data(query, stock_data)
        logger.info(comment)
        logger.debug(f"Comment received in {time.time() - start_time}s ")
        return comment

    except any as error:
        logger.error(f"An error occurred: {error}")
        return "I encountered an error while analyzing the stock data. Please try again."


def _retrieve_stock_data(
    tickerSymbol: str, isHistorical: bool, period: Optional[str] = None
) -> str | dict:
    """Retrieve stock data for a given ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        period: Optional time period for historical data (e.g., '1d', '5d', '1mo', '1y')

    Returns:
        Dictionary containing stock price data

    Example:
        data = await _retrieve_stock_price('AAPL')
        data = await _retrieve_stock_price('AAPL', period='1mo')
    """
    ticker_symbol = tickerSymbol
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        if isHistorical:
            data = ticker.history(period=period)
            # Convert DataFrame to string for the agent
            data_str = data.to_string()
        else:
            data = ticker.fast_info['lastPrice']
            # Convert dict to formatted string for the agent
            data_str = str(data)


    except any as error:
        return error

    return data_str
        
    
