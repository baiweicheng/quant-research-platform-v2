"""Run UI/API and an isolated worker with one local command."""

import argparse
import signal
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

from .api import create_app


def _terminate(signum, frame):
    # Uvicorn restores and re-raises the captured signal after graceful server
    # shutdown. Unwind through our worker cleanup instead of terminating the
    # parent immediately and leaving its separately sessioned worker alive.
    raise SystemExit(0)


def _open_browser_when_ready(server: uvicorn.Server, url: str):
    while not server.started:
        if server.should_exit:
            return
        time.sleep(0.1)
    try:
        if webbrowser.open(url):
            return
    except (webbrowser.Error, OSError, subprocess.SubprocessError) as error:
        print(f"Browser launch failed: {error}", file=sys.stderr)
    print(
        f"Could not open your browser automatically. Open {url} manually.",
        file=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(description="Aperture local research workspace")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="var/aperture.sqlite3")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open your default browser after startup",
    )
    args = parser.parse_args()
    previous_term = signal.signal(signal.SIGTERM, _terminate)
    worker = None
    try:
        worker = subprocess.Popen(
            [sys.executable, "-m", "aperture.worker", "--db", args.db],
            start_new_session=True,
        )
        server = uvicorn.Server(
            uvicorn.Config(create_app(args.db), host="127.0.0.1", port=args.port)
        )
        if args.open_browser:
            threading.Thread(
                target=_open_browser_when_ready,
                args=(server, f"http://127.0.0.1:{args.port}"),
                daemon=True,
            ).start()
        server.run()
    except KeyboardInterrupt:
        return
    finally:
        try:
            if worker:
                worker.terminate()
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait()
        finally:
            signal.signal(signal.SIGTERM, previous_term)


if __name__ == "__main__":
    main()
