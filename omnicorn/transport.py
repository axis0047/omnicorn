import abc
import asyncio
import sys


class OmniTransport(abc.ABC):
    @abc.abstractmethod
    async def connect(self):
        pass

    @abc.abstractmethod
    async def recv(self) -> dict:
        pass

    @abc.abstractmethod
    async def send(self, data: dict):
        pass

    @abc.abstractmethod
    async def close(self):
        pass


class PyUDSTransport(OmniTransport):
    """Asyncio + Erlpack Transport. Easily swappable to PyO3 Rust in the future."""

    def __init__(self, sock_path):
        self.sock_path = sock_path
        self._reader = None
        self._writer = None
        self._write_lock = asyncio.Lock()

    async def connect(self):
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(
                self.sock_path
            )
        except Exception as e:
            sys.stderr.write(f"🔥 Could not connect to UDS {self.sock_path}: {e}\n")
            sys.exit(1)

    async def recv(self) -> dict:
        from .protocol import AsyncProtocol

        return await AsyncProtocol.read(self._reader)

    async def send(self, data: dict):
        from .protocol import AsyncProtocol

        await AsyncProtocol.write(self._writer, self._write_lock, data)

    async def close(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
