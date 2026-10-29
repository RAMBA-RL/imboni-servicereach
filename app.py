"""IMBONI (ServiceReach Rwanda): start the app on your own computer.

Usage:   python app.py
It serves the ready-made web app in the 'app' folder at http://localhost:8000
and opens it in your browser. No extra packages are needed (Python 3.8+).

To rebuild the app from the data first, run:  python 03_build_app.py
The public version is deployed as a static site (see README for the link).
"""
import functools, http.server, os, socketserver, sys, threading, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(HERE, "app")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

if not os.path.exists(os.path.join(APP_DIR, "index.html")):
    sys.exit("app/index.html not found. Run: python 03_build_app.py")

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=APP_DIR)
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), handler) as server:
    url = f"http://localhost:{PORT}"
    print(f"IMBONI is running at {url}  (press Ctrl+C to stop)")
    threading.Timer(1, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
