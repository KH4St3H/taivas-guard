"""Admin commands. Run as: python -m ific_guard.cli <command>"""
import argparse
import json
import logging
from pathlib import Path

from .config import get_settings
from .db import init_db


def main() -> None:
    parser = argparse.ArgumentParser(prog="ific_guard.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Create the operational tables")
    commands.add_parser("sync", help="Run one sync pass against ITU now")
    add = commands.add_parser("import", help="Load a local IFIC zip instead of downloading it")
    add.add_argument("zip", type=Path)
    add.add_argument("--domain", choices=["space", "terrestrial"], required=True)
    add.add_argument("--issue", type=int, required=True)
    export = commands.add_parser("export", help="Evaluate an imported issue and write ranked CSV/JSON with provenance")
    export.add_argument("--domain", choices=["space", "terrestrial"], required=True)
    export.add_argument("--issue", type=int, required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--sha256", help="Select a specific imported revision instead of the latest")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()
    if args.command == "export":
        from .export import export_issue

        try:
            result = export_issue(args.domain, args.issue, args.out, sha256=args.sha256)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(result))
    elif args.command == "sync":
        from .sync.runner import run_sync

        print(json.dumps({"run_id": run_sync("manual")}))
    elif args.command == "import":
        from .sync.fetch import store_zip
        from .sync.runner import record_artifact

        stored = store_zip(args.zip, args.domain, args.issue, get_settings())
        row, is_new = record_artifact(args.domain, args.issue, stored, f"file://{args.zip.resolve()}")
        print(json.dumps({"artifact_id": row.id, "new": is_new, "sha256": stored.sha256}))


if __name__ == "__main__":
    main()
