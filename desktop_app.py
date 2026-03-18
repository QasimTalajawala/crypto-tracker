"""
Crypto Tracker — Desktop Launcher
Starts Streamlit server and opens the app in your default browser.
Run:  python3 desktop_app.py
      or double-click the Crypto Tracker icon on your Desktop
"""

import subprocess
import sys
import os
import time
import webbrowser
import urllib.request

PORT = 8502
URL  = f"http://localhost:{PORT}"


def start_streamlit():
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", app_path,
         "--server.port", str(PORT),
         "--server.headless", "true",
         "--server.runOnSave", "false",
         "--browser.gatherUsageStats", "false",
         "--browser.serverAddress", "localhost"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_server(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    print("🚀 Starting Crypto Tracker…")
    proc = start_streamlit()

    print("⏳ Waiting for server…")
    if wait_for_server():
        print(f"✅ Ready — opening {URL}")
        webbrowser.open(URL)
    else:
        print("❌ Server didn't start in time.")
        proc.terminate()
        sys.exit(1)

    # Keep process alive until user closes terminal / Ctrl+C
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n👋 Shutting down…")
        proc.terminate()


if __name__ == "__main__":
    main()
