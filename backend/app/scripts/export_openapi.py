import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    document = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(document, encoding="utf-8")
    else:
        sys.stdout.write(document)


if __name__ == "__main__":
    main()
