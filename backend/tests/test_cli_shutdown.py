import signal
from types import SimpleNamespace

import pytest
from aperture import __main__ as cli


@pytest.mark.parametrize("failure", ["termination", "startup"])
def test_launcher_restores_signal_and_waits_for_its_worker(monkeypatch, failure):
    previous = signal.getsignal(signal.SIGTERM)
    calls = []
    worker = SimpleNamespace(
        terminate=lambda: calls.append("terminate"),
        wait=lambda **kw: calls.append("wait"),
    )
    monkeypatch.setattr(cli.sys, "argv", ["aperture", "--db", "isolated.sqlite3"])
    monkeypatch.setattr(cli.subprocess, "Popen", lambda *a, **kw: worker)

    def app(*a):
        if failure == "startup":
            raise RuntimeError("Startup failed")
        return object()

    monkeypatch.setattr(cli, "create_app", app)

    def server(config):
        def run():
            # Model Uvicorn restoring and re-raising the handler it captured.
            handler = signal.getsignal(signal.SIGTERM)
            assert callable(handler)
            handler(signal.SIGTERM, None)

        return SimpleNamespace(run=run)

    monkeypatch.setattr(cli.uvicorn, "Server", server)
    with pytest.raises(SystemExit if failure == "termination" else RuntimeError):
        cli.main()
    assert calls == ["terminate", "wait"]
    assert signal.getsignal(signal.SIGTERM) is previous
