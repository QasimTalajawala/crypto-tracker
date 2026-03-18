"""
Crypto Tracker — Desktop Launcher
Starts the Streamlit server in the background then opens a native macOS window.
Run:  python3 desktop_app.py
"""

import threading
import time
import subprocess
import sys
import os
import webview

PORT = 8502
URL  = f"http://localhost:{PORT}"

def _start_streamlit():
    """Run streamlit in-process so it's bundled correctly by PyInstaller."""
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", app_path,
         "--server.port", str(PORT),
         "--server.headless", "true",
         "--server.runOnSave", "false",
         "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def _wait_for_server(timeout: int = 30):
    """Poll until Streamlit is accepting connections."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.4)
    return False

def main():
    # 1. Boot Streamlit in background
    t = threading.Thread(target=_start_streamlit, daemon=True)
    t.start()

    # 2. Show a loading window while server starts
    loading_html = """
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {
          background: #0e1117;
          display: flex; align-items: center; justify-content: center;
          height: 100vh; margin: 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          color: #fafafa;
          flex-direction: column;
          gap: 20px;
        }
        .spinner {
          width: 48px; height: 48px;
          border: 4px solid #1f2937;
          border-top-color: #3b82f6;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        h2 { margin: 0; font-size: 1.4rem; font-weight: 600; }
        p  { margin: 0; color: #6b7280; font-size: 0.9rem; }
      </style>
    </head>
    <body>
      <div class="spinner"></div>
      <h2>📈 Crypto Tracker</h2>
      <p>Starting up…</p>
    </body>
    </html>
    """

    window = webview.create_window(
        "Crypto Tracker",
        html=loading_html,
        width=1280,
        height=780,
        min_size=(900, 600),
    )

    def _load_app():
        """Called after the webview event loop starts — wait then navigate."""
        if _wait_for_server(timeout=30):
            window.load_url(URL)
        else:
            window.load_html("""
            <body style="background:#0e1117;color:#ef4444;font-family:sans-serif;
                         display:flex;align-items:center;justify-content:center;height:100vh;">
              <div style="text-align:center">
                <h2>Could not start server</h2>
                <p>Please make sure Streamlit is installed:<br>
                   <code>pip3 install streamlit</code></p>
              </div>
            </body>
            """)

    webview.start(_load_app, debug=False)

if __name__ == "__main__":
    main()
