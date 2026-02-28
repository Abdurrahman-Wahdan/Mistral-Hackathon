"""
Generic WebSocket manager for OneTeg AI services.

Uses a persistent SockJS/STOMP connection per process (auto-reconnect on
failure) to avoid reconnecting for every emitted message.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import websockets

logger = logging.getLogger(__name__)

# Keep websocket transport logs quiet in runtime logs.
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("websockets.client").setLevel(logging.WARNING)
logging.getLogger("websockets.protocol").setLevel(logging.WARNING)
logging.getLogger("websockets.asyncio").setLevel(logging.WARNING)


class WebSocketManager:
    """
    STOMP-over-WebSocket message sender with connection reuse.
    """

    def __init__(
        self,
        enabled: bool,
        url: str,
        path: str,
        stomp_destination: str,
        connection_timeout: int = 30,
        retry_attempts: int = 3,
        send_queue_maxsize: int = 10000,
    ):
        self.enabled = enabled
        self.url = url
        self.path = path
        self.stomp_destination = stomp_destination
        self.connection_timeout = connection_timeout
        self.retry_attempts = retry_attempts
        self.send_queue_maxsize = max(1, int(send_queue_maxsize))

        self._ws: Optional[Any] = None
        self._connect_lock: Optional[asyncio.Lock] = None
        self._send_lock: Optional[asyncio.Lock] = None
        self._send_queue: Optional[
            asyncio.PriorityQueue["WebSocketManager._QueueItem"]
        ] = None
        self._sender_task: Optional[asyncio.Task[None]] = None
        self._queue_seq: int = 0
        self._lock_loop_id: Optional[int] = None
        self._last_url: Optional[str] = None

        self.is_connected = False

    @dataclass
    class _QueuedMessage:
        route: str
        message: Dict[str, Any]
        result_future: Optional[asyncio.Future[bool]] = None

    @dataclass(order=True)
    class _QueueItem:
        priority: int
        sequence: int
        message: "WebSocketManager._QueuedMessage" = field(compare=False)

    def _ensure_locks(self) -> None:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
        if (
            self._lock_loop_id == loop_id
            and self._connect_lock
            and self._send_lock
            and self._send_queue is not None
        ):
            return

        if self._sender_task is not None and not self._sender_task.done():
            self._sender_task.cancel()
        self._sender_task = None
        self._ws = None
        self.is_connected = False
        self._last_url = None

        self._lock_loop_id = loop_id
        self._connect_lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()
        self._send_queue = asyncio.PriorityQueue(maxsize=self.send_queue_maxsize)
        self._queue_seq = 0

    async def _drain_queue(self) -> None:
        if self._send_queue is None:
            return
        while not self._send_queue.empty():
            try:
                item = self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            queued = item.message
            try:
                if queued.result_future is not None and not queued.result_future.done():
                    queued.result_future.set_result(False)
            finally:
                self._send_queue.task_done()

    def _ensure_sender_task(self) -> None:
        if self._sender_task is not None and not self._sender_task.done():
            return
        self._sender_task = asyncio.create_task(self._sender_loop(), name="wizard-ws-sender")

    async def _sender_loop(self) -> None:
        assert self._send_queue is not None
        while True:
            item = await self._send_queue.get()
            queued = item.message
            try:
                sent = await self._send_message_immediate(
                    route=queued.route,
                    message=queued.message,
                )
                if queued.result_future is not None and not queued.result_future.done():
                    queued.result_future.set_result(sent)
            except asyncio.CancelledError:
                if queued.result_future is not None and not queued.result_future.done():
                    queued.result_future.set_result(False)
                raise
            except Exception:
                if queued.result_future is not None and not queued.result_future.done():
                    queued.result_future.set_result(False)
            finally:
                self._send_queue.task_done()

    def _build_sockjs_url(self) -> str:
        server_id = str(random.randint(0, 999))
        session_id = str(uuid.uuid4()).replace("-", "")[:8]
        return f"{self.url}{self.path}/{server_id}/{session_id}/websocket"

    async def _open_connection(self) -> bool:
        websocket_url = self._build_sockjs_url()
        logger.debug("[WS_MANAGER] Connecting to %s", websocket_url)

        ws = await websockets.connect(
            websocket_url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        )
        timeout = max(1, int(self.connection_timeout))

        try:
            open_frame = await asyncio.wait_for(ws.recv(), timeout=timeout)
            if open_frame != "o":
                raise RuntimeError(f"Expected SockJS open frame 'o', got: {open_frame}")

            connect_frame = "CONNECT\naccept-version:1.2\nhost:/\n\n\x00"
            await ws.send(json.dumps([connect_frame]))

            connected = False
            for _ in range(5):
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                if raw == "h":
                    continue
                if raw.startswith("a"):
                    raw = raw[1:]
                frames = json.loads(raw)
                if isinstance(frames, list) and any("CONNECTED" in str(frame) for frame in frames):
                    connected = True
                    break

            if not connected:
                raise RuntimeError("STOMP CONNECTED frame not received")
        except Exception:
            try:
                await ws.close()
            except Exception:
                pass
            raise

        self._ws = ws
        self._last_url = websocket_url
        self.is_connected = True
        logger.debug("[WS_MANAGER] STOMP connected (%s)", websocket_url)
        return True

    @staticmethod
    def _ws_is_closed(ws: Any) -> bool:
        """Compatibility check across websockets client types/versions."""
        if ws is None:
            return True
        closed = getattr(ws, "closed", None)
        if isinstance(closed, bool):
            return closed
        state = getattr(ws, "state", None)
        if state is not None:
            state_text = str(state).lower()
            if "closed" in state_text:
                return True
        close_code = getattr(ws, "close_code", None)
        if close_code is not None:
            return True
        return False

    async def _reset_connection(self) -> None:
        ws = self._ws
        self._ws = None
        self.is_connected = False
        self._last_url = None
        if ws is None:
            return
        try:
            if not self._ws_is_closed(ws):
                try:
                    await ws.send(json.dumps(["DISCONNECT\n\n\x00"]))
                except Exception:
                    pass
                await ws.close()
                wait_closed = getattr(ws, "wait_closed", None)
                if callable(wait_closed):
                    try:
                        await wait_closed()
                    except Exception:
                        pass
        except Exception:
            pass

    async def connect(self) -> bool:
        """
        Ensure an active STOMP connection exists.
        """
        if not self.enabled:
            logger.info("[WS_MANAGER] WebSocket disabled in configuration")
            return False

        self._ensure_locks()
        assert self._connect_lock is not None

        async with self._connect_lock:
            if self._ws is not None and not self._ws_is_closed(self._ws):
                self.is_connected = True
                return True
            try:
                return await self._open_connection()
            except Exception as e:
                logger.error("[WS_MANAGER] Connection failed: %s", e)
                await self._reset_connection()
                return False

    async def _send_message_immediate(
        self,
        route: str,
        message: Dict[str, Any],
        _from_retry: bool = False,
    ) -> bool:
        """
        Send one payload immediately to the socket transport.
        """
        self._ensure_locks()
        assert self._send_lock is not None

        send_frame = (
            f"SEND\n"
            f"destination:{self.stomp_destination}\n"
            f"content-type:application/json\n"
            f"\n"
            f"{json.dumps(message)}\x00"
        )
        wire_payload = json.dumps([send_frame])

        try:
            # Connection establishment can be slow under reconnect/backoff.
            # Keep it outside the send lock so callers don't queue behind it.
            if not await self.connect():
                if _from_retry:
                    return False
                return await self._retry_send_message(route, message)

            async with self._send_lock:
                if self._ws is None or self._ws_is_closed(self._ws):
                    raise RuntimeError("WebSocket disconnected before send")
                await self._ws.send(wire_payload)
                logger.debug(
                    "[WS_MANAGER] Sent message route=%s destination=%s",
                    route,
                    self.stomp_destination,
                )
                return True
        except (websockets.exceptions.WebSocketException, asyncio.TimeoutError, RuntimeError) as e:
            logger.warning("[WS_MANAGER] Transport error, reconnecting: %s", e)
            await self._reset_connection()
            if _from_retry:
                return False
            return await self._retry_send_message(route, message)
        except Exception as e:
            logger.error("[WS_MANAGER] Failed to send message: %s", e, exc_info=True)
            await self._reset_connection()
            if _from_retry:
                return False
            return await self._retry_send_message(route, message)

    async def send_message(
        self,
        route: str,
        message: Dict[str, Any],
        _from_retry: bool = False,
        wait_for_delivery: bool = True,
        drop_if_queue_full: bool = False,
    ) -> bool:
        """
        Enqueue/send a JSON payload to the configured STOMP destination.

        Args:
            route: Logical route identifier (used for logging).
            message: Message payload.
            _from_retry: Internal retry marker.
            wait_for_delivery: Wait until the message is actually sent.
            drop_if_queue_full: For best-effort progress updates under backpressure.
        """
        if not self.enabled:
            return True

        self._ensure_locks()
        assert self._send_queue is not None

        self._ensure_sender_task()

        if _from_retry:
            return await self._send_message_immediate(
                route=route,
                message=message,
                _from_retry=True,
            )

        loop = asyncio.get_running_loop()
        result_future: Optional[asyncio.Future[bool]] = None
        if wait_for_delivery:
            result_future = loop.create_future()

        queued = self._QueuedMessage(
            route=route,
            message=message,
            result_future=result_future,
        )
        priority = 0 if wait_for_delivery else 1
        self._queue_seq += 1
        queue_item = self._QueueItem(
            priority=priority,
            sequence=self._queue_seq,
            message=queued,
        )

        if drop_if_queue_full and self._send_queue.full():
            logger.warning(
                "[WS_MANAGER] Dropping message route=%s due to full queue (%d)",
                route,
                self.send_queue_maxsize,
            )
            return False

        try:
            if wait_for_delivery:
                await self._send_queue.put(queue_item)
            else:
                self._send_queue.put_nowait(queue_item)
        except asyncio.QueueFull:
            logger.warning(
                "[WS_MANAGER] Queue full, message dropped route=%s (maxsize=%d)",
                route,
                self.send_queue_maxsize,
            )
            return False

        if not wait_for_delivery or result_future is None:
            return True

        return await result_future

    async def _retry_send_message(self, route: str, message: Dict[str, Any]) -> bool:
        """
        Retry send with capped exponential backoff.
        """
        for attempt in range(self.retry_attempts):
            await asyncio.sleep(min(2 ** attempt, 10))
            if await self._send_message_immediate(route, message, _from_retry=True):
                return True
            logger.warning(
                "[WS_MANAGER] Retry %s/%s failed",
                attempt + 1,
                self.retry_attempts,
            )
        logger.error("[WS_MANAGER] All retries exhausted")
        return False

    async def disconnect(self) -> None:
        """
        Close current connection (if any).
        """
        self._ensure_locks()
        assert self._connect_lock is not None
        async with self._connect_lock:
            if self._sender_task is not None:
                self._sender_task.cancel()
                try:
                    await self._sender_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                self._sender_task = None
            await self._drain_queue()
            await self._reset_connection()
