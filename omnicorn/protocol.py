import asyncio
import struct
import sys

import erlpack


class AsyncProtocol:
    HEADER_STRUCT = struct.Struct(">I")
    HEADER_SIZE = 4

    @staticmethod
    async def read(reader: asyncio.StreamReader):
        try:
            raw_len = await reader.readexactly(AsyncProtocol.HEADER_SIZE)
            msg_len = AsyncProtocol.HEADER_STRUCT.unpack(raw_len)[0]
            payload_bytes = await reader.readexactly(msg_len)
            return erlpack.unpack(payload_bytes)
        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            sys.stderr.write(f"Protocol Decode Error: {e}\n")
            return None

    @staticmethod
    async def write(writer: asyncio.StreamWriter, write_lock: asyncio.Lock, data: dict):
        try:
            payload = erlpack.pack(data)
            header = AsyncProtocol.HEADER_STRUCT.pack(len(payload))
            async with write_lock:
                writer.write(header + payload)
                await writer.drain()
        except Exception as e:
            sys.stderr.write(f"Protocol Encode Error: {e}\n")
