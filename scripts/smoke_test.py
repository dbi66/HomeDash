from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an HTTP smoke test against HomeDash.")
    parser.add_argument("--url", default="http://127.0.0.1:8501/")
    arguments = parser.parse_args()
    with urlopen(arguments.url, timeout=5) as response:
        body = response.read().decode("utf-8", errors="replace")
    normalized_body = body.lower()
    required_markers = ("<html", "streamlit", "/static/")
    missing = [marker for marker in required_markers if marker not in normalized_body]
    if missing:
        raise RuntimeError(f"dashboard response missing markers: {', '.join(missing)}")
    print(f"HTTP smoke test: ok ({arguments.url})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
