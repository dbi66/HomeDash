from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EDITOR_ROOT = PROJECT_ROOT / "schema-editor"
PRODUCTION_PATH = PROJECT_ROOT / "data" / "production-schema.json"
FUNCTIONAL_PATH = PROJECT_ROOT / "data" / "functional-schema.json"


class EditorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(EDITOR_ROOT), **kwargs)

    def do_POST(self) -> None:
        if self.path != "/api/save-schema":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size))
            target = payload.get("target")
            schema = payload.get("schema", payload)
            if target not in {"functional", "hydraulic"}:
                raise ValueError("Ungültiges Produktionsziel")
            if schema.get("schema_version") != 1 or not isinstance(schema.get("nodes"), list) or not isinstance(schema.get("edges"), list):
                raise ValueError("Ungültiges Schemaformat")
            output_path = FUNCTIONAL_PATH if target == "functional" else PRODUCTION_PATH
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            response = {"path": str(output_path.relative_to(PROJECT_ROOT)), "target": target}
            body = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))

    def do_GET(self) -> None:
        if self.path == "/api/schemas":
            schemas = []
            for target, path in (("functional", FUNCTIONAL_PATH), ("hydraulic", PRODUCTION_PATH)):
                if path.exists():
                    schemas.append({"target": target, "schema": json.loads(path.read_text(encoding="utf-8"))})
            body = json.dumps({"schemas": schemas}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8080), EditorHandler)
    print("Schema editor listening on http://0.0.0.0:8080")
    server.serve_forever()