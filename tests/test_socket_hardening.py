"""Socket-hardening tests for the Blender bridge session handler.

Ported from Jules PR #26 (14fedba) onto current main. Adaptations for main:

- Main reads MAX_REQUEST_BYTES / CLIENT_READ_TIMEOUT / MAX_CONCURRENT_CLIENTS
  from the environment at import time. Other test modules may import the
  bridge first, so these tests patch the module constants per-test instead of
  relying on import-time environment variables.
- Main answers "ping" on a thread-safe fast path (PR #29: liveness must not
  depend on Blender's main-thread timer), so queued-command coverage uses a
  non-ping command with a patched process_command, and the ping fast path
  gets its own test asserting the queue is never touched.
- The session callback carries the PR #27 exception guard; one test proves
  a crashing process_command returns "Bridge internal error" promptly
  instead of hanging the client.
"""

import json
import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Pre-mock bpy to avoid Blender import errors
sys.modules['bpy'] = MagicMock()
sys.modules['mathutils'] = MagicMock()
sys.modules['mathutils'].Vector = MagicMock
sys.modules['mathutils'].Euler = MagicMock
sys.modules['mathutils'].Matrix = MagicMock
sys.modules['mathutils'].Color = MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import blender_addon.openclaw_blender_bridge as obb
from blender_addon.openclaw_blender_bridge import handle_client_session, _accept_client


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
        # Drain any callbacks leaked by earlier tests.
        while not obb.command_queue.empty():
            obb.command_queue.get()
        # Small limits for the duration of each test (see module docstring).
        self._patches = [
            patch.object(obb, 'MAX_REQUEST_BYTES', 1024),
            patch.object(obb, 'CLIENT_READ_TIMEOUT', 0.5),
            patch.object(obb, 'MAX_CONCURRENT_CLIENTS', 3),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _consume_queue(self):
        while not obb.command_queue.empty():
            cb = obb.command_queue.get()
            cb()

    def _start_consumer(self):
        def consume():
            time.sleep(0.05)
            self._consume_queue()
        threading.Thread(target=consume, daemon=True).start()

    @patch('select.select')
    def test_valid_queued_request(self, mock_select):
        mock_select.return_value = ([True], [], [])

        def fake_process_command(d):
            return {"id": d.get("id", "unknown"), "result": {"ok": True}}

        req_obj = {"command": "get_scene_info", "id": "test_1"}
        sock = MockSocket([json.dumps(req_obj).encode("utf-8")])
        self._start_consumer()

        with patch.object(obb, 'process_command', side_effect=fake_process_command):
            handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertEqual(resp.get("id"), "test_1")
        self.assertEqual(resp.get("result"), {"ok": True})

    @patch('select.select')
    def test_ping_fast_path_skips_queue(self, mock_select):
        """PR #29 invariant: ping must not depend on the main-thread timer."""
        mock_select.return_value = ([True], [], [])

        sentinel = {"status": "ok", "sentinel": True}
        req_obj = {"command": "ping", "id": "p1"}
        sock = MockSocket([json.dumps(req_obj).encode("utf-8")])

        with patch.object(obb, 'handle_ping', return_value=sentinel) as mock_ping:
            handle_client_session(sock)

        mock_ping.assert_called_once()
        self.assertTrue(obb.command_queue.empty())
        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertEqual(resp, sentinel)

    @patch('select.select')
    def test_callback_exception_returns_bridge_error(self, mock_select):
        """PR #27 guard, session level: a crashing handler must not hang."""
        mock_select.return_value = ([True], [], [])

        def crashing_process_command(d):
            raise RuntimeError("Catastrophic Blender crash")

        req_obj = {"command": "get_scene_info", "id": "boom"}
        sock = MockSocket([json.dumps(req_obj).encode("utf-8")])
        self._start_consumer()

        start = time.time()
        with patch.object(obb, 'process_command', side_effect=crashing_process_command):
            handle_client_session(sock)
        duration = time.time() - start

        self.assertLess(duration, 5.0)
        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertEqual(resp.get("id"), "boom")
        self.assertIn("Bridge internal error", resp.get("error", ""))

    @patch('select.select')
    def test_oversized_request(self, mock_select):
        mock_select.return_value = ([True], [], [])

        req_bytes = b" " * (obb.MAX_REQUEST_BYTES + 1)
        sock = MockSocket([req_bytes])

        handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertIn("error", resp)
        self.assertIn("exceeds maximum allowed size", resp["error"])

    @patch('select.select')
    def test_slowloris_timeout(self, mock_select):
        def mock_select_side_effect(rlist, wlist, xlist, timeout):
            time.sleep(timeout)
            return ([], [], [])
        mock_select.side_effect = mock_select_side_effect

        sock = MockSocket([])
        start_time = time.time()
        handle_client_session(sock)
        duration = time.time() - start_time

        # Should take roughly CLIENT_READ_TIMEOUT (patched to 0.5s)
        self.assertGreaterEqual(duration, 0.5)
        self.assertLess(duration, 1.0)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertIn("error", resp)
        self.assertIn("timeout", resp["error"].lower())

    @patch('select.select')
    def test_invalid_json_at_eof(self, mock_select):
        mock_select.return_value = ([True], [], [])

        sock = MockSocket([b'{"command": "ping"'])

        handle_client_session(sock)

        self.assertTrue(sock.closed)
        resp = json.loads(sock.sent_data.decode("utf-8"))
        self.assertIn("error", resp)
        self.assertIn("Invalid request format", resp["error"])

    @patch('select.select')
    def test_split_multibyte_utf8(self, mock_select):
        mock_select.return_value = ([True], [], [])

        def fake_process_command(d):
            return {"id": d.get("id", "unknown"), "result": {"ok": True}}

        # Test splitting 2, 3, and 4 byte characters at EVERY boundary
        chars = [
            '¢',  # 2 bytes
            '€',  # 3 bytes
            '🚀',  # 4 bytes
        ]

        for char in chars:
            char_bytes = char.encode('utf-8')
            byte_len = len(char_bytes)

            for split_idx in range(1, byte_len):
                json_str = f'{{"command": "get_scene_info", "emoji": "{char}"}}'
                json_bytes = json_str.encode("utf-8")

                char_start = json_bytes.find(char_bytes)
                split_point = char_start + split_idx

                chunk1 = json_bytes[:split_point]
                chunk2 = json_bytes[split_point:]

                sock = MockSocket([chunk1, chunk2])
                self._start_consumer()

                with patch.object(obb, 'process_command', side_effect=fake_process_command):
                    handle_client_session(sock)

                self.assertTrue(sock.closed)
                resp = json.loads(sock.sent_data.decode("utf-8"))
                self.assertIn("result", resp)

    @patch('select.select')
    def test_invalid_utf8(self, mock_select):
        mock_select.return_value = ([True], [], [])

        invalid_sequences = [
            b'{"command": "ping", "data": "bad\xffbytes"}',  # Invalid byte
            b'{"command": "ping", "data": "\xc0\xaf"}',  # Overlong encoding of /
            b'{"command": "ping", "data": "\xe2\x28\xa1"}',  # Invalid continuation byte
        ]

        for bad_bytes in invalid_sequences:
            sock = MockSocket([bad_bytes])
            handle_client_session(sock)
            self.assertTrue(sock.closed)
            resp = json.loads(sock.sent_data.decode("utf-8"))
            self.assertIn("error", resp)
            self.assertIn("Invalid UTF-8 sequence", resp["error"])

    @patch('select.select')
    def test_saturation(self, mock_select):
        mock_select.return_value = ([True], [], [])

        max_clients = obb.MAX_CONCURRENT_CLIENTS
        semaphore = threading.Semaphore(max_clients)

        # Acquire all permits to simulate a saturated server
        for _ in range(max_clients):
            self.assertTrue(semaphore.acquire(blocking=False))

        sock = MockSocket([b'{"command": "ping"}'])

        admitted = _accept_client(sock, ("127.0.0.1", 12345), semaphore)
        self.assertFalse(admitted)

        # Wait a moment to ensure no thread was started that might be running
        time.sleep(0.1)

        self.assertTrue(sock.closed)
        self.assertEqual(sock.sent_data, b'{"error": "Server busy"}')

    @patch('select.select')
    def test_semaphore_release_all_paths(self, mock_select):
        mock_select.return_value = ([True], [], [])

        def fake_process_command(d):
            return {"id": d.get("id", "unknown"), "result": {"ok": True}}

        # Test path 1: normal execution
        sem1 = threading.Semaphore(1)
        sem1.acquire(blocking=False)  # Simulate acquired
        sock1 = MockSocket([b'{"command": "get_scene_info", "id": "t1"}'])
        self._start_consumer()
        with patch.object(obb, 'process_command', side_effect=fake_process_command):
            handle_client_session(sock1, sem1)
        self.assertTrue(sem1.acquire(blocking=False))

        # Test path 2: parse error
        sem2 = threading.Semaphore(1)
        sem2.acquire(blocking=False)
        sock2 = MockSocket([b'{"command": "ping" b'])
        handle_client_session(sock2, sem2)
        self.assertTrue(sem2.acquire(blocking=False))

        # Test path 3: serialization error (handler returns non-serializable object)
        sem3 = threading.Semaphore(1)
        sem3.acquire(blocking=False)
        sock3 = MockSocket([b'{"command": "get_scene_info", "id": "t3"}'])
        self._start_consumer()
        with patch.object(obb, 'process_command', return_value=object()):
            handle_client_session(sock3, sem3)
        self.assertTrue(sem3.acquire(blocking=False))
        self.assertTrue(sock3.closed)
        resp3 = json.loads(sock3.sent_data.decode("utf-8"))
        self.assertIn("Failed to serialize response", resp3["error"])

    @patch('select.select')
    def test_non_dict_json(self, mock_select):
        mock_select.return_value = ([True], [], [])

        invalid_payloads = [
            (b'[]', "Invalid request format"),
            (b'123', "Invalid request format"),
            (b'"string"', "Invalid request format"),
            (b'{"id": "test", "command": "ping"} b', "Invalid request format"),  # Trailing bytes
            (b'{"command": "ping"', "Invalid request format"),  # Malformed JSON at EOF
            (b'null', "Invalid request format")
        ]

        for payload, expected_err in invalid_payloads:
            sock = MockSocket([payload])
            handle_client_session(sock)
            self.assertTrue(sock.closed)
            resp = json.loads(sock.sent_data.decode("utf-8"))
            self.assertIn("error", resp)
            self.assertIn(expected_err, resp["error"])

            # Check ID echo for malformed JSON with ID
            if b"id" in payload:
                self.assertIn("id", resp)
                self.assertEqual(resp["id"], "test")


if __name__ == '__main__':
    unittest.main()
