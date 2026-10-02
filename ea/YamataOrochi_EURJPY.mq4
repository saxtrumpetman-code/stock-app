//+------------------------------------------------------------------+
//|                                       YamataOrochi_EURJPY.mq4    |
//|  八岐大蛇 EURJPY専用EA (初代八岐大蛇モード ベース)                   |
//|                                                                  |
//|  8本の首(テクニカル指標)がそれぞれ「買い/売り/中立」を投票し、        |
//|  規定数以上の首が同じ方向を向いたらエントリーする。                   |
//|   首1: EMA20 vs EMA50 (短期の向き)                                 |
//|   首2: 終値 vs EMA200 (大蛇の胴体 = 長期トレンド)                    |
//|   首3: MACD メイン vs シグナル                                      |
//|   首4: RSI 50ライン (過熱圏は中立)                                  |
//|   首5: ストキャスティクス %K vs %D (過熱圏は中立)                     |
//|   首6: ADX +DI vs -DI (ADXが弱いと中立)                             |
//|   首7: ボリンジャーバンド 終値 vs ミドル                             |
//|   首8: 一目均衡表 終値 vs 雲                                        |
//|                                                                  |
//|  売りは1時間足・買いは4時間足で判定 (自分で回す版の設定)。         |
//|  使い方: EURJPY のチャート(どの時間足でも可)にセット。             |
//|  ※スマホ版MT4ではEAは動きません。PC版MT4かVPSで稼働させてください。  |
//+------------------------------------------------------------------+
#property copyright "stock-app"
#property version   "1.10"
#property strict
#property description "八岐大蛇 EURJPY専用: 8本の首(指標)の多数決でエントリー"

//==== 基本設定 ====
input int             MagicNumber      = 880801;     // マジックナンバー
input ENUM_TIMEFRAMES SellTF           = PERIOD_H1;  // 売りシグナルの時間足
input ENUM_TIMEFRAMES BuyTF            = PERIOD_H4;  // 買いシグナルの時間足
input int             VotesRequired    = 6;          // 8本中いくつ揃えばエントリー
input bool            RequireTrendHead = true;       // 首2(EMA200)の同意を必須にする
input bool            AllowBuy         = true;       // 買いを許可
input bool            AllowSell        = true;       // 売りを許可
input bool            CloseOnOpposite  = false;      // 逆シグナルで決済
input int             Slippage         = 3;          // 許容スリッページ(ポイント)
input bool            ECNMode          = false;      // 発注後にSL/TPを設定する(ECN口座用)

//==== ロット ====
input bool            UseRiskPercent   = false;      // 残高に対する%でロット計算
input double          FixedLots        = 0.10;       // 固定ロット
input double          RiskPercent      = 1.0;        // 1トレードのリスク(%)

//==== 決済 ====
input int             ATR_Period       = 14;         // ATR期間
input double          SL_ATR_Mult      = 2.0;        // 損切り = ATR × この倍率
input double          TP_ATR_Mult      = 2.5;        // 利確 = ATR × この倍率
input double          MinSL_Pips       = 0.0;        // 損切り幅の下限(pips, 0=無効)
input double          MaxSL_Pips       = 0.0;        // 損切り幅の上限(pips, 0=無効)
input bool            UseBreakEven     = false;      // 建値ストップ
input double          BE_Trigger_Pips  = 20.0;       // 建値移動の発動(pips)
input double          BE_Offset_Pips   = 2.0;        // 建値+何pipsに置くか
input bool            UseTrailing      = false;      // トレーリングストップ
input double          Trail_Start_Pips = 30.0;       // トレール開始(pips)
input double          Trail_Dist_Pips  = 20.0;       // 現在値からの距離(pips)

//==== フィルター ====
input double          MaxSpreadPips    = 3.0;        // 最大スプレッド(pips)
input int             ServerGMTOffset  = 2;          // サーバー時間のGMT差(夏時間は3が多い)
input int             StartHourJST     = 0;          // 取引開始(日本時間, 開始=終了で24時間)
input int             EndHourJST       = 0;          // 取引終了(日本時間, 日またぎ可)
input int             FridayStopHour   = 24;         // 金曜この時刻(サーバー)以降は新規なし(24=無効)

//==== 首のパラメータ ====
input int             FastEMA          = 20;
input int             SlowEMA          = 50;
input int             TrendEMA         = 200;
input int             MACD_Fast        = 12;
input int             MACD_Slow        = 26;
input int             MACD_Signal      = 9;
input int             RSI_Period       = 14;
input double          RSI_Upper        = 70.0;
input double          RSI_Lower        = 30.0;
input int             Stoch_K          = 14;
input int             Stoch_D          = 3;
input int             Stoch_Slow       = 3;
input double          Stoch_Upper      = 80.0;
input double          Stoch_Lower      = 20.0;
input int             ADX_Period       = 14;
input double          ADX_Min          = 20.0;
input int             BB_Period        = 20;
input double          BB_Dev           = 2.0;
input int             Tenkan           = 9;
input int             Kijun            = 26;
input int             SenkouB          = 52;

datetime g_lastBarBuy  = 0;
datetime g_lastBarSell = 0;
int      g_headsBuy[8];
int      g_headsSell[8];
int      g_buyVotes  = 0;   // 買い時間足での買い票
int      g_sellVotes = 0;   // 売り時間足での売り票

//+------------------------------------------------------------------+
int OnInit()
{
   string sym = Symbol();
   StringToUpper(sym);
   if(StringFind(sym, "EURJPY") < 0)
   {
      Alert("八岐大蛇EAはEURJPY専用です。現在のチャート: ", Symbol());
      return(INIT_FAILED);
   }
   if(VotesRequired < 1 || VotesRequired > 8)
   {
      Alert("VotesRequired は 1〜8 で指定してください");
      return(INIT_PARAMETERS_INCORRECT);
   }
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   Comment("");
}

//+------------------------------------------------------------------+
void OnTick()
{
   ManagePositions();

   bool newBuyBar  = IsNewBar(BuyTF,  g_lastBarBuy);
   bool newSellBar = IsNewBar(SellTF, g_lastBarSell);
   if(!newBuyBar && !newSellBar) return;

   bool buySignal = false, sellSignal = false;
   int  b = 0, sv = 0;

   if(newBuyBar)
   {
      CountVotes(BuyTF, g_headsBuy, b, sv);
      g_buyVotes = b;
      buySignal  = AllowBuy && b >= VotesRequired && (!RequireTrendHead || g_headsBuy[1] > 0);
   }
   if(newSellBar)
   {
      CountVotes(SellTF, g_headsSell, b, sv);
      g_sellVotes = sv;
      sellSignal  = AllowSell && sv >= VotesRequired && (!RequireTrendHead || g_headsSell[1] < 0);
   }
   ShowStatus();

   if(CloseOnOpposite)
   {
      if(buySignal)  CloseByType(OP_SELL);
      if(sellSignal) CloseByType(OP_BUY);
   }

   if(CountPositions() > 0) return;
   if(!CanEnter()) return;

   if(buySignal)       OpenOrder(OP_BUY,  BuyTF);
   else if(sellSignal) OpenOrder(OP_SELL, SellTF);
}

//+------------------------------------------------------------------+
//| 8本の首の投票  (+1=買い, -1=売り, 0=中立)  確定足(shift=1)で判定   |
//+------------------------------------------------------------------+
bool IsNewBar(int tf, datetime &lastBar)
{
   datetime bar = iTime(Symbol(), tf, 0);
   if(bar == 0 || bar == lastBar) return(false);
   lastBar = bar;
   return(true);
}

void CountVotes(int tf, int &heads[], int &buyVotes, int &sellVotes)
{
   string s  = Symbol();
   int    i  = 1;
   double close = iClose(s, tf, i);

   // 首1: EMA20 vs EMA50
   double emaF = iMA(s, tf, FastEMA, 0, MODE_EMA, PRICE_CLOSE, i);
   double emaS = iMA(s, tf, SlowEMA, 0, MODE_EMA, PRICE_CLOSE, i);
   heads[0] = Sign(emaF - emaS);

   // 首2: 終値 vs EMA200
   double emaT = iMA(s, tf, TrendEMA, 0, MODE_EMA, PRICE_CLOSE, i);
   heads[1] = Sign(close - emaT);

   // 首3: MACD
   double macdM = iMACD(s, tf, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_MAIN, i);
   double macdS = iMACD(s, tf, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_SIGNAL, i);
   heads[2] = Sign(macdM - macdS);

   // 首4: RSI
   double rsi = iRSI(s, tf, RSI_Period, PRICE_CLOSE, i);
   heads[3] = 0;
   if(rsi > 50.0 && rsi < RSI_Upper) heads[3] = 1;
   if(rsi < 50.0 && rsi > RSI_Lower) heads[3] = -1;

   // 首5: ストキャスティクス
   double stK = iStochastic(s, tf, Stoch_K, Stoch_D, Stoch_Slow, MODE_SMA, 0, MODE_MAIN, i);
   double stD = iStochastic(s, tf, Stoch_K, Stoch_D, Stoch_Slow, MODE_SMA, 0, MODE_SIGNAL, i);
   heads[4] = 0;
   if(stK > stD && stK < Stoch_Upper) heads[4] = 1;
   if(stK < stD && stK > Stoch_Lower) heads[4] = -1;

   // 首6: ADX / DMI
   double adx = iADX(s, tf, ADX_Period, PRICE_CLOSE, MODE_MAIN, i);
   double pdi = iADX(s, tf, ADX_Period, PRICE_CLOSE, MODE_PLUSDI, i);
   double mdi = iADX(s, tf, ADX_Period, PRICE_CLOSE, MODE_MINUSDI, i);
   heads[5] = (adx >= ADX_Min) ? Sign(pdi - mdi) : 0;

   // 首7: ボリンジャーバンド ミドル
   double bbMid = iBands(s, tf, BB_Period, BB_Dev, 0, PRICE_CLOSE, MODE_MAIN, i);
   heads[6] = Sign(close - bbMid);

   // 首8: 一目均衡表 雲
   double spanA = iIchimoku(s, tf, Tenkan, Kijun, SenkouB, MODE_SENKOUSPANA, i);
   double spanB = iIchimoku(s, tf, Tenkan, Kijun, SenkouB, MODE_SENKOUSPANB, i);
   heads[7] = 0;
   if(close > MathMax(spanA, spanB)) heads[7] = 1;
   if(close < MathMin(spanA, spanB)) heads[7] = -1;

   buyVotes = 0;
   sellVotes = 0;
   for(int h = 0; h < 8; h++)
   {
      if(heads[h] > 0) buyVotes++;
      if(heads[h] < 0) sellVotes++;
   }
}

int Sign(double v)
{
   if(v > 0) return(1);
   if(v < 0) return(-1);
   return(0);
}

//+------------------------------------------------------------------+
double Pip()
{
   return((Digits == 3 || Digits == 5) ? Point * 10.0 : Point);
}

bool CanEnter()
{
   double spread = (Ask - Bid) / Pip();
   if(spread > MaxSpreadPips) return(false);

   if(DayOfWeek() == 5 && Hour() >= FridayStopHour) return(false);

   int jst = (Hour() - ServerGMTOffset + 9 + 48) % 24;
   if(StartHourJST == EndHourJST) return(true);
   if(StartHourJST < EndHourJST) return(jst >= StartHourJST && jst < EndHourJST);
   return(jst >= StartHourJST || jst < EndHourJST);
}

int CountPositions()
{
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;
      if(OrderType() == OP_BUY || OrderType() == OP_SELL) n++;
   }
   return(n);
}

//+------------------------------------------------------------------+
double NormalizeLots(double lots)
{
   double step = MarketInfo(Symbol(), MODE_LOTSTEP);
   double minL = MarketInfo(Symbol(), MODE_MINLOT);
   double maxL = MarketInfo(Symbol(), MODE_MAXLOT);
   if(step <= 0) step = 0.01;
   lots = MathFloor(lots / step) * step;
   if(lots < minL) lots = minL;
   if(lots > maxL) lots = maxL;
   int d = (step >= 1.0) ? 0 : (step >= 0.1 ? 1 : 2);
   return(NormalizeDouble(lots, d));
}

double CalcLots(double slDist)
{
   if(!UseRiskPercent) return(NormalizeLots(FixedLots));
   double tv = MarketInfo(Symbol(), MODE_TICKVALUE);
   double ts = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(tv <= 0 || ts <= 0 || slDist <= 0) return(NormalizeLots(FixedLots));
   double riskMoney  = AccountBalance() * RiskPercent / 100.0;
   double lossPerLot = slDist / ts * tv;
   return(NormalizeLots(riskMoney / lossPerLot));
}

//+------------------------------------------------------------------+
void OpenOrder(int type, int tf)
{
   double atr    = iATR(Symbol(), tf, ATR_Period, 1);
   double slDist = atr * SL_ATR_Mult;
   double tpDist = atr * TP_ATR_Mult;
   if(MinSL_Pips > 0) slDist = MathMax(slDist, MinSL_Pips * Pip());
   if(MaxSL_Pips > 0) slDist = MathMin(slDist, MaxSL_Pips * Pip());

   double minStop = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   slDist = MathMax(slDist, minStop);
   tpDist = MathMax(tpDist, minStop);

   double lots = CalcLots(slDist);

   RefreshRates();
   double price = (type == OP_BUY) ? Ask : Bid;
   double sl    = (type == OP_BUY) ? price - slDist : price + slDist;
   double tp    = (type == OP_BUY) ? price + tpDist : price - tpDist;
   sl = NormalizeDouble(sl, Digits);
   tp = NormalizeDouble(tp, Digits);
   color clr = (type == OP_BUY) ? clrDodgerBlue : clrTomato;

   int ticket;
   if(ECNMode)
   {
      ticket = OrderSend(Symbol(), type, lots, price, Slippage, 0, 0, "Orochi EURJPY", MagicNumber, 0, clr);
      if(ticket > 0 && OrderSelect(ticket, SELECT_BY_TICKET))
      {
         if(!OrderModify(ticket, OrderOpenPrice(), sl, tp, 0, clr))
            Print("SL/TP設定失敗 err=", GetLastError());
      }
   }
   else
   {
      ticket = OrderSend(Symbol(), type, lots, price, Slippage, sl, tp, "Orochi EURJPY", MagicNumber, 0, clr);
   }

   if(ticket < 0) Print("発注失敗 err=", GetLastError());
}

void CloseByType(int type)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;
      if(OrderType() != type) continue;
      RefreshRates();
      double price = (type == OP_BUY) ? Bid : Ask;
      if(!OrderClose(OrderTicket(), OrderLots(), price, Slippage, clrYellow))
         Print("決済失敗 err=", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| 建値ストップ & トレーリング                                         |
//+------------------------------------------------------------------+
void ManagePositions()
{
   if(!UseBreakEven && !UseTrailing) return;
   double pip = Pip();

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;

      double open  = OrderOpenPrice();
      double curSL = OrderStopLoss();
      double newSL = curSL;

      if(OrderType() == OP_BUY)
      {
         double profit = (Bid - open) / pip;
         if(UseBreakEven && profit >= BE_Trigger_Pips)
            newSL = MathMax(newSL, open + BE_Offset_Pips * pip);
         if(UseTrailing && profit >= Trail_Start_Pips)
            newSL = MathMax(newSL, Bid - Trail_Dist_Pips * pip);
         newSL = NormalizeDouble(newSL, Digits);
         if(newSL > curSL + Point && newSL < Bid)
         {
            if(!OrderModify(OrderTicket(), open, newSL, OrderTakeProfit(), 0, clrDodgerBlue))
               Print("SL更新失敗 err=", GetLastError());
         }
      }
      else if(OrderType() == OP_SELL)
      {
         double profit = (open - Ask) / pip;
         if(curSL == 0) newSL = 999999;
         if(UseBreakEven && profit >= BE_Trigger_Pips)
            newSL = MathMin(newSL, open - BE_Offset_Pips * pip);
         if(UseTrailing && profit >= Trail_Start_Pips)
            newSL = MathMin(newSL, Ask + Trail_Dist_Pips * pip);
         newSL = NormalizeDouble(newSL, Digits);
         if((curSL == 0 || newSL < curSL - Point) && newSL > Ask && newSL < 999999)
         {
            if(!OrderModify(OrderTicket(), open, newSL, OrderTakeProfit(), 0, clrTomato))
               Print("SL更新失敗 err=", GetLastError());
         }
      }
   }
}

//+------------------------------------------------------------------+
void ShowStatus()
{
   string names[8] = {"EMA20/50", "EMA200", "MACD", "RSI", "Stoch", "ADX", "BB", "Ichimoku"};
   string txt = "八岐大蛇 EURJPY  買い(" + TFName(BuyTF) + ") " + IntegerToString(g_buyVotes) +
                " / 売り(" + TFName(SellTF) + ") " + IntegerToString(g_sellVotes) +
                "  (必要 " + IntegerToString(VotesRequired) + ")\n";
   for(int h = 0; h < 8; h++)
   {
      string vb = (g_headsBuy[h]  > 0) ? "▲買" : (g_headsBuy[h]  < 0 ? "▼売" : "－");
      string vs = (g_headsSell[h] > 0) ? "▲買" : (g_headsSell[h] < 0 ? "▼売" : "－");
      txt += "首" + IntegerToString(h + 1) + " " + names[h] + ": " + TFName(BuyTF) + " " + vb + " / " + TFName(SellTF) + " " + vs + "\n";
   }
   Comment(txt);
}

string TFName(int tf)
{
   if(tf == 0) tf = Period();
   if(tf >= PERIOD_D1) return("D" + IntegerToString(tf / PERIOD_D1));
   if(tf >= PERIOD_H1) return("H" + IntegerToString(tf / PERIOD_H1));
   return("M" + IntegerToString(tf));
}
//+------------------------------------------------------------------+
