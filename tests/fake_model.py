"""A stand-in OpenAI-compatible model server for tests and demos.

It answers each kind of request the app makes with a canned but plausible
reply. `mode="bad"` makes every reply break the rules, to exercise the guards.

    python tests/fake_model.py 8299          # good replies
    python tests/fake_model.py 8298 bad      # rule-breaking replies
"""

from __future__ import annotations

import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer


def reply_for(messages: list, mode: str = "good") -> str:
    content = messages[-1]["content"]
    has_image = isinstance(content, list) and any(p.get("type") == "image_url" for p in content)
    text = content if isinstance(content, str) else " ".join(p.get("text", "") for p in content if p.get("type") == "text")
    bad = mode == "bad"

    if has_image and "seed packet" in text:
        return json.dumps({"crop": "Tomato", "variety": "Pusa Ruby", "local_name": "Tamatar",
                           "sowing_time": "Jun-Jul, Oct-Nov", "days_to_harvest": "65-70"})
    if has_image:
        if bad:
            return '{"plant": "Tomato", "looks_healthy": false, "possible_causes": [{"cause": "Fungal blight", "check": "Spray 2 ml per litre of fungicide"}], "next_step": "Use 5 g of urea per plant."}'
        return ("```json\n" + json.dumps({
            "plant": "Tomato", "looks_healthy": False,
            "possible_causes": [
                {"cause": "Overwatering", "check": "Push a finger into the soil; water only when the top 2-3 cm is dry."},
                {"cause": "Early blight", "check": "Look for brown rings on the lower leaves and remove them."},
            ],
            "next_step": "Improve drainage and keep the leaves dry when watering."}) + "\n```")
    if text.startswith("Translate this note"):
        note = text.split("NOTE:", 1)[1]
        nums = re.findall(r"\d+", note)
        if bad:
            return "This is still English and has 999 in it."
        return "इस सप्ताह बगीचे में काम है। " + " ".join(f"दिन {n}" for n in nums)
    if "QUESTION:" in text:
        if bad:
            return "Plant karela on Dec 31."
        m = re.search(r"closes ([A-Z][a-z]{2} \d{1,2})", text)
        return f"Yes, the window is open until {m.group(1)}." if m else "I don't know; ask a local nursery."
    # weekly note
    return "Plant okra and watermelon before Dec 31." if bad else "Pick one bed today and get your hands in the soil."


class _Handler(BaseHTTPRequestHandler):
    mode = "good"
    requests: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self._send(200, {"data": [{"id": "gemma3:4b"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(body)
        self._send(200, {"choices": [{"message": {"content": reply_for(body["messages"], type(self).mode)}}]})

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FakeModel:
    def __init__(self, mode: str = "good"):
        handler = type("H", (_Handler,), {"mode": mode, "requests": []})
        self.handler = handler
        self.httpd = HTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def requests(self):
        return self.handler.requests

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8299
    _Handler.mode = sys.argv[2] if len(sys.argv) > 2 else "good"
    print(f"fake model ({_Handler.mode}) on http://127.0.0.1:{port}/v1")
    ThreadingHTTPServer(("127.0.0.1", port), _Handler).serve_forever()
