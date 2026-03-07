import struct
import json
import sys
import io

class Protocol:
    # 4 byte unsigned int, big endian
    HEADER_STRUCT = struct.Struct('>I')
    HEADER_SIZE = 4

    @staticmethod
    def read(input_buffer):
        """
        Reads a length-prefixed message from a binary buffer.
        Blocks until the full message is received or EOF.
        """
        try:
            # 1. Read Length Header
            raw_len = input_buffer.read(Protocol.HEADER_SIZE)
            if not raw_len or len(raw_len) < Protocol.HEADER_SIZE:
                return None # EOF

            msg_len = Protocol.HEADER_STRUCT.unpack(raw_len)[0]

            # 2. Read Payload
            # We must ensure we read exactly msg_len bytes
            payload_buffer = io.BytesIO()
            remaining = msg_len
            while remaining > 0:
                chunk = input_buffer.read(remaining)
                if not chunk:
                    return None # EOF unexpected
                payload_buffer.write(chunk)
                remaining -= len(chunk)

            # 3. Decode JSON
            return json.loads(payload_buffer.getvalue().decode('utf-8'))

        except (struct.error, json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def write(output_buffer, data):
        """
        Writes a length-prefixed JSON message to a binary buffer.
        """
        try:
            # 1. Encode JSON
            payload = json.dumps(data).encode('utf-8')

            # 2. Create Header
            header = Protocol.HEADER_STRUCT.pack(len(payload))

            # 3. Write atomically (if possible)
            output_buffer.write(header + payload)
            output_buffer.flush()
        except OSError:
            # Pipe broken
            sys.exit(1)
