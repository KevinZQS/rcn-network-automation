#!/usr/bin/env python3
"""
deploy_lab2.py - Safe deploy wrapper for rcn-lab2

Solves the recurring problem where rcn.clab.yaml's top-level "name:"
field keeps reverting to "rcn-lab1" (most likely from editing a stale
local copy of the file and re-uploading it via WinSCP).

What this does, every single time, regardless of what's currently in
the file on disk:
  1. Forces the "name:" line to read "name: rcn-lab2" (rewrites the
     file in place if it's wrong, leaves it alone if it's already right).
  2. Destroys any existing deployment under EITHER "rcn-lab1" or
     "rcn-lab2" labels, so there is never a leftover orphan container
     set sitting around eating CPU under the wrong name.
  3. Deploys fresh from the now-guaranteed-correct file.
  4. Prints the final container list so you can see it worked.

Usage:
    python3 deploy_lab2.py

Run this from the same directory as rcn.clab.yaml (~/rcn-lab2).
"""

import re
import subprocess
import sys
from pathlib import Path

YAML_FILE = "rcn.clab.yaml"
CORRECT_NAME = "rcn-lab2"
KNOWN_STALE_NAMES = ["rcn-lab1", "rcn-lab2"]  # destroy under both, just in case


def run(cmd, check=True):
    """Run a shell command, streaming output live, and return the exit code."""
    print(f"\n$ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"\n!! Command failed with exit code {result.returncode}: {cmd}")
        sys.exit(result.returncode)
    return result.returncode


def force_correct_name(path: Path) -> None:
    """Rewrite the top-level 'name:' line to the correct value, no matter
    what it currently says. Only touches the first line matching
    ^name:\\s*\\S+ at the start of the file (the top-level topology name),
    not any other 'name:' key that might appear nested elsewhere."""
    text = path.read_text()
    pattern = re.compile(r"^name:\s*\S+", re.MULTILINE)

    match = pattern.search(text)
    if not match:
        print("!! Could not find a top-level 'name:' line in the file. "
              "Refusing to guess - please check the file manually.")
        sys.exit(1)

    current = match.group(0)
    correct = f"name: {CORRECT_NAME}"

    if current.strip() == correct.strip():
        print(f"[ok] name field already correct: '{current.strip()}'")
        return

    print(f"[fix] name field was '{current.strip()}' -> rewriting to '{correct}'")
    new_text = pattern.sub(correct, text, count=1)
    path.write_text(new_text)


def cleanup_orphans() -> None:
    """Force-remove any leftover containers under either lab name, so a
    stale deployment can never sit around silently eating resources."""
    for name in KNOWN_STALE_NAMES:
        result = subprocess.run(
            f"docker ps -a --format '{{{{.Names}}}}' | grep -E '^clab-{name}-'",
            shell=True, capture_output=True, text=True
        )
        containers = result.stdout.split()
        if containers:
            print(f"[cleanup] found {len(containers)} leftover container(s) "
                  f"under '{name}', removing: {' '.join(containers)}")
            run(f"docker rm -f {' '.join(containers)}", check=False)
        else:
            print(f"[ok] no leftover containers under '{name}'")


def main():
    path = Path(YAML_FILE)
    if not path.exists():
        print(f"!! {YAML_FILE} not found in the current directory ({Path.cwd()}). "
              f"cd into ~/rcn-lab2 first.")
        sys.exit(1)

    print("=== Step 1: Force-correct the topology name ===")
    force_correct_name(path)

    print("\n=== Step 2: Destroy any existing deployment (both possible names) ===")
    run(f"sudo containerlab destroy -t {YAML_FILE}", check=False)
    cleanup_orphans()

    print("\n=== Step 3: Verify name one more time before deploying ===")
    verify = subprocess.run(f"grep '^name:' {YAML_FILE}", shell=True,
                             capture_output=True, text=True)
    print(f"[verify] {verify.stdout.strip()}")
    if CORRECT_NAME not in verify.stdout:
        print("!! Name still wrong after fix attempt - aborting deploy. "
              "Something is seriously off, check the file by hand.")
        sys.exit(1)

    print("\n=== Step 4: Deploy fresh ===")
    run(f"sudo containerlab deploy -t {YAML_FILE}")

    print("\n=== Step 5: Final container list ===")
    run(f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep {CORRECT_NAME}")

    print(f"\nDone. All containers should be named clab-{CORRECT_NAME}-*.")
    print("Give it 2-4 minutes to converge (longer if R5/SONiC is involved) "
          "before running any reachability tests.")


if __name__ == "__main__":
    main()