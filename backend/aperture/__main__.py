"""Run UI/API and an isolated worker with one local command."""

import argparse
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

from .api import create_app


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
    worker = subprocess.Popen(
        [sys.executable, "-m", "aperture.worker", "--db", args.db],
        start_new_session=True,
    )
    try:
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
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()


if __name__ == "__main__":
    main()
