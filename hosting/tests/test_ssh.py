"""Смена root-пароля по SSH против настоящего SSH-сервера (paramiko) внутри теста."""
import socket
import threading

import paramiko
import pytest

from app.ssh import SshError, set_root_password


class FakeSshd(paramiko.ServerInterface):
    def __init__(self, state):
        self.state = state
        self.event = threading.Event()

    def check_auth_password(self, username, password):
        ok = username == "root" and password == self.state["password"]
        return paramiko.AUTH_SUCCESSFUL if ok else paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, channel, command):
        self.state["commands"].append(command.decode())

        def run():
            data = b""
            while not data.endswith(b"\n"):
                chunk = channel.recv(1024)
                if not chunk:
                    break
                data += chunk
            user, _, pw = data.decode().strip().partition(":")
            if command == b"chpasswd" and user == "root":
                self.state["password"] = pw
                channel.send_exit_status(0)
            else:
                channel.send_exit_status(1)
            channel.close()
        threading.Thread(target=run, daemon=True).start()
        return True


@pytest.fixture
def sshd():
    host_key = paramiko.RSAKey.generate(2048)
    state = {"password": "TempPass123", "commands": [], "key": host_key}
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    stop = threading.Event()

    def serve():
        sock.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
            except OSError:
                continue
            t = paramiko.Transport(conn)
            t.add_server_key(host_key)
            t.start_server(server=FakeSshd(state))
    threading.Thread(target=serve, daemon=True).start()
    state["port"] = sock.getsockname()[1]
    yield state
    stop.set()
    sock.close()


def test_sets_password_via_chpasswd_stdin(sshd):
    fp = set_root_password("127.0.0.1", "TempPass123", "N3w!RootPassword", port=sshd["port"], attempts=1)
    assert sshd["password"] == "N3w!RootPassword"
    # пароль передаётся через stdin, а не в командной строке
    assert sshd["commands"] == ["chpasswd"]
    assert fp.startswith("ssh-rsa ")


def test_known_hostkey_is_accepted_and_mismatch_rejected(sshd):
    fp = set_root_password("127.0.0.1", "TempPass123", "First!Passw0rd1", port=sshd["port"], attempts=1)
    set_root_password("127.0.0.1", "First!Passw0rd1", "Second!Passw0rd", port=sshd["port"], attempts=1, known_hostkey=fp)
    assert sshd["password"] == "Second!Passw0rd"
    with pytest.raises(SshError, match="Ключ SSH"):
        set_root_password("127.0.0.1", "Second!Passw0rd", "Third!Passw0rd1", port=sshd["port"], attempts=1,
                          known_hostkey="ssh-rsa AAAAdifferent")
    assert sshd["password"] == "Second!Passw0rd"


def test_wrong_temp_password_fails(sshd):
    with pytest.raises(SshError, match="временный пароль"):
        set_root_password("127.0.0.1", "wrong", "N3w!RootPassword", port=sshd["port"], attempts=2, delay=0)


def test_unreachable_host_fails_fast():
    with pytest.raises(SshError, match="Не удалось подключиться"):
        set_root_password("127.0.0.1", "x", "N3w!RootPassword", port=1, attempts=1, timeout=2)
