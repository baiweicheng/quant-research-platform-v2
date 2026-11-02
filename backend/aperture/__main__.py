"""Run UI/API and an isolated worker with one local command."""

import argparse
import subprocess
import sys

import uvicorn

from .api import create_app


def main():
    parser = argparse.ArgumentParser(description="Aperture local research workspace")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="var/aperture.sqlite3")
    args = parser.parse_args()
    worker = subprocess.Popen(
        [sys.executable, "-m", "aperture.worker", "--db", args.db],
        start_new_session=True,
    )
    try:
        uvicorn.run(create_app(args.db), host="127.0.0.1", port=args.port)
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()


if __name__ == "__main__":
    main()
