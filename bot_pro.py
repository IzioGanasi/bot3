# bot_pro.py
import numpy as np
import pandas as pd
import asyncio
import time
from typing import Optional, Callable
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from myiq.core.client import IQOption

class RiskManager:
    def __init__(self, percent_risk_per_trade: float = 0.01, max_daily_loss_percent: float = 0.05):
        """
        percent_risk_per_trade: fração do saldo para arriscar por operação (ex: 0.01 = 1%)
        max_daily_loss_percent: se perda acumulada diária exceder isso, pausa trading
        """
        self.percent_risk = percent_risk_per_trade
        self.max_daily_loss_percent = max_daily_loss_percent
        self.starting_balance = None
        self.daily_pnl = 0.0

    def set_starting_balance(self, balance: float):
        self.starting_balance = balance
        self.daily_pnl = 0.0

    def record_trade_pnl(self, pnl: float):
        self.daily_pnl += pnl

    def should_pause(self) -> bool:
        if self.starting_balance is None:
            return False
        loss_ratio = -self.daily_pnl / self.starting_balance
        return loss_ratio >= self.max_daily_loss_percent

    def position_size(self, balance: float, price_per_unit: float = 1.0) -> float:
        """
        Retorna valor monetário a ser usado na operação.
        Aqui usamos percent_risk * balance.
        """
        return max(0.01, balance * self.percent_risk)

class MomentumProBot:
    def __init__(
        self,
        iq: IQOption,
        active_id: int = 76,
        timeframe: int = 60,
        min_confidence: float = 0.72,
        vol_threshold: float = 0.0001,
        use_mlp: bool = False
    ):
        self.iq = iq
        self.active_id = active_id
        self.timeframe = timeframe

        # Model & scaler
        self.scaler = StandardScaler()
        self.model = LogisticRegression(max_iter=500) if not use_mlp else MLPClassifier(hidden_layer_sizes=(32,16), max_iter=300)
        self.use_mlp = use_mlp

        # training storage
        self.X = []
        self.y = []

        # candles
        self.current_open = None
        self.current_impulse = 0
        self.impulse_strength = 0.0
        self.last_candle = None
        self.last_candle_timestamp = None  # Track when the last candle started

        # cfg
        self.min_confidence = min_confidence
        self.vol_threshold = vol_threshold  # filtro de volatilidade (absoluto, ajuste por ativo)

        # risk
        self.risk = RiskManager(percent_risk_per_trade=0.01, max_daily_loss_percent=0.05)
        self.balance = None

        # metrics
        self.trades = []
        self.trained = False
        
        # trade status control
        self.trade_in_progress = False
        self.new_candle_started = False  # Flag to indicate when a new candle begins

    # -------------------------
    # Features / coleta
    # -------------------------
    def _extract_features(self):
        body = 0.0
        vol = 0.0
        if self.last_candle:
            body = abs(self.last_candle.close - self.last_candle.open)
            vol = abs(self.last_candle.max - self.last_candle.min)
        return [
            1 if self.current_impulse == 1 else 0,
            float(self.impulse_strength),
            float(body),
            float(vol)
        ]

    def on_candle_tick(self, data: dict):
        """Chamado a cada tick do candle em construção (dados do stream)."""
        # Check if this is a new candle by comparing timestamps
        candle_timestamp = data.get("from", 0)
        if self.last_candle_timestamp is None or candle_timestamp > self.last_candle_timestamp:
            # New candle started
            self.last_candle_timestamp = candle_timestamp
            self.new_candle_started = True
            self.current_open = data.get("open")
            self.current_impulse = 0
            self.impulse_strength = 0.0
            # print(f"[bot] Novo candle open {self.current_open}")
        elif self.current_open is None:
            # Initialize if not already done
            self.current_open = data.get("open")
            self.current_impulse = 0
            self.impulse_strength = 0.0

        price = data.get("close", self.current_open)
        diff = price - self.current_open

        if self.current_impulse == 0:
            if diff > 0:
                self.current_impulse = 1
            elif diff < 0:
                self.current_impulse = -1

        self.impulse_strength = abs(diff)

    def on_candle_close(self, candle):
        """Quando candle fecha, armazenamos exemplo para treinar."""
        if self.current_open is None:
            return

        close = candle.close
        label = 1 if close > self.current_open else 0

        feat = self._extract_features()
        self.X.append(feat)
        self.y.append(label)

        # atualiza last candle
        self.last_candle = candle

        # reseta
        self.current_open = None
        self.current_impulse = 0
        self.impulse_strength = 0.0
        self.new_candle_started = False  # Reset the flag when candle closes

        # treina se possível
        if len(self.X) >= 30:
            self._retrain()

    def _retrain(self):
        Xnp = np.array(self.X)
        # escala
        try:
            self.scaler.fit(Xnp)
            Xs = self.scaler.transform(Xnp)
        except Exception:
            Xs = Xnp

        # treina novo modelo (re-treinamento batch)
        try:
            self.model.fit(Xs, np.array(self.y))
            self.trained = True
            print(f"[bot] Modelo treinado com {len(self.X)} exemplos.")
        except Exception as e:
            print("[bot] Erro treinando:", e)

    # -------------------------
    # Entrada automática
    # -------------------------
    async def try_entry(self):
        # Check if there's already a trade in progress
        if self.trade_in_progress:
            return
            
        # Check if this is the start of a new candle
        if not self.new_candle_started:
            return
            
        if not self.trained:
            return

        # mínimo de impulso e volatilidade
        if self.current_impulse == 0:
            return

        feat = np.array(self._extract_features()).reshape(1, -1)
        try:
            feat_s = self.scaler.transform(feat)
        except Exception:
            feat_s = feat

        # probabilidades
        if hasattr(self.model, "predict_proba"):
            prob = self.model.predict_proba(feat_s)[0][1]
        else:
            # fallback to decision_function -> convert to prob (sigmoid)
            df = self.model.decision_function(feat_s)[0]
            prob = 1.0 / (1.0 + np.exp(-df))

        # volatilidade filter (usa última candle)
        last_vol = abs(self.last_candle.max - self.last_candle.min) if self.last_candle else 0.0
        if last_vol < self.vol_threshold:
            # mercado lateral, ignora
            # print("[bot] Vol baixa, pulando.")
            return

        # confiança
        if prob >= self.min_confidence:
            side = "call"
        elif prob <= (1 - self.min_confidence):
            side = "put"
        else:
            return  # sem confiança suficiente

        # checa risco / saldo
        if self.balance is None:
            # tenta pegar saldo
            try:
                bals = asyncio.get_event_loop().run_until_complete(self.iq.get_balances())
                # pega primeira conta válida
                b = next((bb for bb in bals if bb.amount > 0), bals[0])
                self.balance = b.amount
                self.risk.set_starting_balance(self.balance)
            except Exception:
                # se falhar, define um valor pequeno
                self.balance = 100.0

        # pausa se limite diário atingido
        if self.risk.should_pause():
            print("[bot] Pausado: limite de perda diária atingido.")
            return

        amount = self.risk.position_size(self.balance)
        amount = round(amount, 2)
        if amount < 0.01:
            return

        print(f"[bot] Entrada {side.upper()} prob={prob:.2f} amount={amount}")

        # Set trade in progress flag before placing order
        self.trade_in_progress = True
        
        # Reset new candle flag since we're making a trade on this candle
        self.new_candle_started = False
        
        # realiza ordem
        try:
            res = await self.iq.buy_blitz(self.active_id, side, amount, 30)
            # res expected: dict with profit/pnl
            pnl = res.get("profit", 0) or 0
            self.risk.record_trade_pnl(pnl)
            self.trades.append({
                "time": time.time(), "side": side, "prob": prob, "amount": amount, "pnl": pnl
            })
            # update balance estimate
            self.balance = max(0.0, self.balance + pnl)
            print(f"[bot] Trade result: {res.get('result')} pnl={pnl}")
        except Exception as e:
            print("[bot] Erro na ordem:", e)
        finally:
            # Reset trade in progress flag after order completion (success or failure)
            self.trade_in_progress = False

    # -------------------------
    # Start / integração com ws
    # -------------------------
    async def start(self, initial_history: int = 1000):
        # baixa histórico para warmstart
        candles = await self.iq.get_candles(self.active_id, self.timeframe, initial_history)
        # popula X,y com base no histórico (gera labels simples)
        for i in range(1, len(candles)):
            prev = candles[i-1]
            cur = candles[i]
            open_price = cur.open
            # impulsos: usamos primeiro movimento aproximado (cur.close - cur.open)
            impulse = 1 if cur.close > cur.open else -1
            impulse_strength = abs(cur.close - cur.open)
            body = abs(prev.close - prev.open)
            vol = abs(prev.max - prev.min)
            feat = [1 if impulse == 1 else 0, impulse_strength, body, vol]
            label = 1 if cur.close > cur.open else 0
            self.X.append(feat)
            self.y.append(label)
            self.last_candle = cur

        if len(self.X) >= 30:
            self._retrain()

        # define saldo inicial a partir do get_balances (se possível)
        try:
            bals = await self.iq.get_balances()
            b = next((bb for bb in bals if bb.amount > 0), bals[0])
            self.balance = b.amount
            self.risk.set_starting_balance(self.balance)
        except Exception:
            self.balance = 100.0

        # função que será chamada a cada tick do stream
        async def tick(data):
            # chamada sync
            self.on_candle_tick(data)
            # tenta entrada sem bloquear (fire-and-forget)
            await self.try_entry()

        # registra listener de candles (usa start_candles_stream da sua lib)
        await self.iq.start_candles_stream(self.active_id, self.timeframe, tick)
        print("[bot] Iniciado (pro) — aguardando candles...")

    # utilitários
    def summary(self):
        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]
        total = sum(t["pnl"] for t in self.trades)
        return {
            "trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "total_pnl": total,
            "winrate": len(wins) / len(self.trades) if self.trades else 0.0
        }
