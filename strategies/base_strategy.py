from abc import ABC, abstractmethod
from typing import List, Optional, Dict
import pandas as pd

class BaseStrategy(ABC):
    @abstractmethod
    def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        """
        Analyzes market data and returns a signal dictionary if a setup is found.
        """
        pass

    @abstractmethod
    def get_id(self) -> str:
        """
        Returns the unique identifier for the strategy.
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Returns the human-readable name for the strategy.
        """
        pass
