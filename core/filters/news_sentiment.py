import logging

class NewsSentimentAnalyzer:
    # Categories for standard economic impact interpretation
    # If "Actual > Forecast", it's BULLISH for the currency.
    BULLISH_IF_HIGHER = [
        "GDP", "CPI", "Retail Sales", "Employment Change", "Interest Rate", 
        "PMI", "Consumer Confidence", "Trade Balance", "PPI"
    ]
    
    # If "Actual < Forecast", it's BULLISH for the currency (e.g., lower unemployment is good).
    BULLISH_IF_LOWER = [
        "Unemployment Rate", "Jobless Claims", "Claimant Count Change"
    ]

    @staticmethod
    def get_bias(event: dict) -> str:
        """
        Predicts the bias (BULLISH/BEARISH) based on Forecast and Previous.
        Note: This is a pre-event prediction based on the expected change.
        """
        title = event.get('title', '')
        forecast_str = event.get('forecast', '')
        previous_str = event.get('previous', '')

        if not forecast_str or not previous_str:
            return "NEUTRAL"

        try:
            # Clean and parse values (remove %, K, M, etc.)
            def clean_val(val):
                return float(val.strip().replace('%', '').replace('K', '').replace('M', '').replace('B', '').replace(',', ''))

            forecast = clean_val(forecast_str)
            previous = clean_val(previous_str)

            is_higher_bullish = any(term in title for term in NewsSentimentAnalyzer.BULLISH_IF_HIGHER)
            is_lower_bullish = any(term in title for term in NewsSentimentAnalyzer.BULLISH_IF_LOWER)

            if is_higher_bullish:
                if forecast > previous:
                    return "BULLISH"
                elif forecast < previous:
                    return "BEARISH"
            
            if is_lower_bullish:
                if forecast < previous:
                    return "BULLISH"
                elif forecast > previous:
                    return "BEARISH"

        except Exception as e:
            logging.error(f"Error analyzing sentiment for {title}: {e}")
            pass

        return "NEUTRAL"
