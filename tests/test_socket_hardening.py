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
from blender_addon.openclaw_blender_bridge import handle_client_session, command_queue, MAX_REQUEST_BYTES, _accept_client

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

        # Try to handle one more connection, should fail to acquire semaphore via the real admission path
        sock = MockSocket([b'{"command": "ping"}'])

        # Calling _accept_client should reject
        admitted = _accept_client(sock, ("127.0.0.1", 12345), semaphore)
        self.assertFalse(admitted)

        # Wait a moment to ensure no thread was started that might be running
        time.sleep(0.1)

        self.assertTrue(sock.closed)
        self.assertEqual(sock.sent_data, b'{"error": "Server busy"}')

    @patch('select.select')
    def test_semaphore_release_all_paths(self, mock_select):
        mock_select.return_value = ([True], [], [])

        import os
        max_clients = int(os.environ.get("OPENCLAW_MAX_CONCURRENT_CLIENTS", "10"))

        # Test path 1: normal execution
        sem1 = threading.Semaphore(max_clients)
        sem1.acquire(blocking=False) # Simulate acquired
        sock1 = MockSocket([b'{"command": "ping", "id": "t1"}'])
        def consume():
            time.sleep(0.1)
            self._consume_queue()
        threading.Thread(target=consume, daemon=True).start()
        handle_client_session(sock1, sem1)
        # Verify semaphore was released - we can now acquire it again
        self.assertTrue(sem1.acquire(blocking=False))

        # Test path 2: parse error
        sem2 = threading.Semaphore(max_clients)
        sem2.acquire(blocking=False)
        sock2 = MockSocket([b'{"command": "ping" b'])
        handle_client_session(sock2, sem2)
        self.assertTrue(sem2.acquire(blocking=False))

        # Test path 3: serialization error (handler returns non-serializable object)
        sem3 = threading.Semaphore(max_clients)
        sem3.acquire(blocking=False)
        sock3 = MockSocket([b'{"command": "ping", "id": "t3"}'])

        # Custom consumer that pushes an un-json-serializable object to response
        def consume_bad_response():
            time.sleep(0.1)
            while not command_queue.empty():
                cb = command_queue.get()
                # Instead of hacking closure, patch process_command to return an un-json-serializable object
                with patch('blender_addon.openclaw_blender_bridge.process_command', return_value=object()):
                    cb()

        threading.Thread(target=consume_bad_response, daemon=True).start()
        handle_client_session(sock3, sem3)
        self.assertTrue(sem3.acquire(blocking=False))
        self.assertTrue(sock3.closed)

    @patch('select.select')
    def test_non_dict_json(self, mock_select):
        mock_select.return_value = ([True], [], [])

        invalid_payloads = [
            (b'[]', "Invalid request format"),
            (b'123', "Invalid request format"),
            (b'"string"', "Invalid request format"),
            (b'{"id": "test", "command": "ping"} b', "Invalid request format"), # Trailing bytes
            (b'{"command": "ping"', "Invalid request format"), # Malformed JSON at EOF
            (b'null', "Invalid request format")
        ]

        for payload, expected_err in invalid_payloads:
            sock = MockSocket([payload])
            handle_client_session(sock)
            self.assertTrue(sock.closed)
            resp = json.loads(sock.sent_data.decode("utf-8"))
            self.assertTrue("error" in resp)
            self.assertIn(expected_err, resp["error"])

            # Check ID echo for malformed JSON with ID
            if b"id" in payload:
                self.assertIn("id", resp)
                self.assertEqual(resp["id"], "test")

if __name__ == '__main__':
    unittest.main()
