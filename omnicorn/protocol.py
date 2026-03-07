import struct
import json
import sys
import io
import socket

class Protocol:
    # 4 byte unsigned int, big endian
    HEADER_STRUCT = struct.Struct('>I')
    HEADER_SIZE = 4

    @staticmethod
    def read(sock):
        """
        Reads a length-prefixed message from a socket.
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

            # 3. Decode JSON
            # In Phase 3, we will swap json.loads for erlpack.unpack here
            return json.loads(payload_bytes.decode('utf-8'))

        except (struct.error, json.JSONDecodeError, OSError) as e:
            sys.stderr.write(f"Protocol Error: {e}\n")
            return None

    @staticmethod
    def write(sock, data):
        """
        Writes a length-prefixed JSON message to a socket.
        """
        try:
            # 1. Encode JSON
            payload = json.dumps(data).encode('utf-8')

            # 2. Create Header
            header = Protocol.HEADER_STRUCT.pack(len(payload))

            # 3. Send
            sock.sendall(header + payload)
        except OSError:
            sys.exit(1)

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
