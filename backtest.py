# backtest.py
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

def run_backtest(model, scaler, candles):
    """
    candles: lista/iterável de objetos com .open .close .min .max .from .to .volume
    model: trained sklearn model (ou None)
    scaler: fitted scaler (ou None)
    """
    trades = []
    last = None
    for i in range(1, len(candles)):
        prev = candles[i-1]
        cur = candles[i]
        impulse = 1 if cur.close > cur.open else -1
        impulse_str = abs(cur.close - cur.open)
        body = abs(prev.close - prev.open)
        vol = abs(prev.max - prev.min)
        feat = np.array([1 if impulse==1 else 0, impulse_str, body, vol]).reshape(1,-1)
        if scaler is not None:
            try:
                feat = scaler.transform(feat)
            except:
                pass

        if model is None:
            continue

        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(feat)[0][1]
        else:
            df = model.decision_function(feat)[0]
            prob = 1.0 / (1.0 + np.exp(-df))

        # threshold
        thr = 0.72
        if prob >= thr:
            side = "call"
        elif prob <= (1-thr):
            side = "put"
        else:
            continue

        # simulate profit: usar close - open como proxy (simplificado)
        pnl = (cur.close - cur.open) if side=="call" else (cur.open - cur.close)
        trades.append({"index": i, "side": side, "prob": prob, "pnl": pnl})

    # métricas
    wins = [t for t in trades if t["pnl"] > 0]
    total = sum(t["pnl"] for t in trades)
    return {"trades": len(trades), "wins": len(wins), "total_pnl": total, "winrate": len(wins)/len(trades) if trades else 0}
