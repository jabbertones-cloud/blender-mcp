import json
import socket
import pytest

class MockSocket:
    def __init__(self, family, type_, test_scenario="match"):
        self.closed = False
        self.test_scenario = test_scenario
        self.sent_data = b""
        self.request_id = None
        self.chunks_to_send = []
        self.raise_on_connect = None

    def settimeout(self, timeout):
        pass

    def connect(self, address):
        if self.raise_on_connect:
            raise self.raise_on_connect

    def sendall(self, data):
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
        elif self.test_scenario == "split_utf8":
            base_dict = {"id": self.request_id, "result": "こんにちは"}
            resp = json.dumps(base_dict, ensure_ascii=False).encode("utf-8")
            # Split the string at an arbitrary byte to test multibyte boundary handling
            split_point = len(resp) - 4
            self.chunks_to_send = [resp[:split_point], resp[split_point:]]
        elif self.test_scenario == "eof":
            self.chunks_to_send = [b'{"id": "']
        elif self.test_scenario == "raise_timeout":
            self.chunks_to_send = [socket.timeout("timed out")]
        elif self.test_scenario == "raise_oserror":
            self.chunks_to_send = [OSError("os error")]

    def recv(self, bufsize):
        if not self.chunks_to_send:
            return b""
        chunk = self.chunks_to_send.pop(0)
        if isinstance(chunk, Exception):
            raise chunk
        return chunk

    def close(self):
        self.closed = True

def patch_socket(monkeypatch, scenario="match"):
    mock_sock = MockSocket(socket.AF_INET, socket.SOCK_STREAM, test_scenario=scenario)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: mock_sock)
    return mock_sock

from server.blender_mcp_guided import send_command

def test_matching_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="match")
    result = send_command("ping")
    assert result == "ok"
    assert mock_sock.closed is True

def test_mismatched_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="mismatch")
    result = send_command("ping")
    assert result.get("code") == "RESPONSE_ID_MISMATCH"
    assert "id mismatch" in result.get("error").lower()
    assert mock_sock.closed is True

def test_missing_response_id(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="missing_id")
    result = send_command("ping")
    assert result == "ok"
    assert mock_sock.closed is True

def test_eof_before_valid_json(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="eof")
    result = send_command("ping")
    assert result.get("code") == "EMPTY_RESPONSE"
    assert mock_sock.closed is True

def test_split_multibyte_utf8_response(monkeypatch):
    mock_sock = patch_socket(monkeypatch, scenario="split_utf8")
    result = send_command("ping")
    assert result == "こんにちは"
    assert mock_sock.closed is True

def test_exceeding_max_response_bytes(monkeypatch):
    import server.blender_mcp_guided as guided
    monkeypatch.setattr(guided, "MAX_RESPONSE_BYTES", 10)
    mock_sock = patch_socket(monkeypatch, scenario="match")
    result = send_command("ping")
    assert result.get("code") == "RESPONSE_TOO_LARGE"
    assert "exceeded 10 bytes" in result.get("error").lower()
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
