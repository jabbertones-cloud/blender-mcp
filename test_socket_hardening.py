import os
import sys
import time
import json
import socket
import threading
import unittest
from unittest.mock import MagicMock, patch

# Configure env vars before importing to override defaults for testing
os.environ["OPENCLAW_MAX_REQUEST_BYTES"] = "1024"  # 1KB max for test
os.environ["OPENCLAW_CLIENT_READ_TIMEOUT"] = "0.5" # 0.5s timeout for test

# Pre-mock bpy to avoid Blender import errors
sys.modules['bpy'] = MagicMock()
sys.modules['mathutils'] = MagicMock()
sys.modules['mathutils'].Vector = MagicMock
sys.modules['mathutils'].Euler = MagicMock
sys.modules['mathutils'].Matrix = MagicMock
sys.modules['mathutils'].Color = MagicMock

# Import the bridge
from blender_addon.openclaw_blender_bridge import handle_client_session, command_queue, MAX_REQUEST_BYTES

class MockSocket:
    def __init__(self, chunks, chunk_delay=0.0):
        self.chunks = chunks
        self.chunk_delay = chunk_delay
        self.sent_data = b""
        self.closed = False
        self.blocking = True

    def setblocking(self, blocking):
        self.blocking = blocking

    def recv(self, size):
        if self.chunk_delay > 0:
            time.sleep(self.chunk_delay)
        if self.chunks:
            return self.chunks.pop(0)
        return b""

    def sendall(self, data):
        self.sent_data += data

    def close(self):
        self.closed = True

class TestSocketHardening(unittest.TestCase):
    def setUp(self):
        # Empty the command queue
        while not command_queue.empty():
            command_queue.get()

    def _consume_queue(self):
        while not command_queue.empty():
            cb = command_queue.get()
            cb()

    @patch('select.select')
    def test_valid_request(self, mock_select):
        # Mock select to always say socket is readable
        mock_select.return_value = ([True], [], [])

        req_obj = {"command": "ping", "id": "test_1"}
        req_bytes = json.dumps(req_obj).encode("utf-8")
        sock = MockSocket([req_bytes])

        # Start a thread to consume the queue after a short delay
        def consume():
            time.sleep(0.1)
            self._consume_queue()
        threading.Thread(target=consume, daemon=True).start()

        handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertEqual(resp.get("id"), "test_1")
        self.assertTrue("result" in resp)

    @patch('select.select')
    def test_oversized_request(self, mock_select):
        mock_select.return_value = ([True], [], [])

        # Create a request larger than MAX_REQUEST_BYTES
        req_bytes = b" " * (MAX_REQUEST_BYTES + 1)
        sock = MockSocket([req_bytes])

        handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertTrue("error" in resp)
        self.assertIn("exceeds maximum allowed size", resp["error"])

    @patch('select.select')
    def test_slowloris_timeout(self, mock_select):
        # Simulate blocking socket where select blocks until timeout
        # by making select sleep then return empty
        def mock_select_side_effect(rlist, wlist, xlist, timeout):
            time.sleep(timeout)
            return ([], [], [])
        mock_select.side_effect = mock_select_side_effect

        sock = MockSocket([])
        start_time = time.time()
        handle_client_session(sock)
        duration = time.time() - start_time

        # Should take roughly CLIENT_READ_TIMEOUT (0.5s)
        self.assertGreaterEqual(duration, 0.5)
        self.assertLess(duration, 1.0)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertTrue("error" in resp)
        self.assertIn("timeout", resp["error"].lower())

    @patch('select.select')
    def test_invalid_json_at_eof(self, mock_select):
        mock_select.return_value = ([True], [], [])

        # Send partial JSON and then EOF
        sock = MockSocket([b'{"command": "ping"'])

        handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertTrue("error" in resp)
        self.assertIn("Invalid request format", resp["error"])

    @patch('select.select')
    def test_split_multibyte_utf8(self, mock_select):
        mock_select.return_value = ([True], [], [])

        # Multibyte char '🚀' is \xf0\x9f\x9a\x80
        # Split it across two chunks
        json_str = '{"command": "ping", "emoji": "🚀"}'
        json_bytes = json_str.encode("utf-8")

        split_point = json_bytes.find(b'\xf0\x9f\x9a\x80') + 2
        chunk1 = json_bytes[:split_point]
        chunk2 = json_bytes[split_point:]

        sock = MockSocket([chunk1, chunk2])

        def consume():
            time.sleep(0.1)
            self._consume_queue()
        threading.Thread(target=consume, daemon=True).start()

        handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertIn("result", resp)
        # Verify it passed through ping (ping doesn't reflect params, but success means it parsed correctly)

    @patch('select.select')
    def test_invalid_utf8(self, mock_select):
        mock_select.return_value = ([True], [], [])

        # Send a byte sequence that is invalid UTF-8 but not near EOF
        # e.g., \xff in the middle of a string
        bad_bytes = b'{"command": "ping", "data": "bad\xffbytes"}'

        sock = MockSocket([bad_bytes])

        handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertTrue("error" in resp)
        self.assertIn("Invalid UTF-8 sequence", resp["error"])

if __name__ == '__main__':
    unittest.main()
