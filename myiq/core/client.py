import asyncio
import time
import structlog
from typing import List, Optional, Callable
from myiq.http.auth import IQAuth
from myiq.core.connection import WSConnection
from myiq.core.dispatcher import Dispatcher
from myiq.core.utils import get_req_id, get_sub_id
from myiq.core.constants import *
from myiq.models.base import WsRequest, WsMessageBody, Balance, Candle

logger = structlog.get_logger()

class IQOption:
    def __init__(self, email: str, password: str):
        self.auth = IQAuth(email, password)
        self.dispatcher = Dispatcher()
        self.ws = WSConnection(self.dispatcher)
        self.ssid: Optional[str] = None
        self.active_balance_id: Optional[int] = None
        self.server_time_offset = 0.0
        self.connected = False

        # hook para mensagens gerais (opcional)
        self.ws.on_message_hook = self._on_ws_message

    async def start(self):
        """Faz login e conecta WebSocket"""
        # pega ssid via http
        self.ssid = await self.auth.get_ssid()
        # connect ws
        await self.ws.connect()
        # authenticate via ws
        try:
            await self._authenticate()
            # subscreve portfolio
            await self.subscribe_portfolio()
            self.connected = True
        except Exception as e:
            logger.error("start_error", error=str(e))
            self.connected = False

    def _on_ws_message(self, msg: dict):
        # timeSync pode vir com msg como inteiro ms
        if msg.get("name") == EV_TIME_SYNC:
            # msg.msg pode vir com estrutura, aceitar int ou dict
            m = msg.get("msg", 0)
            if isinstance(m, dict):
                ts = m.get("time", 0)
            else:
                ts = m
            try:
                # ajustar server_time_offset em milissegundos
                self.server_time_offset = float(ts) - (time.time() * 1000)
            except Exception:
                pass

    def get_server_timestamp(self) -> int:
        # retorna timestamp em segundos (inteiro)
        return int((time.time() * 1000 + self.server_time_offset) / 1000)

    async def _authenticate(self):
        req_id = get_req_id()
        future = self.dispatcher.create_future(req_id)
        await self.ws.send({
            "name": OP_AUTHENTICATE,
            "request_id": req_id,
            "msg": {"ssid": self.ssid, "protocol": 3}
        })
        # espera resposta
        try:
            await asyncio.wait_for(future, timeout=8.0)
            logger.info("authenticated")
        except asyncio.TimeoutError:
            logger.error("auth_timeout")
            raise ConnectionError("Authentication timeout")

    async def subscribe_portfolio(self):
        req_ids = [get_sub_id(), get_sub_id()]
        # order-changed
        await self.ws.send({
            "name": "subscribeMessage",
            "request_id": req_ids[0],
            "msg": {"name": "portfolio.order-changed", "version": "2.0", "params": {"routingFilters": {"instrument_type": INSTRUMENT_TYPE_BLITZ}}}
        })
        # position-changed
        await self.ws.send({
            "name": "subscribeMessage",
            "request_id": req_ids[1],
            "msg": {"name": "portfolio.position-changed", "version": "3.0", "params": {"routingFilters": {"instrument_type": INSTRUMENT_TYPE_BLITZ}}}
        })
        logger.info("portfolio_subscribed")

    async def get_balances(self) -> List[Balance]:
        req_id = get_req_id()
        future = self.dispatcher.create_future(req_id)
        payload = WsRequest(
            name="sendMessage",
            request_id=req_id,
            msg=WsMessageBody(name=OP_GET_BALANCES, version="1.0", body={"types_ids": [1, 4, 2, 6]})
        )
        await self.ws.send(payload.model_dump())
        res = await future
        # res可能 contém msg -> lista de balances
        data = res.get("msg", [])
        balances = []
        for b in data:
            try:
                balances.append(Balance(**b))
            except Exception as e:
                logger.error("balance_parse_error", error=str(e), raw=b)
        return balances

    async def change_balance(self, balance_id: int):
        self.active_balance_id = int(balance_id)
        logger.info("balance_selected", id=balance_id)

    # --- CANDLES STREAMING ---
    async def start_candles_stream(self, active_id: int, duration: int, callback: Callable[[dict], None]):
        msg = {
            "name": "subscribeMessage",
            "request_id": get_sub_id(),
            "msg": {
                "name": EV_CANDLE_GENERATED,
                "params": {
                    "routingFilters": {
                        "active_id": int(active_id),
                        "size": int(duration)
                    }
                }
            }
        }
        await self.ws.send(msg)

        def on_candle(msg):
            if msg.get("name") == EV_CANDLE_GENERATED:
                data = msg.get("msg", {})
                if str(data.get("active_id")) == str(active_id) and str(data.get("size")) == str(duration):
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(data))
                    else:
                        callback(data)

        self.dispatcher.add_listener(EV_CANDLE_GENERATED, on_candle)
        logger.info("stream_started", active=active_id)

    async def get_candles(self, active_id: int, duration: int, count: int, to_time: Optional[int] = None) -> List[Candle]:
        req_id = get_req_id()
        future = self.dispatcher.create_future(req_id)
        if to_time is None:
            to_time = self.get_server_timestamp()
        body = {"active_id": active_id, "size": duration, "to": to_time, "count": count}
        payload = WsRequest(name="sendMessage", request_id=req_id, msg=WsMessageBody(name=OP_GET_CANDLES, version="2.0", body=body))
        await self.ws.send(payload.model_dump())
        res = await future
        candles = []
        for c in res.get("msg", {}).get("candles", []):
            try:
                candles.append(Candle(**c))
            except Exception as e:
                logger.error("candle_parse_error", error=str(e), raw=c)
        return candles

    # --- BLITZ TRADING ---
    async def buy_blitz(self, active_id: int, direction: str, amount: float, duration: int = 30) -> dict:
        if not self.active_balance_id:
            raise ValueError("Saldo necessario")
        req_id = get_req_id()
        server_time = self.get_server_timestamp()
        expired = server_time + duration

        body = {
            "user_balance_id": self.active_balance_id,
            "active_id": active_id,
            "option_type_id": OPTION_TYPE_BLITZ,
            "direction": direction.lower(),
            "expired": expired,
            "expiration_size": duration,
            "refund_value": 0,
            "price": float(amount),
            "value": 0,
            "profit_percent": 85
        }

        payload = WsRequest(name="sendMessage", request_id=req_id, msg=WsMessageBody(name=OP_OPEN_OPTION, version="2.0", body=body))

        uuid_future = asyncio.get_running_loop().create_future()

        def on_open(msg):
            if msg.get("name") == EV_POSITION_CHANGED:
                raw = msg.get("msg", {})
                if "raw_event" in raw:
                    evt = raw.get("raw_event", {}).get("binary_options_option_changed1", {})
                    if str(evt.get("active_id")) == str(active_id) and evt.get("result") == "opened":
                        if not uuid_future.done():
                            uuid_future.set_result(raw.get("id"))

        self.dispatcher.add_listener(EV_POSITION_CHANGED, on_open)
        logger.info("sending_order", active=active_id)
        await self.ws.send(payload.model_dump())

        try:
            order_uuid = await asyncio.wait_for(uuid_future, timeout=8.0)
            self.dispatcher.remove_listener(EV_POSITION_CHANGED, on_open)

            await self.ws.send({
                "name": "sendMessage",
                "request_id": get_req_id(),
                "msg": {
                    "name": OP_SUBSCRIBE_POSITIONS,
                    "version": "1.0",
                    "body": {"frequency": "frequent", "ids": [order_uuid]}
                }
            })

            result_future = asyncio.get_running_loop().create_future()

            def on_result(msg):
                if msg.get("name") == EV_POSITION_CHANGED:
                    raw = msg.get("msg", {})
                    if raw.get("id") == order_uuid:
                        evt = raw.get("raw_event", {}).get("binary_options_option_changed1", {})
                        status = raw.get("status")
                        res_type = evt.get("result")
                        if status == "closed" or res_type in ["win", "loose", "equal"]:
                            if not result_future.done():
                                profit = 0.0
                                if res_type == "win":
                                    profit = evt.get("win_enrolled_amount", 0) - evt.get("amount", 0)
                                elif res_type == "loose":
                                    profit = -evt.get("amount", 0)
                                result_future.set_result({
                                    "status": "completed",
                                    "result": res_type,
                                    "profit": profit,
                                    "pnl": raw.get("pnl", 0)
                                })

            self.dispatcher.add_listener(EV_POSITION_CHANGED, on_result)
            result = await asyncio.wait_for(result_future, timeout=duration + 15)
            self.dispatcher.remove_listener(EV_POSITION_CHANGED, on_result)
            return result

        except asyncio.TimeoutError:
            self.dispatcher.remove_listener(EV_POSITION_CHANGED, on_open)
            return {"status": "error", "result": "timeout", "pnl": 0}

    async def close(self):
        """Fecha corretamente o websocket e marca desconexão."""
        try:
            await self.ws.close()
        except Exception as e:
            logger.error("client_close_error", error=str(e))
        finally:
            self.connected = False
            logger.info("client_closed")
