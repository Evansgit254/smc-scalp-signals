"""
Dynamic Reasoning Library
Contains randomized phrase variations for signal explanations to prevent repetition.
"""

REASONING_LIBRARY = {
    'BUY': {
        'SPEED': [
            "🚀 <b>Speed:</b> Price is moving up quickly, showing strong buyer interest.",
            "🚀 <b>Momentum:</b> Fast upward move indicates eager buyers.",
            "🚀 <b>Velocity:</b> Buyers are aggressive, pushing price up rapidly.",
            "🚀 <b>Surge:</b> Sudden upward spike suggests a breakout wave."
        ],
        'DISCOUNT': [
            "📉 <b>Discount:</b> Price has dropped too fast and is likely to snap back up (Oversold).",
            "📉 <b>Value:</b> Recent drop offers a great entry price relative to the trend.",
            "📉 <b>Pullback:</b> Market is oversold, expecting a sharp snapback.",
            "📉 <b>Cheap:</b> Price is technically undervalued here, inviting buyers."
        ],
        'STRENGTH': [
            "💪 <b>Strength:</b> Buyers are stepping in aggressively right now.",
            "💪 <b>Power:</b> Bulls are currently in control of the price action.",
            "💪 <b>Force:</b> Strong buying pressure is evident on the tape.",
            "💪 <b>Dominance:</b> Buyers are overwhelming sellers at this level."
        ],
        'WHY_NOT_SELL': [
            "⛔ <b>Why NOT Sell?</b> Sellers have failed to push price lower (Support Holding).",
            "⛔ <b>Risk of Selling:</b> Momentum has shifted up; selling now would be fighting the trend.",
            "⛔ <b>Caution:</b> Attempts to go lower were rejected instantly.",
            "⛔ <b>Trap:</b> Bears are trapped; selling here provides liquidity for buyers."
        ]
    },
    'SELL': {
        'SPEED': [
            "🔻 <b>Speed:</b> Price is dropping quickly, showing strong seller pressure.",
            "🔻 <b>Momentum:</b> Fast downward move indicates eager sellers.",
            "🔻 <b>Velocity:</b> Sellers are aggressive, pushing price down rapidly.",
            "🔻 <b>Plunge:</b> Sudden downward spike suggests a breakdown wave."
        ],
        'PREMIUM': [
            "📈 <b>Premium:</b> Price has rallied too fast and is likely to pullback (Overbought).",
            "📈 <b>Extension:</b> Price is over-extended to the upside, due for a correction.",
            "📈 <b>Peak:</b> Market is overbought, expecting a sharp reversal.",
            "📈 <b>Expensive:</b> Price is technically overvalued here, inviting sellers."
        ],
        'STRENGTH': [
            "💪 <b>Strength:</b> Sellers are dominating the market right now.",
            "💪 <b>Power:</b> Bears are currently in control of the price action.",
            "💪 <b>Force:</b> Strong selling pressure is evident on the tape.",
            "💪 <b>Dominance:</b> Sellers are overwhelming buyers at this level."
        ],
        'WHY_NOT_BUY': [
            "⛔ <b>Why NOT Buy?</b> Buyers failed to break higher (Resistance Holding).",
            "⛔ <b>Risk of Buying:</b> Upside momentum is weak; buying here is catching a falling knife.",
            "⛔ <b>Caution:</b> Attempts to go higher were rejected instantly.",
            "⛔ <b>Trap:</b> Bulls are trapped; buying here provides liquidity for sellers."
        ]
    },
    'CONTEXT': {
        'TRENDING': [
            "✅ <b>Trend Alignment:</b> The overall market trend supports this trade.",
            "✅ <b>With the Flow:</b> We are trading in the direction of the dominant trend.",
            "✅ <b>Momentum:</b> The broader trend is pushing in our favor.",
            "✅ <b>Path of Least Resistance:</b> The trend suggests this direction is easiest."
        ],
        'RANGING': [
            "↔️ <b>Market Structure:</b> Price is bouncing within a range, perfect for quick scalps.",
            "↔️ <b>Range Bound:</b> We are fading the edges of a consolidated market.",
            "↔️ <b>Choppy:</b> Market is sideways; taking quick profits at range boundaries.",
            "↔️ <b>Ping Pong:</b> Price is oscillating; good for short-term mean reversion."
        ]
    }
}
