import multiprocessing
import os
import sys
import time
from typing import Optional

import yfinance as yf
from langchain.agents import create_agent
from langchain_community.chat_models import ChatLlamaCpp
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from prompts.finance_prompt import finance_prompt
from utils import HTTPClient

stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')


class FinanceAgent:
    """Finance agent handler that maintains a single LLM agent instance."""

    _instance = None
    _agent = None
    _llm = None

    def __new__(cls):
        """Ensure only one instance of FinanceAgent exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_agent()
        return cls._instance

    def _initialize_agent(self):
        """Initialize the LLM and agent."""
        try:
            self._llm = ChatLlamaCpp(
                temperature=0.0,  # Set to 0 for maximum determinism
                model_path=f"{os.environ['MODEL_PATH']}/{os.environ['MODEL_GENERAL_PURPOSE']}",
                n_ctx=10000,
                n_gpu_layers=8,
                n_batch=1000,  # Should be between 1 and n_ctx, consider VRAM
                max_tokens=512,
                n_threads=multiprocessing.cpu_count() - 1,
                repeat_penalty=1.2,
                top_p=0.1,
                top_k=10,
                verbose=False,
            )
        finally:
            sys.stderr.close()
            sys.stderr = stderr_backup

        self._agent = create_agent(
            model=self._llm
        )

    def classify_intent(self, query: str) -> str:
        """Classify user intent and extract ticker, data type, and time period.

        Args:
            query: The user's financial query

        Returns:
            Formatted string: TICKER/DATA_TYPE/TIME_PERIOD

        Example:
            >>> agent = FinanceAgent()
            >>> agent.classify_intent("What's Apple stock price?")
            'AAPL/CURRENT'
        """
        messages = [
            SystemMessage(content=finance_prompt),
            HumanMessage(content=query)
        ]

        response = self._agent.invoke({
            "messages": messages
        })

        # Extract the response content
        result = response["messages"][-1].content.strip()
        logger.debug(f"Intent classification result: {result}")

        return result

    async def retrieve_stock_price(self, ticker: str) -> dict:
        """Retrieve stock price for a given ticker symbol.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

        Returns:
            Dictionary containing stock price data

        Example:
            agent = FinanceAgent()
            data = await agent.retrieve_stock_price('AAPL')
        """
        async with HTTPClient(base_url="https://www.yahoofinanceapi.com") as client:
            data = await client.get(f"/stocks/{ticker}")
            return data


# Create a singleton instance
_finance_agent = FinanceAgent()


def handle_finance_stocks(query: str) -> None:
    """Handle stock prices and financial information.

    Args:
        query: The original user query
    """
    logger.info(f"[handle_finance_stocks]: {query}")

    # Use the singleton agent to classify intent
    intent = _finance_agent.classify_intent(query)
    logger.info(f"Classified intent: {intent}")

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

    retrieve_stock_price(tickerSymbol = tickerSymbol, isHistorical=isHistorical, period=period)
    # TODO: Implement data fetching based on classified intent


def retrieve_stock_price(tickerSymbol: str, isHistorical: bool, period: Optional[str] = None) -> dict:
    """Retrieve stock price for a given ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        period: Optional time period for historical data (e.g., '1d', '5d', '1mo', '1y')

    Returns:
        Dictionary containing stock price data

    Example:
        data = await retrieve_stock_price('AAPL')
        data = await retrieve_stock_price('AAPL', period='1mo')
    """
    ticker_symbol = tickerSymbol
    ticker = yf.Ticker(ticker_symbol)
    
    if(isHistorical):
        data = ticker.history(period) # data for the last
        logger.info(data)

    elif():
        data = ticker.live()
        logger.info(data)
        
