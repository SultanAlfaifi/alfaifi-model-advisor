from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from mustakshif.catalog import CATALOG_SCHEMA_VERSION, OllamaOfficialSource


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Mustakshif's complete official Ollama catalog index.")
    parser.add_argument("--output", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--minimum-models", type=int, default=50)
    return parser


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="catalog-", suffix=".json", dir=str(path.parent))
    os.close(handle)
    temp_path = Path(temporary)
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    args = _parser().parse_args()
    source = OllamaOfficialSource(timeout=args.timeout, workers=args.workers)
    models, errors = source.fetch_all(progress=print)
    if len(models) < args.minimum_models:
        print(f"Catalog rejected: only {len(models)} runnable variants were verified.")
        for error in errors[:20]:
            print(f"  {error}")
        return 2

    payload: dict[str, object] = {
        "version": CATALOG_SCHEMA_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://ollama.com/library",
        "discovered_families": source.discovered_family_count,
        "verified_families": source.verified_family_count,
        "models": [model.to_dict() for model in sorted(models, key=lambda item: item.id)],
    }
    _atomic_json(args.output, payload)
    print(
        f"Wrote {len(models)} variants from {source.verified_family_count}/"
        f"{source.discovered_family_count} official families to {args.output}"
    )
    if errors:
        print(f"{len(errors)} families did not expose a canonical runnable tag in this pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
