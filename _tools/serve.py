#!/usr/bin/env python3
"""Tiny local web server WITH HTTP Range support (needed so browsers can seek in the audio).
Usage:  python3 serve.py [port]   then open http://localhost:8000/
(Python's built-in `python3 -m http.server` does not support Range requests, so audio seeking
fails in Chrome when served that way.) Only needed for YouTube mode testing; Local audio mode
works by simply double-clicking the HTML files."""
import http.server, os, re, sys
class H(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        rng = self.headers.get('Range')
        path = self.translate_path(self.path)
        if not rng or os.path.isdir(path) or not os.path.exists(path):
            return super().send_head()
        m = re.match(r'bytes=(\d*)-(\d*)', rng)
        size = os.path.getsize(path)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else size - 1
        if m and not m.group(1) and m.group(2):
            start, end = size - int(m.group(2)), size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416); return None
        f = open(path, 'rb'); f.seek(start)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        self._remaining = end - start + 1
        return f
    def copyfile(self, src, dst):
        n = getattr(self, '_remaining', None)
        if n is None: return super().copyfile(src, dst)
        while n > 0:
            b = src.read(min(65536, n))
            if not b: break
            dst.write(b); n -= len(b)
    def end_headers(self):
        if not self.headers.get('Range'): self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()
if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # serve the site root (parent of _tools/)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f'Serving {os.getcwd()} at http://localhost:{port}/  (Ctrl+C to stop)')
    http.server.ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
