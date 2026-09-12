import json
import socket
from unittest.mock import MagicMock, patch

import pytest

import server.blender_mcp_guided as guided
from server.blender_mcp_guided import send_command

@pytest.fixture
def mock_uuid():
    with patch("server.blender_mcp_guided.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "test-id-1234"
        yield mock_uuid

@pytest.fixture
def mock_socket():
    with patch("server.blender_mcp_guided.socket.socket") as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        yield mock_sock

def test_split_multibyte_utf8(mock_socket, mock_uuid):
    payload = json.dumps({"id": "test-id-1234", "result": {"star": "🌟"}}, ensure_ascii=False).encode("utf-8")

    idx = payload.index(b'\xf0') + 1
    chunk1 = payload[:idx]
    chunk2 = payload[idx:]

    mock_socket.recv.side_effect = [chunk1, chunk2, b'']

    res = send_command("test")
    assert res == {"star": "🌟"}

def test_matching_response_id_succeeds(mock_socket, mock_uuid):
    payload = json.dumps({"id": "test-id-1234", "result": {"success": True}}).encode("utf-8")
    mock_socket.recv.side_effect = [payload, b'']

    res = send_command("test")
    assert res == {"success": True}
    mock_socket.close.assert_called_once()

def test_mismatched_response_id_fails(mock_socket, mock_uuid):
    payload = json.dumps({"id": "wrong-id-5678", "result": {"success": True}}).encode("utf-8")
    mock_socket.recv.side_effect = [payload, b'']

    res = send_command("test")
    assert res["code"] == "RESPONSE_ID_MISMATCH"
    mock_socket.close.assert_called_once()

def test_oversized_response(mock_socket, mock_uuid):
    mock_socket.recv.side_effect = [b'a' * (32 * 1024 * 1024 + 1)]

    res = send_command("test")
    assert res["code"] == "RESPONSE_TOO_LARGE"
    mock_socket.close.assert_called_once()

def test_eof_before_json(mock_socket, mock_uuid):
    mock_socket.recv.side_effect = [b'{"id": "test-', b'']

    res = send_command("test")
    assert res["code"] == "EMPTY_RESPONSE"
    mock_socket.close.assert_called_once()

def test_connection_refused(mock_socket, mock_uuid):
    mock_socket.connect.side_effect = ConnectionRefusedError()

    res = send_command("test")
    assert res["code"] == "CONNECTION_REFUSED"
    mock_socket.close.assert_called_once()

def test_timeout(mock_socket, mock_uuid):
    mock_socket.connect.side_effect = socket.timeout()

    res = send_command("test")
    assert res["code"] == "TIMEOUT"
    mock_socket.close.assert_called_once()

def test_generic_oserror(mock_socket, mock_uuid):
    mock_socket.connect.side_effect = OSError("generic error")

    res = send_command("test")
    assert res["code"] == "SOCKET_ERROR"
    mock_socket.close.assert_called_once()
