import pandas as pd

class VolatilityFilter:
    @staticmethod
    def is_volatile(m1_df: pd.DataFrame) -> bool:
        """
        Checks if ATR is expanding and above average.
        """
        if m1_df.empty or len(m1_df) < 2:
            return False

        latest = m1_df.iloc[-1]
        prev = m1_df.iloc[-2]
        
        atr = latest['atr']
        atr_avg = latest['atr_avg']
        prev_atr = prev['atr']

        # ATR > ATR_AVG and ATR >= Prev ATR (expanding or holding high)
        return atr > atr_avg and atr >= prev_atr

    @staticmethod
    def get_atr_status(m1_df: pd.DataFrame) -> str:
        if VolatilityFilter.is_volatile(m1_df):
            return "Expanding"
        return "Compressed"
