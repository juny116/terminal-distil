#!/usr/bin/env python3
"""Minimal auth'd static server for the project memory/plan HTML.

Serves ONLY *.html under SERVE_DIR (default: this dir) behind HTTP Basic Auth.
Directory listing disabled; non-.html paths 404 (so source files aren't exposed).
`/` redirects to /MEMORY.html.

Env:
  SERVE_USER  (default: juny116)
  SERVE_PASS  (required)
  SERVE_PORT  (default: 9997)
  SERVE_DIR   (default: cwd)
"""
import os, base64, secrets, urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

USER  = os.environ.get("SERVE_USER", "juny116")
PASS  = os.environ.get("SERVE_PASS")
PORT  = int(os.environ.get("SERVE_PORT", "9997"))
DIR   = os.environ.get("SERVE_DIR", os.getcwd())
REALM = "terminal-distil"

if not PASS:
    raise SystemExit("SERVE_PASS env var is required")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIR, **k)

    def _authed(self):
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return False
        try:
            u, _, p = base64.b64decode(h[6:]).decode("utf-8", "replace").partition(":")
        except Exception:
            return False
        return secrets.compare_digest(u, USER) and secrets.compare_digest(p, PASS)

    def _deny(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _path(self):
        return urllib.parse.urlparse(self.path).path

    def _allowed(self):
        p = self._path()
        return p in ("/", "/index.html") or p.endswith(".html")

    def do_HEAD(self):
        if not self._authed():
            return self._deny()
        if not self._allowed():
            return self.send_error(404)
        super().do_HEAD()

    def do_GET(self):
        if not self._authed():
            return self._deny()
        if self._path() in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/MEMORY.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not self._allowed():
            return self.send_error(404)
        super().do_GET()

    def list_directory(self, path):
        self.send_error(404)
        return None

    def log_message(self, fmt, *args):
        # quiet; comment out to debug
        pass


if __name__ == "__main__":
    print(f"serving {DIR} on 0.0.0.0:{PORT} (user={USER}, *.html only, basic auth)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
