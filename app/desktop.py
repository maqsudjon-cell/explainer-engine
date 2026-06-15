"""desktop.py — launch explainer-engine as a native desktop window.

Starts the local Flask server in a background thread, then opens a native
OS window (via pywebview) pointing at it. Feels like a real desktop app —
no browser tab, no Electron.

    pip install pywebview
    python app/desktop.py
"""
import os
import sys
import time
import threading
import socket

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _free_port(default=7867):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", default))
        s.close()
        return default
    except OSError:
        s.close()
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.bind(("127.0.0.1", 0))
        port = s2.getsockname()[1]
        s2.close()
        return port


def _wait_for(port, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    try:
        import webview
    except ImportError:
        print("pywebview is not installed.\n"
              "  pip install pywebview\n"
              "Or just run the server and open it in a browser:\n"
              "  python app/server.py   ->   http://127.0.0.1:7867")
        return 1

    port = _free_port()
    os.environ["PORT"] = str(port)

    from app import server

    t = threading.Thread(target=server.app.run,
                         kwargs={"host": "127.0.0.1", "port": port, "threaded": True},
                         daemon=True)
    t.start()

    if not _wait_for(port):
        print("Server did not start in time.")
        return 1

    webview.create_window(
        "explainer-engine",
        f"http://127.0.0.1:{port}",
        width=1080, height=820, min_size=(720, 600),
        background_color="#060A09",
    )
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
