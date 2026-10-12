#!/usr/bin/env python3
"""Render drive-tree/tree.json as a terminal-style `tree` listing in index.html.

tree.json is a flat list of {"id","name","parent","type": "d"|"f"} nodes for
every item under the Drive folder ROOT_ID, gathered by walking it folder by
folder (parentId = '<id>') through the Google Drive connector.
"""
import html
import json
import sys
from pathlib import Path

ROOT_ID = "174OV5jkCQcif_sBKFWrEgzPg1Yxwomsy"
ROOT_NAME = "Music"
HERE = Path(__file__).resolve().parent


def main(src=HERE / "tree.json", out=HERE.parent / "index.html"):
    nodes = {n["id"]: n for n in json.loads(Path(src).read_text())}
    kids = {}
    for n in nodes.values():
        kids.setdefault(n["parent"], []).append(n)
    key = lambda n: (n["type"] != "d", n["name"].casefold(), n["name"], n["id"])
    for v in kids.values():
        v.sort(key=key)

    lines, dirs, files = [f'<span class="d">{html.escape(ROOT_NAME)}/</span>'], 0, 0

    def walk(pid, prefix):
        nonlocal dirs, files
        ch = kids.get(pid, [])
        for i, n in enumerate(ch):
            last = i == len(ch) - 1
            branch = "└── " if last else "├── "
            name = html.escape(n["name"])
            if n["type"] == "d":
                dirs += 1
                lines.append(f'{prefix}{branch}<span class="d">{name}/</span>')
                walk(n["id"], prefix + ("    " if last else "│   "))
            else:
                files += 1
                lines.append(f"{prefix}{branch}{name}")

    walk(ROOT_ID, "")
    lines += ["", f"{dirs} directories, {files} files"]
    body = "\n".join(lines)
    Path(out).write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Music</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; background: #0d1117; color: #c9d1d9; }}
  pre {{ margin: 0; padding: 16px; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre; overflow-x: auto; }}
  .d {{ color: #58a6ff; font-weight: 600; }}
</style>
</head>
<body>
<pre>{body}</pre>
</body>
</html>
""", encoding="utf-8")
    print(f"{out}: {dirs} directories, {files} files")


if __name__ == "__main__":
    main(*sys.argv[1:])
