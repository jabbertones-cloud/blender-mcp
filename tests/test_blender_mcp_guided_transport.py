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
        elif self.test_scenario == "mismatch":
            resp = json.dumps({"id": "wrong_id", "result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp]
        elif self.test_scenario == "missing_id":
            resp = json.dumps({"result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp]
        elif self.test_scenario.startswith("split_utf8"):
            # Ensure we test 2-byte, 3-byte, and 4-byte splits
            if "2byte" in self.test_scenario:
                char = "ñ"  # 2 bytes
            elif "3byte" in self.test_scenario:
                char = "こ"  # 3 bytes
            elif "4byte" in self.test_scenario:
                char = "𐍈"  # 4 bytes
            else:
                char = "こ"

            base_dict = {"id": self.request_id, "result": char}
            resp = json.dumps(base_dict, ensure_ascii=False).encode("utf-8")
            char_bytes = char.encode("utf-8")
            start_idx = resp.find(char_bytes)
            assert start_idx > 0, f"Could not find target byte for {char}"

            # split_offset can be 1, 2, or 3
            offset = int(self.test_scenario.split("_")[-1])
            split_point = start_idx + offset
            self.chunks_to_send = [resp[:split_point], resp[split_point:]]
        elif self.test_scenario == "truncated_multibyte_eof":
            # Send part of a multibyte string and then EOF
            char = "こ"
            base_dict = {"id": self.request_id, "result": char}
            resp = json.dumps(base_dict, ensure_ascii=False).encode("utf-8")
            start_idx = resp.find(char.encode("utf-8"))
            self.chunks_to_send = [resp[:start_idx + 1]]
        elif self.test_scenario == "eof":
            self.chunks_to_send = [b'']
        elif self.test_scenario == "raise_timeout":
            self.chunks_to_send = [socket.timeout("timed out")]
        elif self.test_scenario == "raise_oserror":
            self.chunks_to_send = [OSError("os error")]
        elif self.test_scenario == "invalid_utf8":
            # Send invalid utf-8 byte sequence \xff
            self.chunks_to_send = [b'{"id": "' + self.request_id.encode("utf-8") + b'", "result": \xff}']
        elif self.test_scenario == "invalid_utf8_prompt_failure":
            self.chunks_to_send = [b'\xff', Exception("AssertionError: recv called after invalid utf-8")]
        elif self.test_scenario == "invalid_continuation_prompt_failure":
            self.chunks_to_send = [b'\xe3', b'\xff', Exception("AssertionError: recv called after invalid continuation")]
        elif self.test_scenario == "malformed_json":
            self.chunks_to_send = [b'{"id": "' + self.request_id.encode("utf-8") + b'", "result": ok}']
        elif self.test_scenario == "trailing_garbage":
            resp = json.dumps({"id": self.request_id, "result": "ok"}).encode("utf-8")
            self.chunks_to_send = [resp + b' garbage']
        elif self.test_scenario == "non_object":
            self.chunks_to_send = [b'["a", "b", "c"]']
        elif self.test_scenario == "string_response":
            self.chunks_to_send = [b'"some string"']

    def recv(self, bufsize):
        if hasattr(self, "max_recv_assert_budget") and self.max_recv_assert_budget is not None:
            assert bufsize <= self.max_recv_assert_budget + 1, f"recv requested size {bufsize} exceeds budget+1 ({self.max_recv_assert_budget + 1})"

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
    mock_sock = patch_socket(monkeypatch, scenario="match")
    result = send_command("ping")
    assert result == "ok"
    assert mock_sock.closed is True
    assert mock_sock.configured_timeout == TIMEOUT


def test_mismatched_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="mismatch")
    result = send_command("ping")
    assert result.get("code") == "RESPONSE_ID_MISMATCH"
    assert "id mismatch" in result.get("error").lower()
    assert mock_sock.closed is True


def test_missing_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="missing_id")
    result = send_command("ping")
    assert result.get("code") == "RESPONSE_ID_MISSING"
    assert mock_sock.closed is True


def test_eof_before_valid_json(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="eof")
    result = send_command("ping")
    assert result.get("code") == "EMPTY_RESPONSE"
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
    mock_sock = patch_socket(monkeypatch, scenario=scenario)
    result = send_command("ping")
    assert result == expected_char
    assert mock_sock.closed is True


def test_truncated_multibyte_eof(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="truncated_multibyte_eof")
    result = send_command("ping")
    assert result.get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_invalid_utf8_prompt_failure(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="invalid_utf8_prompt_failure")
    result = send_command("ping")
    assert result.get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_invalid_continuation_prompt_failure(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="invalid_continuation_prompt_failure")
    result = send_command("ping")
    assert result.get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_exact_cap_response_bytes(monkeypatch):
    import server.blender_mcp_guided as guided
    # We want to send a valid JSON within exact bounds
    # JSON length: len('{"id": "...", "result": "ok"}')
    # id is 32 hex chars. JSON payload is 58 bytes.
    monkeypatch.setattr(guided, "MAX_RESPONSE_BYTES", 58)
    mock_sock = patch_socket(monkeypatch, scenario="match")
    mock_sock.max_recv_assert_budget = 58
    result = send_command("ping")
    assert result == "ok"
    assert mock_sock.closed is True


def test_exceeding_max_response_bytes(monkeypatch):
    import server.blender_mcp_guided as guided
    monkeypatch.setattr(guided, "MAX_RESPONSE_BYTES", 10)
    mock_sock = patch_socket(monkeypatch, scenario="match")
    mock_sock.max_recv_assert_budget = 10
    result = send_command("ping")
    assert result.get("code") == "RESPONSE_TOO_LARGE"
    assert "exceeded 10 bytes" in result.get("error").lower()
    assert mock_sock.closed is True


def test_invalid_utf8_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="invalid_utf8")
    result = send_command("ping")
    assert result.get("code") == "INVALID_UTF8_RESPONSE"
    assert mock_sock.closed is True


def test_malformed_json_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="malformed_json")
    result = send_command("ping")
    assert result.get("code") == "INVALID_JSON_RESPONSE"
    assert mock_sock.closed is True


def test_trailing_garbage_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="trailing_garbage")
    result = send_command("ping")
    assert result.get("code") == "INVALID_JSON_RESPONSE"
    assert mock_sock.closed is True


def test_non_object_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="non_object")
    result = send_command("ping")
    assert result.get("code") == "INVALID_RESPONSE_SHAPE"
    assert mock_sock.closed is True


def test_string_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="string_response")
    result = send_command("ping")
    assert result.get("code") == "INVALID_RESPONSE_SHAPE"
    assert mock_sock.closed is True


def test_connection_refused(monkeypatch):
    mock_sock = patch_socket(monkeypatch)
    mock_sock.raise_on_connect = ConnectionRefusedError("Connection refused")
    result = send_command("ping")
    assert result.get("code") == "CONNECTION_REFUSED"
    assert "cannot connect" in result.get("error").lower()
    assert mock_sock.closed is True


def test_socket_timeout(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="raise_timeout")
    result = send_command("ping")
    assert result.get("code") == "TIMEOUT"
    assert "timed out" in result.get("error").lower()
    assert mock_sock.closed is True


def test_generic_oserror(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="raise_oserror")
    result = send_command("ping")
    assert result.get("code") == "SOCKET_ERROR"
    assert "socket error" in result.get("error").lower()
    assert mock_sock.closed is True


def test_sendall_failure(monkeypatch):
    mock_sock = patch_socket(monkeypatch)
    mock_sock.raise_on_sendall = BrokenPipeError("Broken pipe")
    result = send_command("ping")
    assert result.get("code") == "SOCKET_ERROR"
    assert "socket error" in result.get("error").lower()
    assert mock_sock.closed is True
