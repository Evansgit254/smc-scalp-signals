//+------------------------------------------------------------------+
//|                                                    Evans AI.mq5  |
//|                                   Copyright 2026, MetaQuotes Ltd.|
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property version   "1.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Inputs
input double   InpRiskPercent    = 0.5;    // Risk per trade (%) — lowered for HFT
input double   InpMaxLots        = 0.0;    // Max lots per trade (safety cap; 0 = no cap)
input double   InpATRMultiplier  = 1.5;    // ATR multiplier for SL (intraday)
input double   InpTP1R           = 1.5;    // TP1 in R (partial)
input double   InpTP2R           = 3.0;    // TP2 in R
input double   InpTP3R           = 5.0;    // TP3 in R
input bool     InpPartialTP      = true;   // Partial TP: close 1/3 at TP1, 1/3 at TP2, rest at TP3
input bool     InpUseTrailing    = true;   // Enable Trailing Stop / Break Even
input double   InpBreakEvenR     = 1.0;    // Move SL to BE when price > this R
input double   InpTrailingStopR  = 1.5;    // Trail SL by this R distance (if price > BE)
input double   InpMinQuality     = 3.0;    // Min quality score (0-10) — loosened for HFT
input double   InpThreshold      = 0.3;    // Signal threshold for entry — loosened for HFT
input int      InpMagic          = 220206; // Magic number
input int      InpMaxPositions   = 3;      // Max open positions per symbol (increased for HFT)
input int      InpATRPeriod      = 14;     // ATR period
input int      InpEMAPeriod      = 50;     // EMA period (faster for M1)
input int      InpVelocityPeriod = 10;     // Velocity lookback bars (faster)
input int      InpFastVelPeriod  = 3;      // Fast velocity lookback (faster)
input int      InpRSIPeriod      = 7;      // RSI period
input int      InpCooldownSecs   = 10;     // Cooldown between trades (seconds)
input int      InpMaxSpreadPts   = 100;    // Max spread in points (0 = no filter)

//--- Globals
CTrade         g_trade;
CPositionInfo  g_pos;
CSymbolInfo    g_sym;
int            g_handleATR;
int            g_handleEMA;
int            g_handleRSI;
double         g_point;
double         g_tickValue;
datetime       g_lastTradeTime = 0;  // Cooldown tracker

//--- Store original SL distance per ticket for TP calculations
ulong          s_ticketList[];
double         s_origSLDist[];

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
{
//---
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   if(!g_sym.Name(_Symbol))
   {
      Print("Symbol info failed");
      return(INIT_FAILED);
   }
   g_point = g_sym.Point();
   if(g_sym.Digits() == 3 || g_sym.Digits() == 5)
      g_point *= 10.0;
   g_tickValue = g_sym.TickValue();

   g_handleATR = iATR(_Symbol, _Period, InpATRPeriod);
   g_handleEMA = iMA(_Symbol, _Period, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_handleRSI = iRSI(_Symbol, _Period, InpRSIPeriod, PRICE_CLOSE);
   if(g_handleATR == INVALID_HANDLE || g_handleEMA == INVALID_HANDLE || g_handleRSI == INVALID_HANDLE)
   {
      Print("Indicator handles failed");
      return(INIT_FAILED);
   }
//---
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
//---
   if(g_handleATR != INVALID_HANDLE) IndicatorRelease(g_handleATR);
   if(g_handleEMA != INVALID_HANDLE) IndicatorRelease(g_handleEMA);
   if(g_handleRSI != INVALID_HANDLE) IndicatorRelease(g_handleRSI);
}

//+------------------------------------------------------------------+
//| Velocity alpha: normalized slope of close (linear regression)     |
//+------------------------------------------------------------------+
double VelocityAlpha(int period)
{
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, _Period, 0, period, closes) < period) return 0.0;

   double sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
   for(int i = 0; i < period; i++)
   {
      sumX  += i;
      sumY  += closes[i];
      sumXY += i * closes[i];
      sumX2 += i * i;
   }
   double n = (double)period;
   double denom = n * sumX2 - sumX * sumX;
   if(denom == 0) return 0.0;
   double slope = (n * sumXY - sumX * sumY) / denom;

   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(g_handleATR, 0, 0, 1, atr) < 1 || atr[0] == 0) return 0.0;
   return slope / atr[0];
}

//+------------------------------------------------------------------+
//| Mean reversion z-score: (close - EMA) / std(close)               |
//+------------------------------------------------------------------+
double ZScoreAlpha(int period)
{
   double closes[];
   double ema[];
   ArraySetAsSeries(closes, true);
   ArraySetAsSeries(ema, true);
   if(CopyClose(_Symbol, _Period, 0, period, closes) < period) return 0.0;
   if(CopyBuffer(g_handleEMA, 0, 0, period, ema) < period) return 0.0;

   double mean = ema[0];  // Use current EMA as mean for z-score
   double sumSq = 0;
   for(int i = 0; i < period; i++)
      sumSq += (closes[i] - mean) * (closes[i] - mean);
   double std = MathSqrt(sumSq / (double)period);
   if(std == 0) return 0.0;
   return (closes[0] - mean) / std;
}

//+------------------------------------------------------------------+
//| RSI Alpha: normalized RSI centered at 0                          |
//+------------------------------------------------------------------+
double RSIAlpha()
{
   double rsi[];
   ArraySetAsSeries(rsi, true);
   if(CopyBuffer(g_handleRSI, 0, 0, 1, rsi) < 1) return 0.0;
   // Map 0-100 to roughly -2 to +2
   return (rsi[0] - 50.0) / 20.0;
}

//+------------------------------------------------------------------+
//| Regime: 0=CHOPPY, 1=RANGING, 2=TRENDING (simplified)             |
//+------------------------------------------------------------------+
int GetRegime()
{
   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(g_handleATR, 0, 0, 50, atr) < 50) return 1;
   double atrNow = atr[0];
   double atrAvg = 0;
   for(int i = 0; i < 50; i++) atrAvg += atr[i];
   atrAvg /= 50.0;
   if(atrAvg == 0) return 1;
   double volRatio = atrNow / atrAvg;
   if(volRatio < 0.8) return 0;  // CHOPPY
   if(volRatio > 1.2) return 2;  // TRENDING
   return 1;  // RANGING
}

//+------------------------------------------------------------------+
//| Alpha combiner: weighted velocity + zscore, regime-adaptive      |
//+------------------------------------------------------------------+
double AlphaCombine(double velocity, double fastVel, double zscore, double rsi, int regime)
{
   double wVel = 0.25, wFVel = 0.25, wZ = 0.3, wRSI = 0.2;
   
   if(regime == 2) { // TRENDING
      wVel = 0.35; wFVel = 0.35; wZ = 0.1; wRSI = 0.2; 
   }
   if(regime == 0) { // CHOPPY
      wVel = 0.15; wFVel = 0.15; wZ = 0.5; wRSI = 0.2; 
   }
   
   double v  = MathMax(-4.0, MathMin(4.0, velocity));
   double fv = MathMax(-4.0, MathMin(4.0, fastVel));
   double z  = MathMax(-4.0, MathMin(4.0, zscore));
   double r  = MathMax(-4.0, MathMin(4.0, rsi));
   
   return (v * wVel) + (fv * wFVel) + (z * wZ) + (r * wRSI);
}

//+------------------------------------------------------------------+
//| Quality score 0-10: alignment + signal strength                   |
//+------------------------------------------------------------------+
double QualityScore(double velocity, double fastVel, double signal)
{
   // Use alignment of both velocity components for quality
   bool aligned = (velocity >= 0 && fastVel >= 0) || (velocity <= 0 && fastVel <= 0);
   double alignPart = aligned ? 0.6 : 0.3;
   double strPart = MathMin(1.0, MathAbs(signal) / 1.5) * 0.4;
   return (alignPart + strPart) * 10.0;
}

//+------------------------------------------------------------------+
//| Lot size from risk % and SL distance                              |
//+------------------------------------------------------------------+
double LotSize(double slDistance)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * (InpRiskPercent / 100.0);
   double tickVal = g_sym.TickValue();  // Refresh dynamically
   if(tickVal == 0) return 0.01;
   double tickSize = g_sym.TickSize();
   if(tickSize == 0) return 0.01;
   double ticksPerLot = slDistance / tickSize;
   if(ticksPerLot == 0) return 0.01;
   double lot = riskMoney / (ticksPerLot * tickVal);
   double minLot = g_sym.LotsMin();
   double maxLot = g_sym.LotsMax();
   double step   = g_sym.LotsStep();
   lot = MathFloor(lot / step) * step;
   if(InpMaxLots > 0.0)
      lot = MathMin(lot, InpMaxLots);   // Safety cap
   lot = MathMax(minLot, MathMin(maxLot, lot));
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Count open positions for this EA                                 |
//+------------------------------------------------------------------+
int CountPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(g_pos.SelectByIndex(i) && g_pos.Magic() == InpMagic && g_pos.Symbol() == _Symbol)
         n++;
   return n;
}

//--- Track which position tickets have had TP1/TP2 (for partial TP)
ulong s_tp1_done[];
ulong s_tp2_done[];

bool TicketInList(const ulong &list[], ulong ticket)
{
   for(int i = 0; i < ArraySize(list); i++)
      if(list[i] == ticket) return true;
   return false;
}
void AddTicket(ulong &list[], ulong ticket)
{
   int n = ArraySize(list);
   ArrayResize(list, n + 1);
   list[n] = ticket;
}
bool PositionExists(ulong ticket)
{
   for(int p = PositionsTotal() - 1; p >= 0; p--)
      if(g_pos.SelectByIndex(p) && g_pos.Magic() == InpMagic && g_pos.Symbol() == _Symbol && g_pos.Ticket() == ticket)
         return true;
   return false;
}
// Fix: Iterating backwards, simply remove and continue decrementing.
// The element swapped in from the end has already been checked.
void PurgeClosedTickets(ulong &list[])
{
   for(int i = ArraySize(list) - 1; i >= 0; i--)
   {
      if(!PositionExists(list[i]))
      {
         int n = ArraySize(list);
         if(n == 0) break; // Safety
         
         // If not the last element, swap with last
         if(i < n - 1) list[i] = list[n - 1];
         
         ArrayResize(list, n - 1);
      }
   }
}

//+------------------------------------------------------------------+
//| Store/Retrieve original SL distance for a ticket                  |
//+------------------------------------------------------------------+
void StoreOrigSLDist(ulong ticket, double slDist)
{
   int n = ArraySize(s_ticketList);
   ArrayResize(s_ticketList, n + 1);
   ArrayResize(s_origSLDist, n + 1);
   s_ticketList[n] = ticket;
   s_origSLDist[n] = slDist;
}

double GetOrigSLDist(ulong ticket)
{
   for(int i = 0; i < ArraySize(s_ticketList); i++)
      if(s_ticketList[i] == ticket) return s_origSLDist[i];
   return 0.0;
}

void PurgeClosedSLDist()
{
   for(int i = ArraySize(s_ticketList) - 1; i >= 0; i--)
   {
      // Check bounds first (redundant but safe)
      if(i >= ArraySize(s_ticketList)) continue;
      
      if(!PositionExists(s_ticketList[i]))
      {
         int n = ArraySize(s_ticketList);
         if(n == 0) break;

         // If not last, swap
         if(i < n - 1) {
            s_ticketList[i] = s_ticketList[n - 1];
            s_origSLDist[i] = s_origSLDist[n - 1];
         }
         
         ArrayResize(s_ticketList, n - 1);
         ArrayResize(s_origSLDist, n - 1);
      }
   }
}

//+------------------------------------------------------------------+
//| Draw/Update virtual TP lines on the chart                        |
//+------------------------------------------------------------------+
void UpdateVisualTPs(ulong ticket, double tp1, double tp2, double tp3)
{
   string p1 = "EVANS_TP1_" + (string)ticket;
   string p2 = "EVANS_TP2_" + (string)ticket;
   string p3 = "EVANS_TP3_" + (string)ticket;

   if(ObjectFind(0, p1) < 0) {
      ObjectCreate(0, p1, OBJ_HLINE, 0, 0, tp1);
      ObjectSetInteger(0, p1, OBJPROP_COLOR, clrLime);
      ObjectSetInteger(0, p1, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetString(0, p1, OBJPROP_TEXT, "TP1 (Partial)");
   }
   if(ObjectFind(0, p2) < 0) {
      ObjectCreate(0, p2, OBJ_HLINE, 0, 0, tp2);
      ObjectSetInteger(0, p2, OBJPROP_COLOR, clrGreen);
      ObjectSetInteger(0, p2, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetString(0, p2, OBJPROP_TEXT, "TP2 (Partial)");
   }
   if(ObjectFind(0, p3) < 0) {
      ObjectCreate(0, p3, OBJ_HLINE, 0, 0, tp3);
      ObjectSetInteger(0, p3, OBJPROP_COLOR, clrForestGreen);
      ObjectSetInteger(0, p3, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetString(0, p3, OBJPROP_TEXT, "TP3 (Final)");
   }
}

void CleanVisualTPs(ulong ticket)
{
   ObjectDelete(0, "EVANS_TP1_" + (string)ticket);
   ObjectDelete(0, "EVANS_TP2_" + (string)ticket);
   ObjectDelete(0, "EVANS_TP3_" + (string)ticket);
}

//+------------------------------------------------------------------+
//| Manage open positions: partial TP at TP1, TP2, TP3                 |
//+------------------------------------------------------------------+
void ManagePositions()
{
   if(!InpPartialTP) return;
   PurgeClosedTickets(s_tp1_done);
   PurgeClosedTickets(s_tp2_done);

   // Clean up any orphaned TP lines
   for(int j = ObjectsTotal(0, 0) - 1; j >= 0; j--) {
      string name = ObjectName(0, j, 0);
      if(StringFind(name, "EVANS_TP") == 0) {
         ulong ticket = (ulong)StringToInteger(StringSubstr(name, 10));
         if(!PositionExists(ticket)) ObjectDelete(0, name);
      }
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i) || g_pos.Magic() != InpMagic || g_pos.Symbol() != _Symbol) continue;
      ulong ticket = g_pos.Ticket();
      double openPrice = g_pos.PriceOpen();
      double curSL     = g_pos.StopLoss();
      double volume   = g_pos.Volume();
      long   type     = g_pos.PositionType();

      // Use stored original SL distance if available, else calculate from current SL
      double slDist = GetOrigSLDist(ticket);
      if(slDist <= 0)
      {
         slDist = (type == POSITION_TYPE_BUY) ? (openPrice - curSL) : (curSL - openPrice);
         if(slDist > 0) StoreOrigSLDist(ticket, slDist); // Store for future use
      }
      if(slDist <= 0) continue;
      double price = (type == POSITION_TYPE_BUY) ? bid : ask;

      double tp1 = (type == POSITION_TYPE_BUY) ? openPrice + slDist * InpTP1R : openPrice - slDist * InpTP1R;
      double tp2 = (type == POSITION_TYPE_BUY) ? openPrice + slDist * InpTP2R : openPrice - slDist * InpTP2R;
      double tp3 = (type == POSITION_TYPE_BUY) ? openPrice + slDist * InpTP3R : openPrice - slDist * InpTP3R;
      bool hit1 = (type == POSITION_TYPE_BUY && price >= tp1) || (type == POSITION_TYPE_SELL && price <= tp1);
      bool hit2 = (type == POSITION_TYPE_BUY && price >= tp2) || (type == POSITION_TYPE_SELL && price <= tp2);
      bool hit3 = (type == POSITION_TYPE_BUY && price >= tp3) || (type == POSITION_TYPE_SELL && price <= tp3);

      UpdateVisualTPs(ticket, tp1, tp2, tp3);

      if(hit3)
      {
         if(volume >= g_sym.LotsMin()) {
            if(g_trade.PositionClose(ticket)) CleanVisualTPs(ticket);
         }
         continue;
      }

      if(!InpPartialTP || volume < g_sym.LotsMin() * 2) continue;

      if(hit2 && !TicketInList(s_tp2_done, ticket))
      {
         double closeVol = NormalizeDouble(volume / 2.0, 2);
         if(closeVol >= g_sym.LotsMin() && closeVol < volume)
            if(g_trade.PositionClosePartial(ticket, closeVol))
               AddTicket(s_tp2_done, ticket);
      }
      else if(hit1 && !TicketInList(s_tp1_done, ticket))
      {
         double closeVol = NormalizeDouble(volume / 3.0, 2);
         if(closeVol >= g_sym.LotsMin() && closeVol < volume)
            if(g_trade.PositionClosePartial(ticket, closeVol))
               AddTicket(s_tp1_done, ticket);
      }
   }
}

//+------------------------------------------------------------------+
//| Check Trailing Stop and Break Even                                |
//+------------------------------------------------------------------+
void CheckTrailingStop()
{
   if(!InpUseTrailing) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = g_sym.Point();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i) || g_pos.Magic() != InpMagic || g_pos.Symbol() != _Symbol) continue;
      
      ulong ticket = g_pos.Ticket();
      double openPrice = g_pos.PriceOpen();
      double curSL     = g_pos.StopLoss();
      long   type     = g_pos.PositionType();

      double atr[];
      ArraySetAsSeries(atr, true);
      if(CopyBuffer(g_handleATR, 0, 0, 1, atr) < 1) continue;
      double unitR = atr[0] * InpATRMultiplier; // This is approx 1R size
      
      double newSL = curSL;
      bool modify = false;

      if(type == POSITION_TYPE_BUY)
      {
         double profitPoints = bid - openPrice;
         
         // Break Even
         if(profitPoints >= InpBreakEvenR * unitR)
         {
            if(curSL < openPrice) // Only if SL is still below entry
            {
               newSL = openPrice + 2 * point; // BE + tiny buffer
               modify = true;
            }
         }
         
         // Trailing
         if(profitPoints >= InpTrailingStopR * unitR)
         {
            double trailLevel = bid - (InpTrailingStopR * unitR);
            if(trailLevel > newSL)
            {
               newSL = trailLevel;
               modify = true;
            }
         }
      }
      else // SELL
      {
         double profitPoints = openPrice - ask;
         
         // Break Even
         if(profitPoints >= InpBreakEvenR * unitR)
         {
            if(curSL > openPrice) // Only if SL is still above entry
            {
               newSL = openPrice - 2 * point;
               modify = true;
            }
         }
         
         // Trailing
         if(profitPoints >= InpTrailingStopR * unitR)
         {
            double trailLevel = ask + (InpTrailingStopR * unitR);
            // For SELL: trailLevel should be BELOW current SL (or if no SL, set it)
            if(curSL == 0 || trailLevel < curSL)
            {
               newSL = trailLevel;
               modify = true;
            }
         }
      }

      if(modify)
      {
         g_trade.PositionModify(ticket, newSL, g_pos.TakeProfit());
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
//---
   ManagePositions();
   CheckTrailingStop();
   PurgeClosedSLDist();  // Clean up stored SL distances for closed positions
   if(CountPositions() >= InpMaxPositions) return;
   
   // Cooldown check
   if(InpCooldownSecs > 0 && TimeCurrent() - g_lastTradeTime < InpCooldownSecs) return;
   
   // Spread filter
   if(InpMaxSpreadPts > 0)
   {
      long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPts) return;
   }

   int period = MathMax(InpVelocityPeriod, InpEMAPeriod);
   period = MathMax(period, InpFastVelPeriod);
   if(Bars(_Symbol, _Period) < period + 10) return;

   double velocity = VelocityAlpha(InpVelocityPeriod);
   double fastVel  = VelocityAlpha(InpFastVelPeriod);
   double zscore   = ZScoreAlpha(InpEMAPeriod);
   double rsi      = RSIAlpha();
   int    regime   = GetRegime();
   
   double signal   = AlphaCombine(velocity, fastVel, zscore, rsi, regime);
   double quality  = QualityScore(velocity, fastVel, signal);

   if(quality < InpMinQuality) return;
   if(MathAbs(signal) < InpThreshold) return;

   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(g_handleATR, 0, 0, 1, atr) < 1 || atr[0] == 0) return;

   double price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double slDist = atr[0] * InpATRMultiplier;
   double sl, tp1, tp2, tp3;
   int    dir;

   if(signal > InpThreshold)
   {
      dir = POSITION_TYPE_BUY;
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      sl   = price - slDist;
      tp1  = price + slDist * InpTP1R;
      tp2  = price + slDist * InpTP2R;
      tp3  = price + slDist * InpTP3R;
   }
   else if(signal < -InpThreshold)
   {
      dir = POSITION_TYPE_SELL;
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      sl   = price + slDist;
      tp1  = price - slDist * InpTP1R;
      tp2  = price - slDist * InpTP2R;
      tp3  = price - slDist * InpTP3R;
   }
   else
      return;

   sl   = NormalizeDouble(sl,   (int)g_sym.Digits());
   tp1  = NormalizeDouble(tp1,  (int)g_sym.Digits());
   double lots = LotSize(slDist);
   if(lots < g_sym.LotsMin()) return;

   // When partial TP is on, open with TP=0 and manage TP1/TP2/TP3 in code
   double orderTP = InpPartialTP ? 0 : tp1;

   if(dir == POSITION_TYPE_BUY)
   {
      if(g_trade.Buy(lots, _Symbol, price, sl, orderTP, "Evans AI"))
      {
         Print("Evans AI BUY ", lots, " @ ", price, " SL ", sl, InpPartialTP ? " (partial TP)" : " TP1 ", tp1);
         g_lastTradeTime = TimeCurrent();
         // Store original SL distance for this new position
         ulong newTicket = g_trade.ResultOrder();
         if(newTicket > 0) StoreOrigSLDist(newTicket, slDist);
      }
   }
   else
   {
      if(g_trade.Sell(lots, _Symbol, price, sl, orderTP, "Evans AI"))
      {
         Print("Evans AI SELL ", lots, " @ ", price, " SL ", sl, InpPartialTP ? " (partial TP)" : " TP1 ", tp1);
         g_lastTradeTime = TimeCurrent();
         ulong newTicket = g_trade.ResultOrder();
         if(newTicket > 0) StoreOrigSLDist(newTicket, slDist);
      }
   }
}
//+------------------------------------------------------------------+
