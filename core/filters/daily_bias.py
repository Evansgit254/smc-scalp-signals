import pandas as pd
import pandas_ta_classic as ta

class DailyBias:
    @staticmethod
    def analyze(d1_df: pd.DataFrame) -> dict:
        """
        Analyzes Daily (D1) structure to determine higher timeframe bias.
        This allows the system to override 'Choppy' signals on lower timeframes
        if the Daily expansion carries significant momentum.
        """
        if d1_df is None or d1_df.empty or len(d1_df) < 50:
            return {'bias': 'NEUTRAL', 'strength': 'WEAK'}

        latest = d1_df.iloc[-1]
        
        # 1. EMA Trend (20 Daily EMA is standard for short-term institutional trend)
        ema_20 = d1_df['ema_20'].iloc[-1] if 'ema_20' in d1_df.columns else ta.ema(d1_df['close'], length=20).iloc[-1]
        
        bias = "NEUTRAL"
        if latest['close'] > ema_20:
            bias = "BULLISH"
        elif latest['close'] < ema_20:
            bias = "BEARISH"
            
        # 2. Candle Structure (Expansion check)
        open_price = latest['open']
        close_price = latest['close']
        high_price = latest['high']
        low_price = latest['low']
        
        is_green = close_price > open_price
        is_red = close_price < open_price
        
        # Range calculation
        daily_range = high_price - low_price
        body = abs(close_price - open_price)
        
        # Strength Calculation
        strength = "WEAK"
        
        # Strong D1 Expansion: Trading near highs/lows with large body
        if is_green and bias == "BULLISH":
            # If closing near the high (>75% of range) and decent body
            if (close_price - low_price) > (daily_range * 0.75) and body > (daily_range * 0.5):
                strength = "STRONG"
                
        elif is_red and bias == "BEARISH":
            # If closing near the low (>75% from high)
            if (high_price - close_price) > (daily_range * 0.75) and body > (daily_range * 0.5):
                strength = "STRONG"
                
        return {
            'bias': bias,
            'strength': strength,
            'ema_20': ema_20
        }
