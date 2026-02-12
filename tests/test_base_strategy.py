import pytest
import pandas as pd
from strategies.base_strategy import BaseStrategy

class ConcreteStrategy(BaseStrategy):
    def analyze(self, symbol, data, news_events, market_context):
        return None
    def get_id(self):
        return "test_strat"
    def get_name(self):
        return "Test Strategy"

def test_base_strategy_methods():
    strategy = ConcreteStrategy()
    assert strategy.get_id() == "test_strat"
    assert strategy.get_name() == "Test Strategy"
    assert strategy.analyze("EURUSD", {}, [], {}) is None

def test_base_strategy_abstract_instantiation():
    with pytest.raises(TypeError):
        # This will fail because BaseStrategy is abstract
        BaseStrategy() 
