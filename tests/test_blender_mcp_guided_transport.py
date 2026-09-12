import json
import socket

import pytest

from server.blender_mcp_guided import send_command, TIMEOUT


class MockSocket:
    def __init__(self, family, type_, test_scenario="match"):
        self.closed = False
        self.test_scenario = test_scenario
        self.sent_data = b""
        self.request_id = None
        self.chunks_to_send = []
        self.raise_on_connect = None
        self.raise_on_sendall = None
        self.configured_timeout = None

    def settimeout(self, timeout):
        self.configured_timeout = timeout

    def connect(self, address):
        if self.raise_on_connect:
            raise self.raise_on_connect

    def sendall(self, data):
        if self.raise_on_sendall:
            raise self.raise_on_sendall
        self.sent_data += data
        payload = json.loads(data.decode("utf-8"))
        self.request_id = payload.get("id")

        if self.test_scenario == "match":
            resp = json.dumps({"id": self.request_id, "result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp]
        elif self.test_scenario == "structured_error":
            resp = json.dumps({"id": self.request_id, "error": "Server busy", "code": "SERVER_BUSY", "retryable": True}).encode("utf-8")
            self.chunks_to_send = [resp]
        elif self.test_scenario == "mismatch":
            resp = json.dumps({"id": "wrong_id", "result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp]
        elif self.test_scenario == "missing_id":
            resp = json.dumps({"result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp]
        elif self.test_scenario.startswith("split_utf8"):
            if "2byte" in self.test_scenario:
                char = "ñ"
            elif "3byte" in self.test_scenario:
                char = "こ"
            elif "4byte" in self.test_scenario:
                char = "𐍈"
            else:
                char = "こ"
            resp = json.dumps({"id": self.request_id, "result": char}, ensure_ascii=False).encode("utf-8")
            char_bytes = char.encode("utf-8")
            start_idx = resp.find(char_bytes)
            assert start_idx > 0
            offset = int(self.test_scenario.split("_")[-1])
            split_point = start_idx + offset
            self.chunks_to_send = [resp[:split_point], resp[split_point:]]
        elif self.test_scenario == "truncated_multibyte_eof":
            char = "こ"
            resp = json.dumps({"id": self.request_id, "result": char}, ensure_ascii=False).encode("utf-8")
            start_idx = resp.find(char.encode("utf-8"))
            self.chunks_to_send = [resp[:start_idx + 1]]
        elif self.test_scenario == "eof":
            self.chunks_to_send = [b""]
        elif self.test_scenario == "raise_timeout":
            self.chunks_to_send = [socket.timeout("timed out")]
        elif self.test_scenario == "raise_oserror":
            self.chunks_to_send = [OSError("os error")]
        elif self.test_scenario == "invalid_utf8":
            self.chunks_to_send = [b'{"id": "' + self.request_id.encode("utf-8") + b'", "result": \xff}']
        elif self.test_scenario == "invalid_utf8_prompt_failure":
            self.chunks_to_send = [b"\xff", Exception("AssertionError: recv called after invalid utf-8")]
        elif self.test_scenario == "invalid_continuation_prompt_failure":
            self.chunks_to_send = [b"\xe3", b"\xff", Exception("AssertionError: recv called after invalid continuation")]
        elif self.test_scenario == "malformed_json":
            self.chunks_to_send = [b'{"id": "' + self.request_id.encode("utf-8") + b'", "result": ok}']
        elif self.test_scenario == "trailing_garbage":
            resp = json.dumps({"id": self.request_id, "result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp, b" garbage"]
        elif self.test_scenario == "concatenated_json":
            resp = json.dumps({"id": self.request_id, "result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp, b'{"some": "other_json"}']
        elif self.test_scenario == "trailing_whitespace":
            resp = json.dumps({"id": self.request_id, "result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp, b"   \n  \t  "]
        elif self.test_scenario == "non_object":
            self.chunks_to_send = [b'["a", "b", "c"]']
        elif self.test_scenario == "string_response":
            self.chunks_to_send = [b'"some string"']

    def recv(self, bufsize):
        if hasattr(self, "max_recv_assert_budget") and self.max_recv_assert_budget is not None:
            assert bufsize <= self.max_recv_assert_budget + 1
        if not self.chunks_to_send:
            return b""
        chunk = self.chunks_to_send.pop(0)
        if isinstance(chunk, Exception):
            if str(chunk).startswith("AssertionError"):
                raise AssertionError(str(chunk))
            raise chunk
        return chunk

    def close(self):
        self.closed = True


def patch_socket(monkeypatch, scenario="match"):
    mock_sock = MockSocket(socket.AF_INET, socket.SOCK_STREAM, test_scenario=scenario)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: mock_sock)
    return mock_sock


def test_matching_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "match")
    assert send_command("ping") == "ok"
    assert mock_sock.closed is True


def test_structured_server_error_survives(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "structured_error")
    result = send_command("ping")
    assert result == {"error": "Server busy", "code": "SERVER_BUSY", "retryable": True}
    assert mock_sock.closed is True


def test_mismatched_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "mismatch")
    assert send_command("ping").get("code") == "RESPONSE_ID_MISMATCH"
    assert mock_sock.closed is True


def test_missing_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "missing_id")
    assert send_command("ping").get("code") == "RESPONSE_ID_MISSING"
    assert mock_sock.closed is True


def test_eof_before_valid_json(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "eof")
    assert send_command("ping").get("code") == "EMPTY_RESPONSE"
    assert mock_sock.closed is True


@pytest.mark.parametrize("scenario, expected_char", [
    ("split_utf8_2byte_1", "ñ"),
    ("split_utf8_3byte_1", "こ"),
    ("split_utf8_3byte_2", "こ"),
    ("split_utf8_4byte_1", "𐍈"),
    ("split_utf8_4byte_2", "𐍈"),
    ("split_utf8_4byte_3", "𐍈"),
])
def test_split_multibyte_utf8_response(monkeypatch, scenario, expected_char):
    mock_sock = patch_socket(monkeypatch, scenario)
    assert send_command("ping") == expected_char
    assert mock_sock.closed is True


def test_truncated_multibyte_eof(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "truncated_multibyte_eof")
    assert send_command("ping").get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_invalid_utf8_prompt_failure(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "invalid_utf8_prompt_failure")
    assert send_command("ping").get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_invalid_continuation_prompt_failure(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "invalid_continuation_prompt_failure")
    assert send_command("ping").get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_exact_cap_response_bytes(monkeypatch):
    import server.blender_mcp_guided as guided
    monkeypatch.setattr(guided, "MAX_RESPONSE_BYTES", 58)
    mock_sock = patch_socket(monkeypatch, "match")
    mock_sock.max_recv_assert_budget = 58
    assert send_command("ping") == "ok"
    assert mock_sock.closed is True


def test_exceeding_max_response_bytes(monkeypatch):
    import server.blender_mcp_guided as guided
    monkeypatch.setattr(guided, "MAX_RESPONSE_BYTES", 10)
    mock_sock = patch_socket(monkeypatch, "match")
    mock_sock.max_recv_assert_budget = 10
    assert send_command("ping").get("code") == "RESPONSE_TOO_LARGE"
    assert mock_sock.closed is True


def test_invalid_utf8_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "invalid_utf8")
    assert send_command("ping").get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_malformed_json_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "malformed_json")
    assert send_command("ping").get("code") == "INVALID_JSON_RESPONSE"
    assert mock_sock.closed is True


@pytest.mark.parametrize("scenario", ["trailing_garbage", "concatenated_json"])
def test_extra_response_data_rejected(monkeypatch, scenario):
    mock_sock = patch_socket(monkeypatch, scenario)
    assert send_command("ping").get("code") == "INVALID_JSON_RESPONSE"
    assert mock_sock.closed is True


def test_trailing_whitespace_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "trailing_whitespace")
    assert send_command("ping") == "ok"
    assert mock_sock.closed is True


@pytest.mark.parametrize("scenario", ["non_object", "string_response"])
def test_non_object_response(monkeypatch, scenario):
    mock_sock = patch_socket(monkeypatch, scenario)
    assert send_command("ping").get("code") == "INVALID_RESPONSE_SHAPE"
    assert mock_sock.closed is True


def test_connection_refused(monkeypatch):
    mock_sock = patch_socket(monkeypatch)
    mock_sock.raise_on_connect = ConnectionRefusedError("Connection refused")
    assert send_command("ping").get("code") == "CONNECTION_REFUSED"
    assert mock_sock.closed is True


def test_socket_timeout(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "raise_timeout")
    assert send_command("ping").get("code") == "TIMEOUT"
    assert mock_sock.closed is True


def test_total_deadline_reduces_each_recv_timeout(monkeypatch):
    import server.blender_mcp_guided as guided
    mock_sock = patch_socket(monkeypatch, "trailing_whitespace")
    ticks = iter([100.0, 100.0, 101.0, 102.0])
    monkeypatch.setattr(guided.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(guided, "TIMEOUT", 10.0)
    assert send_command("ping") == "ok"
    assert 0 < mock_sock.configured_timeout <= 9.0
    assert mock_sock.closed is True


def test_generic_oserror(monkeypatch):
    mock_sock = patch_socket(monkeypatch, "raise_oserror")
    assert send_command("ping").get("code") == "SOCKET_ERROR"
    assert mock_sock.closed is True


def test_sendall_failure(monkeypatch):
    mock_sock = patch_socket(monkeypatch)
    mock_sock.raise_on_sendall = BrokenPipeError("Broken pipe")
    assert send_command("ping").get("code") == "SOCKET_ERROR"
    assert mock_sock.closed is True
