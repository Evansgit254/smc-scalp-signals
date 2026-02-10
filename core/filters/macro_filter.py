import pandas as pd
from typing import Dict, Optional

class MacroFilter:
    @staticmethod
    def get_macro_bias(market_context: Dict[str, pd.DataFrame]) -> Dict[str, str]:
        """
        Analyzes DXY and ^TNX to determine global risk bias.
        """
        bias = {
            'DXY': 'NEUTRAL',
            'TNX': 'NEUTRAL',
            'RISK': 'NEUTRAL'
        }
        
        # 1. DXY Trend (Dollar Index)
        if 'DXY' in market_context:
            dxy_df = market_context['DXY']
            if dxy_df is not None and len(dxy_df) > 0 and 'ema_20' in dxy_df.columns:
                ema = dxy_df.iloc[-1].get('ema_20')
                if ema is not None:
                    bias['DXY'] = 'BULLISH' if dxy_df.iloc[-1]['close'] > ema else 'BEARISH'
        
        # 2. Yield Trend (US 10Y Treasury)
        if '^TNX' in market_context:
            tnx_df = market_context['^TNX']
            if tnx_df is not None and len(tnx_df) > 0 and 'ema_20' in tnx_df.columns:
                ema = tnx_df.iloc[-1].get('ema_20')
                if ema is not None:
                    bias['TNX'] = 'BULLISH' if tnx_df.iloc[-1]['close'] > ema else 'BEARISH'
                
        # 3. Aggregate Risk Bias
        if bias['DXY'] == 'BULLISH' and bias['TNX'] == 'BULLISH':
            bias['RISK'] = 'OFF' # Strong Dollar + High Yields = Bad for Gold/Indices
        elif bias['DXY'] == 'BEARISH' and bias['TNX'] == 'BEARISH':
            bias['RISK'] = 'ON'
            
        return bias

    @staticmethod
    def is_macro_safe(symbol: str, direction: str, bias: Dict[str, str]) -> bool:
        """
        Verifies if a specific trade aligns with macro trends.
        Permissive: Only blocks if there is a DIRECT CONFLICT.
        """
        # Gold (GC=F) Logic: Inverse to Yields
        if symbol == "GC=F":
            if direction == "BUY":
                # Only block if Yields are actively BULLISH
                return bias['TNX'] != 'BULLISH'
            else:
                # Only block if Yields are actively BEARISH
                return bias['TNX'] != 'BEARISH'
                
        # USD Pairs (EURUSD, GBPUSD) Logic: Inverse to DXY
        if symbol in ["EURUSD=X", "GBPUSD=X", "NZDUSD=X"]:
            if direction == "BUY":
                # Only block if DXY is actively BULLISH
                return bias['DXY'] != 'BULLISH'
            else:
                return bias['DXY'] != 'BEARISH'
                
        # Indices (^IXIC) Logic: Pro-Risk
        if symbol in ["^IXIC", "^GSPC"]:
            if direction == "BUY":
                return bias['RISK'] != 'OFF'
            else:
                return bias['RISK'] != 'ON'
                
        return True 
