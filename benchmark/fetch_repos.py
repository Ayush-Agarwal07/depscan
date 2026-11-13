"""Clone the benchmark repos at their pinned commits into benchmark/repos/ (git-ignored).

    python benchmark/fetch_repos.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def main() -> None:
    for r in json.loads((HERE / "repos.json").read_text()):
        dest = ROOT / r["path"]
        if (dest / ".git").exists():
            print(f"exists  {r['name']}")
            continue
        dest.mkdir(parents=True)
        git("init", "-q", cwd=dest)
        git("remote", "add", "origin", r["url"], cwd=dest)
        git("fetch", "-q", "--depth", "1", "origin", r["sha"], cwd=dest)
        git("checkout", "-q", "FETCH_HEAD", cwd=dest)
        print(f"cloned  {r['name']} @ {r['sha'][:10]}")


if __name__ == "__main__":
    main()
