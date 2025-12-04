import json
import asyncio
import websockets
import structlog
from myiq.core.constants import IQ_WS_URL

logger = structlog.get_logger()

class WSConnection:
    def __init__(self, dispatcher):
        self.url = IQ_WS_URL
        self.dispatcher = dispatcher
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.is_connected = False
        self.on_message_hook = None
        self._recv_task: asyncio.Task | None = None

    async def connect(self):
        # connect e inicia loop de recepção
        self.ws = await websockets.connect(self.url)
        self.is_connected = True
        self._recv_task = asyncio.create_task(self._loop())
        logger.info("websocket_connected")

    async def _loop(self):
        try:
            async for msg in self.ws:
                try:
                    data = json.loads(msg)
                except Exception:
                    # ignore non-json messages
                    continue
                if self.on_message_hook:
                    try:
                        self.on_message_hook(data)
                    except Exception as e:
                        logger.error("on_message_hook_error", error=str(e))
                self.dispatcher.dispatch(data)
        except asyncio.CancelledError:
            # task was cancelled—closing gracefully
            pass
        except Exception as e:
            logger.error("ws_error", error=str(e))
        finally:
            self.is_connected = False

    async def send(self, data: dict):
        if not self.is_connected or not self.ws:
            raise ConnectionError("WS desconectado")
        await self.ws.send(json.dumps(data))

    async def close(self):
        try:
            if self._recv_task and not self._recv_task.done():
                self._recv_task.cancel()
                try:
                    await self._recv_task
                except asyncio.CancelledError:
                    pass
            if self.ws:
                await self.ws.close()
        except Exception as e:
            logger.error("ws_close_error", error=str(e))
        finally:
            self.is_connected = False
