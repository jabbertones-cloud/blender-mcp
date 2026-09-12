# We need to mock bpy before importing openclaw_blender_bridge
import sys
from unittest.mock import MagicMock
sys.modules['bpy'] = MagicMock()
sys.modules['mathutils'] = MagicMock()

import pytest
import json
import socket
import time
import queue

from blender_addon.openclaw_blender_bridge import read_single_json_request, handle_client_connection

class MockSocket:
    def __init__(self, chunks, raises_on_recv=None, raises_on_send=None):
        self.chunks = chunks
        self.raises_on_recv = raises_on_recv
        self.raises_on_send = raises_on_send
        self.timeout = None
        self.closed = False
        self.sent_data = b""

    def settimeout(self, t):
        self.timeout = t

    def recv(self, bufsize):
        if self.raises_on_recv:
            raise self.raises_on_recv
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if chunk == b"SLEEP":
            time.sleep(0.2)
            # simulate blocking socket
            return b""
        if isinstance(chunk, Exception):
            raise chunk
        return chunk

    def sendall(self, data):
        if self.raises_on_send:
            raise self.raises_on_send
        self.sent_data += data

    def close(self):
        self.closed = True

def test_valid_single_json():
    sock = MockSocket([b'{"a": 1, "id":', b' "test"}'])
    obj = read_single_json_request(sock, 1000, 1.0)
    assert obj == {"a": 1, "id": "test"}

def test_max_bytes_exceeded():
    sock = MockSocket([b'{"a": 1}'])
    with pytest.raises(ValueError, match="exceeded MAX_REQUEST_BYTES"):
        read_single_json_request(sock, 5, 1.0)

def test_timeout_exceeded():
    # simulate a socket timeout natively
    sock = MockSocket([socket.timeout("mock timeout")])
    with pytest.raises(TimeoutError, match="Read deadline exceeded"):
        read_single_json_request(sock, 1000, 0.1)

def test_multibyte_utf8_split():
    # '你好' (Ni Hao) is E4 BD A0 E5 A5 BD
    part1 = b'{"text": "\xe4\xbd\xa0'
    part2 = b'\xe5\xa5\xbd"}'
    sock = MockSocket([part1, part2])
    obj = read_single_json_request(sock, 1000, 1.0)
    assert obj == {"text": "你好"}

def test_invalid_start_byte():
    # 0xFF is not a valid UTF-8 start byte
    sock = MockSocket([b'{"a": \xff\xff}'])
    with pytest.raises(UnicodeDecodeError):
        read_single_json_request(sock, 1000, 1.0)

def test_syntactically_malformed_json_fails_at_eof():
    # Malformed JSON should not fail immediately, but wait until EOF and then fail
    sock = MockSocket([b'{bad}'])
    with pytest.raises(ValueError, match="PROTOCOL_ERROR"):
        read_single_json_request(sock, 1000, 1.0)

def test_concatenated_json():
    sock = MockSocket([b'{"a": 1}{"b": 2}'])
    with pytest.raises(ValueError, match="Concatenated or extra data is not allowed"):
        read_single_json_request(sock, 1000, 1.0)

def test_trailing_garbage():
    sock = MockSocket([b'{"a": 1} GARBAGE'])
    with pytest.raises(ValueError, match="Concatenated or extra data is not allowed"):
        read_single_json_request(sock, 1000, 1.0)

def test_incomplete_json_eof():
    sock = MockSocket([b'{"a": 1'])
    with pytest.raises(ValueError, match="PROTOCOL_ERROR"):
        read_single_json_request(sock, 1000, 1.0)

def test_client_disconnected_cleanly():
    sock = MockSocket([])
    with pytest.raises(ConnectionError, match="Client disconnected cleanly without data"):
        read_single_json_request(sock, 1000, 1.0)

def test_scalar_rejected():
    sock = MockSocket([b'"scalar"'])
    with pytest.raises(ValueError, match="Top-level request must be a JSON object"):
        read_single_json_request(sock, 1000, 1.0)

def test_array_rejected():
    sock = MockSocket([b'[1, 2, 3]'])
    with pytest.raises(ValueError, match="Top-level request must be a JSON object"):
        read_single_json_request(sock, 1000, 1.0)


# Testing handle_client_connection

def _run_handle_client(sock):
    q = queue.Queue()
    # Mocking process_command isn't easy here without patching,
    # but handle_client_connection enqueues a callback. We can just process it inline if needed.
    # To prevent it from hanging on response_event.wait, we can run the queue in a separate thread,
    # or patch the callback logic. Let's just patch response_event.wait temporarily or process queue.

    # Simple hack to unblock wait: we'll drain the queue after starting handle_client in a thread
    import threading
    t = threading.Thread(target=handle_client_connection, args=(sock, 1000, 1.0, q, 1.0))
    t.start()

    # process the callback
    try:
        cb = q.get(timeout=0.5)
        # We need to mock process_command behavior or just let it return an error from HANDLERS
        cb()
    except queue.Empty:
        pass

    t.join()


def test_handle_client_success():
    sock = MockSocket([b'{"command": "ping", "id": "test1"}'])
    _run_handle_client(sock)
    assert sock.closed
    resp = json.loads(sock.sent_data.decode("utf-8"))
    assert resp.get("id") == "test1"

def test_handle_client_parse_error():
    sock = MockSocket([b'{bad}'])
    # Malformed JSON should return PROTOCOL_ERROR
    _run_handle_client(sock)
    assert sock.closed
    resp = json.loads(sock.sent_data.decode("utf-8"))
    assert resp.get("error") == "PROTOCOL_ERROR"

def test_handle_client_timeout():
    sock = MockSocket([socket.timeout("mock timeout")])
    _run_handle_client(sock)
    assert sock.closed
    resp = json.loads(sock.sent_data.decode("utf-8"))
    assert resp.get("error") == "READ_TIMEOUT"

def test_handle_client_exec_timeout():
    sock = MockSocket([b'{"command": "ping", "id": "test_exec"}'])
    # By passing an exec_timeout of 0.05, we force the wait to fail
    q = queue.Queue()
    import threading
    t = threading.Thread(target=handle_client_connection, args=(sock, 1000, 1.0, q, 0.05))
    t.start()
    t.join() # We do not process the queue, simulating a hung execution

    assert sock.closed
    resp = json.loads(sock.sent_data.decode("utf-8"))
    assert resp.get("error") == "BLENDER_EXECUTION_TIMEOUT"
    assert resp.get("id") == "test_exec"

def test_handle_client_send_failure():
    sock = MockSocket([b'{"command": "ping"}'], raises_on_send=ConnectionResetError("Reset"))
    _run_handle_client(sock)
    assert sock.closed
