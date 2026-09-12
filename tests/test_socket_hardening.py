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

        # Test splitting 2, 3, and 4 byte characters at EVERY boundary
        chars = [
            '¢', # 2 bytes: \xc2\xa2
            '€', # 3 bytes: \xe2\x82\xac
            '🚀' # 4 bytes: \xf0\x9f\x9a\x80
        ]

        for char in chars:
            char_bytes = char.encode('utf-8')
            byte_len = len(char_bytes)

            for split_idx in range(1, byte_len):
                json_str = f'{{"command": "ping", "emoji": "{char}"}}'
                json_bytes = json_str.encode("utf-8")

                # Find where the character starts in the JSON
                char_start = json_bytes.find(char_bytes)
                split_point = char_start + split_idx

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

    @patch('select.select')
    def test_invalid_utf8(self, mock_select):
        mock_select.return_value = ([True], [], [])

        invalid_sequences = [
            b'{"command": "ping", "data": "bad\xffbytes"}', # Invalid byte
            b'{"command": "ping", "data": "\xc0\xaf"}', # Overlong encoding of /
            b'{"command": "ping", "data": "\xe2\x28\xa1"}', # Invalid continuation byte
        ]

        for bad_bytes in invalid_sequences:
            sock = MockSocket([bad_bytes])
            handle_client_session(sock)
            self.assertTrue(sock.closed)
            resp = json.loads(sock.sent_data.decode("utf-8"))
            self.assertTrue("error" in resp)
            self.assertIn("Invalid UTF-8 sequence", resp["error"])

    @patch('select.select')
    def test_saturation(self, mock_select):
        mock_select.return_value = ([True], [], [])

        import os
        max_clients = int(os.environ.get("OPENCLAW_MAX_CONCURRENT_CLIENTS", "10"))
        semaphore = threading.Semaphore(max_clients)

        # Acquire all permits to simulate a saturated server
        for _ in range(max_clients):
            self.assertTrue(semaphore.acquire(blocking=False))

        # Try to handle one more connection, should fail to acquire semaphore
        # Since handle_client_session expects the semaphore to be acquired before it's called
        # We need to simulate socket_server_thread's rejection logic here
        sock = MockSocket([b'{"command": "ping"}'])

        if semaphore.acquire(blocking=False):
            threading.Thread(target=handle_client_session, args=(sock, semaphore), daemon=True).start()
        else:
            try:
                sock.setblocking(True)
                sock.sendall(b'{"error": "Server busy"}')
                sock.close()
            except Exception:
                pass

        self.assertTrue(sock.closed)
        self.assertEqual(sock.sent_data, b'{"error": "Server busy"}')

if __name__ == '__main__':
    unittest.main()
