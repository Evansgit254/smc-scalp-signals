from core.filters.session_filter import SessionFilter

class SignalFormatter:
    """
    Formats raw strategy signals into comprehensive trading instructions.
    """
    
    @staticmethod
    def _generate_reasoning(signal: dict) -> str:
        """
        Translates raw alpha factors and regime into human-readable logic.
        """
        score_details = signal.get('score_details', {})
        direction = signal.get('direction', 'N/A')
        regime = signal.get('regime', 'NORMAL')
        
        velocity = score_details.get('velocity', 0)
        zscore = score_details.get('zscore', 0)
        momentum = score_details.get('momentum', 0)
        
        reasons = []
        
        # 1. Regime Context
        if regime == "TRENDING":
            reasons.append(f"Strong trend confirmed.")
        elif regime == "RANGING":
            reasons.append(f"Range-bound market conditions.")
            
        # 2. Main Factor Alignment
        if direction == "BUY":
            if velocity > 0.5: reasons.append("Positive price velocity indicates bullish strength.")
            if zscore < -1.5: reasons.append("Mean reversion setup: price is oversold relative to EMA.")
            if momentum > 0.5: reasons.append("Bullish momentum breakout detected.")
        else:
            if velocity < -0.5: reasons.append("Negative price velocity indicates bearish strength.")
            if zscore > 1.5: reasons.append("Mean reversion setup: price is overbought relative to EMA.")
            if momentum < -0.5: reasons.append("Bearish momentum breakout detected.")
            
        if not reasons:
            reasons.append("Alpha factor alignment meets institutional threshold.")
            
        return " ".join(reasons)

    @staticmethod
    def format_signal(signal: dict) -> str:
        """
        Convert raw signal dict to human-readable comprehensive instructions.
        """
        symbol = signal.get('symbol', 'UNKNOWN')
        direction = signal.get('direction', 'N/A')
        trade_type = signal.get('trade_type', 'TRADE')
        entry = signal.get('entry_price', 0)
        sl = signal.get('sl', 0)
        tp0 = signal.get('tp0', 0)
        tp1 = signal.get('tp1', 0)
        tp2 = signal.get('tp2', 0)
        confidence = signal.get('confidence', 0)
        hold_time = signal.get('expected_hold', 'Unknown')
        risk_details = signal.get('risk_details', {})
        
        # Calculate pips
        pip_divisor = 10000.0
        if "JPY" in symbol:
            pip_divisor = 100.0
        elif "GC" in symbol or "BTC" in symbol:
            pip_divisor = 10.0
            
        sl_pips = abs(entry - sl) * pip_divisor
        tp0_pips = abs(tp0 - entry) * pip_divisor
        tp1_pips = abs(tp1 - entry) * pip_divisor
        tp2_pips = abs(tp2 - entry) * pip_divisor
        
        # Session and Probability Formatting
        session_name = SessionFilter.get_session_name()
        quality_score = signal.get('quality_score', 0)
        is_high_prob = quality_score >= 8.0
        
        session_emoji = "🇬🇧" if "London Open" in session_name else "🇺🇸" if "Overlap" in session_name else "🌐"
        prob_header = " 🔥⚡ HIGH PROBABILITY ⚡🔥" if is_high_prob else ""
        reasoning = SignalFormatter._generate_reasoning(signal)
        
        # Format output
        output = f"""
{'='*60}
{session_emoji} TRADE SIGNAL - {trade_type}{prob_header}
{'='*60}
Symbol:           {symbol}
Direction:        {direction}
Timeframe:        {signal.get('timeframe', 'N/A')}
Current Session:  {session_name}
Entry Price:      {entry:.5f}
Stop Loss:        {sl:.5f} ({'-' if direction == 'BUY' else '+'}{sl_pips:.1f} pips)

📝 SIGNAL REASONING:
{reasoning}
──────────────────────────────────────────────────────────
TP0 (50% Exit):   {tp0:.5f} ({'+' if direction == 'BUY' else '-'}{tp0_pips:.1f} pips)
TP1 (30% Exit):   {tp1:.5f} ({'+' if direction == 'BUY' else '-'}{tp1_pips:.1f} pips)
TP2 (20% Exit):   {tp2:.5f} ({'+' if direction == 'BUY' else '-'}{tp2_pips:.1f} pips)
──────────────────────────────────────────────────────────
Position Size:    {risk_details.get('lots', risk_details.get('lot_size', 0)):.2f} lots
Risk Amount:      ${risk_details.get('risk_cash', risk_details.get('risk_amount', 0)):.2f}
Risk Percent:     {risk_details.get('risk_percent', 0):.1f}%
Expected Hold:    {hold_time}
Alpha Score:      {confidence:.2f} {"(STRONG)" if confidence > 1.5 else "(MODERATE)" if confidence > 1.0 else "(WEAK)"}
Quality Score:    {quality_score:.1f} {"🏆" if is_high_prob else "✅"}
{'='*60}
"""
        return output
    
    @staticmethod
    def format_signal_json(signal: dict) -> dict:
        """
        Formats signal as structured JSON for API/Webhook integration.
        """
        return {
            'symbol': signal.get('symbol'),
            'direction': signal.get('direction'),
            'type': signal.get('trade_type'),
            'timeframe': signal.get('timeframe'),
            'entry': signal.get('entry_price'),
            'stop_loss': signal.get('sl'),
            'take_profits': {
                'tp0': {'price': signal.get('tp0'), 'size_pct': 50},
                'tp1': {'price': signal.get('tp1'), 'size_pct': 30},
                'tp2': {'price': signal.get('tp2'), 'size_pct': 20}
            },
            'position_size': signal.get('risk_details', {}).get('lots', signal.get('risk_details', {}).get('lot_size', 0)),
            'risk_usd': signal.get('risk_details', {}).get('risk_cash', signal.get('risk_details', {}).get('risk_amount', 0)),
            'confidence': signal.get('confidence'),
            'expected_hold': signal.get('expected_hold')
        }
