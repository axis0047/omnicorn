import struct
import sys
import os
import erlpack

class Protocol:
    # 4 byte unsigned int, big endian
    HEADER_STRUCT = struct.Struct('>I')
    HEADER_SIZE = 4

    @staticmethod
    def read(sock):
        """
        Reads a length-prefixed ETF message from a socket.
        """
        try:
            # 1. Read Length Header
            raw_len = Protocol._recv_exact(sock, Protocol.HEADER_SIZE)
            if not raw_len:
                return None # EOF

            msg_len = Protocol.HEADER_STRUCT.unpack(raw_len)[0]

            # 2. Read Payload
            payload_bytes = Protocol._recv_exact(sock, msg_len)
            if not payload_bytes:
                return None

            # 3. Decode ETF
            return erlpack.unpack(payload_bytes)

        except struct.error as e:
            sys.stderr.write(f"Protocol Struct Error: {e}\n")
            return None
        except OSError as e:
            sys.stderr.write(f"Protocol OS Error: {e}\n")
            return None
        except Exception as e:
            sys.stderr.write(f"Protocol Decode Error: {e}\n")
            return None

    @staticmethod
    def write(sock, data):
        """
        Writes a length-prefixed ETF message to a socket.
        """
        try:
            # 1. Encode ETF (Dicts -> Maps, Bytes -> Binaries)
            payload = erlpack.pack(data)

            # 2. Create Header
            header = Protocol.HEADER_STRUCT.pack(len(payload))

            # 3. Send
            sock.sendall(header + payload)
        except OSError:
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(f"Protocol Encode Error: {e}\n")

    @staticmethod
    def _recv_exact(sock, n):
        """Helper to ensure we get exactly N bytes"""
        data = b''
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
