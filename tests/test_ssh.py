import unittest

from auto_deployer.ssh import RemoteProbe, SSHCredentials, SSHSession


class FakeChannel:
    def __init__(self, status: int = 0) -> None:
        self._status = status

    def recv_exit_status(self) -> int:
        return self._status


class FakeStream:
    def __init__(self, data: str, status: int = 0) -> None:
        self._data = data.encode("utf-8")
        self.channel = FakeChannel(status)

    def read(self) -> bytes:
        return self._data


class FakeSSHClient:
    def __init__(self) -> None:
        self.connected = False
        self.closed = False
        self.commands: list[str] = []

    def set_missing_host_key_policy(self, policy) -> None:  # pragma: no cover - noop
        self.policy = policy

    def connect(self, **kwargs) -> None:
        self.connected = True
        self.kwargs = kwargs

    def exec_command(self, command: str, timeout=None):
        self.commands.append(command)
        return (None, FakeStream("ok"), FakeStream(""))

    def close(self) -> None:
        self.closed = True


class SSHSessionTests(unittest.TestCase):
    def test_run_command_uses_client_factory(self) -> None:
        credentials = SSHCredentials(
            host="example.com",
            username="root",
            password="secret",
        )
        credentials.auth_method = "password"
        session = SSHSession(  # type: ignore[arg-type]
            credentials, client_factory=FakeSSHClient
        )
        with session:
            result = session.run("echo test")
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout, "ok")

    def test_remote_probe_collects_fields(self) -> None:
        probe = RemoteProbe()

        class StubSession:
            def __init__(self) -> None:
                self.commands = []

            def run(self, command: str):
                self.commands.append(command)
                return type(
                    "Result",
                    (),
                    {
                        "stdout": command.upper(),
                        "stderr": "",
                        "ok": True,
                        "exit_status": 0,
                    },
                )()

        session = StubSession()
        facts = probe.collect(session)  # type: ignore[arg-type]
        self.assertEqual(facts.hostname, "HOSTNAME")
        self.assertTrue(session.commands)


if __name__ == "__main__":
    unittest.main()
