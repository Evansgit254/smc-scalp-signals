from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
from core.filters.risk_manager import RiskManager
from indicators.calculations import IndicatorCalculator

class StatisticalArbitrageStrategy(BaseStrategy):
    """
    Identifies mathematical divergences between an asset and the US Dollar Index (DXY).
    If DXY is surging but a USD-quote asset (like EURUSD) is not correctly dropping, 
    we fade the asset to catch up to the macro spread.
    """

    def get_id(self) -> str:
        return "stat_arb_v1"

    def get_name(self) -> str:
        return "Statistical Arbitrage (DXY Divergence)"

    async def analyze(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        news_events: list,
        market_context: dict,
    ) -> Optional[dict]:
        try:
            df = data.get('h1')
            if df is None or len(df) < 50:
                return None

            if 'DXY' not in market_context:
                return None
                
            dxy_df = market_context['DXY']
            if len(dxy_df) < 50:
                return None

            latest = df.iloc[-1]
            dxy_latest = dxy_df.iloc[-1]
            
            # V26.3: REGIME FILTER — don't trade stat arb in a trending market.
            # In trending macro environments, divergence correction can take days,
            # exceeding our 4-12 hour expected hold. Only trade in RANGING regimes.
            regime = IndicatorCalculator.get_market_regime(df)
            if regime == 'TRENDING':
                return None
            
            # We need standard Z-Scores
            asset_z = latest.get('zscore_20')
            dxy_z = dxy_latest.get('zscore_20')
            
            if asset_z is None or dxy_z is None:
                return None

            # V26.3: DIVERGENCE PERSISTENCE — require 2 consecutive bars of divergence
            # Prevents firing on a single-bar DXY spike that immediately reverses
            prev_asset_z = df.iloc[-2].get('zscore_20', 0) if len(df) >= 2 else 0
            prev_dxy_z   = dxy_df.iloc[-2].get('zscore_20', 0) if len(dxy_df) >= 2 else 0

            direction = None
            quality = 0.0
            
            # Most USD pairs move inversely to DXY.
            # If DXY is highly overbought (Z > +2.0), USD pairs SHOULD be extremely oversold (Z < -2.0).
            # If EURUSD is actually > 0 (divergence), SELL EURUSD because it should drop.
            is_usd_quote = symbol in ["EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "GC=F"]
            is_usd_base = symbol in ["USDJPY=X"] # Moves WITH DXY
            
            # USD-Quote assets (EURUSD, GC=F, etc) diverge when DXY is extremely overextended
            # V26.3: Raised threshold from 1.8 to 2.2 to reduce simultaneous multi-symbol firing
            # and require a more extreme, persistent divergence signal
            DXY_THRESHOLD = 2.2
            if is_usd_quote:
                if dxy_z > DXY_THRESHOLD and prev_dxy_z > DXY_THRESHOLD and asset_z > 0.0 and prev_asset_z > 0.0:
                    direction = "SELL"
                    quality = 8.5
                elif dxy_z < -DXY_THRESHOLD and prev_dxy_z < -DXY_THRESHOLD and asset_z < 0.0 and prev_asset_z < 0.0:
                    direction = "BUY"
                    quality = 8.5
                    
            elif is_usd_base:
                if dxy_z > DXY_THRESHOLD and prev_dxy_z > DXY_THRESHOLD and asset_z < 0.0 and prev_asset_z < 0.0:
                    direction = "BUY"
                    quality = 8.5
                elif dxy_z < -DXY_THRESHOLD and prev_dxy_z < -DXY_THRESHOLD and asset_z > 0.0 and prev_asset_z > 0.0:
                    direction = "SELL"
                    quality = 8.5

            if not direction:
                return None

            entry = latest['close']
            atr = latest.get('atr', 0.001)
            
            sl_dist = atr * 1.5
            tp_dist = atr * 2.5
            
            sl = entry - sl_dist if direction == "BUY" else entry + sl_dist
            tp = entry + tp_dist if direction == "BUY" else entry - tp_dist
            
            risk_details = RiskManager.calculate_lot_size(symbol, entry, sl)

            return {
                'strategy_id': self.get_id(),
                'strategy_name': self.get_name(),
                'symbol': symbol,
                'direction': direction,
                'timeframe': 'H1',
                'trade_type': 'STAT_ARB',
                'entry_price': entry,
                'sl': sl,
                'tp0': tp,
                'tp1': tp,
                'tp2': tp,
                'confidence': 1.5,
                'quality_score': quality,
                'regime': 'DIVERGENCE',
                'macro_bias': 'CONTRARIAN',
                'risk_details': risk_details,
                'expected_hold': '4-12 hours',
                'score_details': {
                    'asset_z': float(asset_z),
                    'dxy_z': float(dxy_z)
                }
            }
        except Exception as e:
            return None
