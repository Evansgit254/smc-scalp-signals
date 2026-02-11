from core.filters.session_filter import SessionFilter

class SignalFormatter:
    """
    Formats raw strategy signals into comprehensive trading instructions.
    """
    
    @staticmethod
    def _generate_reasoning(signal: dict) -> str:
        """
        Translates raw alpha factors and regime into beginner-friendly logic.
        """
        score_details = signal.get('score_details', {})
        direction = signal.get('direction', 'N/A')
        regime = signal.get('regime', 'NORMAL')
        
        velocity = score_details.get('velocity', 0)
        zscore = score_details.get('zscore', 0)
        momentum = score_details.get('momentum', 0)
        
        reasons = []
        
        # 1. Market Context (The "Where are we?" part)
        if regime == "TRENDING":
            reasons.append("✅ <b>Trend Alignment:</b> The overall market trend supports this trade.")
        elif regime == "RANGING":
            reasons.append("↔️ <b>Market Structure:</b> Price is bouncing within a range, perfect for quick scalps.")
            
        # 2. Key Drivers (The "Why now?" part)
        if direction == "BUY":
            if velocity > 0.5: 
                reasons.append("🚀 <b>Speed:</b> Price is moving up quickly, showing strong buyer interest.")
            if zscore < -1.5: 
                reasons.append("📉 <b>Discount:</b> Price has dropped too fast and is likely to snap back up (Oversold).")
            if momentum > 0.5: 
                reasons.append("💪 <b>Strength:</b> Buyers are stepping in aggressively right now.")
        else:
            if velocity < -0.5: 
                reasons.append("🔻 <b>Speed:</b> Price is dropping quickly, showing strong seller pressure.")
            if zscore > 1.5: 
                reasons.append("📈 <b>Premium:</b> Price has rallied too fast and is likely to pullback (Overbought).")
            if momentum < -0.5: 
                reasons.append("💪 <b>Strength:</b> Sellers are dominating the market right now.")
            
        if not reasons:
            reasons.append("✅ <b>Confirmation:</b> Multiple technical factors verify this entry.")
            
        return "\n".join(reasons)

    @staticmethod
    def format_signal(signal: dict) -> str:
        """
        Convert raw signal into a comprehensive, educational trade instruction.
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
{session_emoji} {direction} SIGNAL - {symbol} {prob_header}
{'='*60}
📊 <b>TRADE SETUP</b>
• <b>Direction:</b>    {direction} ({trade_type})
• <b>Entry Price:</b>  {entry:.5f}
• <b>Stop Loss:</b>    {sl:.5f} ({sl_pips:.1f} pips risk)

🎯 <b>PROFIT TARGETS</b>
1️⃣ <b>TP1 (Secure):</b> {tp0:.5f} (+{tp0_pips:.1f} pips)
2️⃣ <b>TP2 (Growth):</b> {tp1:.5f} (+{tp1_pips:.1f} pips)
3️⃣ <b>TP3 (Runner):</b> {tp2:.5f} (+{tp2_pips:.1f} pips)

📝 <b>WHY WE ARE ENTERING THIS TRADE</b>
{reasoning}

🛡️ <b>RISK GUIDANCE</b>
• <b>Recommended Risk:</b> {risk_details.get('risk_percent', 0):.1f}% of balance
• <b>Position Size:</b>    {risk_details.get('lots', risk_details.get('lot_size', 0)):.2f} lots
• <b>Dollar Risk:</b>      ${risk_details.get('risk_cash', risk_details.get('risk_amount', 0)):.2f}
• <b>Hold Time:</b>        ~{hold_time}

⚙️ <b>Strategy Details</b>
• <b>Quality Score:</b> {quality_score:.1f}/10.0 {"🏆 Excellent" if is_high_prob else "✅ Good"}
• <b>Session:</b>       {session_name}
{'='*60}
"""
        return output
    
    @staticmethod
    def format_personalized_signal(signal: dict, client: dict) -> str:
        """
        Formats a signal specifically for a single client with their balance.
        """
        from core.filters.risk_manager import RiskManager
        
        # Calculate personalized risk for this client
        p_risk = RiskManager.calculate_lot_size(
            signal['symbol'], 
            signal['entry_price'], 
            signal['sl'],
            balance=client['account_balance'],
            risk_pct_override=client['risk_percent']
        )
        
        # Update signal with personalized risk for the basic formatter
        personal_signal = signal.copy()
        personal_signal['risk_details'] = p_risk
        
        # Add client-specific banner to the output
        base_output = SignalFormatter.format_signal(personal_signal)
        
        # Beginner-friendly personalization
        safety_check = "✅ <b>SAFE:</b> Risk is within healthy limits."
        if p_risk.get('is_high_risk'):
            safety_check = "⚠️ <b>CAUTION:</b> High risk for your account size. Consider reducing lot size."

        client_banner = f"""
👤 <b>YOUR PERSONAL PLAN</b>
💰 <b>Balance:</b> ${client['account_balance']:.2f}
📉 <b>Your Risk:</b> {p_risk.get('risk_percent', 0.0):.1f}%
🛡️ <b>Status:</b> {safety_check}
"""
        # Insert personalize banner before Risk Guidance
        parts = base_output.split("🛡️ <b>RISK GUIDANCE</b>")
        if len(parts) > 1:
            header = parts[0]
            rest = parts[1]
            return f"{header}{client_banner}\n🛡️ <b>RISK GUIDANCE</b>{rest}"
            
        return base_output

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
