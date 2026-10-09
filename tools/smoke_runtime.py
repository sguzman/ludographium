#!/usr/bin/env python3
"""End-to-end checks for self-contained verification of an extracted runtime."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(root: Path, *, expect_success: bool):
    command = [
        "cargo", "run", "--locked", "--quiet", "-p", "ludographium", "--",
        "--verify-runtime", "--root", str(root),
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if expect_success and completed.returncode != 0:
        raise AssertionError(f"Unexpected verifier failure: {completed.stderr}")
    if not expect_success:
        if completed.returncode == 0:
            raise AssertionError("Tampered or incomplete runtime was accepted")
        return
    return json.loads(completed.stdout)


def main():
    source = json.loads((ROOT / "generated/v1/distribution.json").read_bytes())
    expected = len(source["artifacts"])
    original = run(ROOT, expect_success=True)
    assert original["verified"] is True
    assert original["input_kind"] == "runtime-root"
    assert original["artifact_count"] == expected

    with tempfile.TemporaryDirectory() as temporary:
        dest = Path(temporary)
        paths = [Path("generated/v1/distribution.json")]
        paths += [Path(item["path"]) for item in source["artifacts"]]
        for relative in paths:
            copy_to = dest / relative
            copy_to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, copy_to)

        clean = run(dest, expect_success=True)
        assert clean == original

        victim = dest / "generated/v1/gb.json"
        pristine = victim.read_bytes()
        victim.write_bytes(pristine + b"tamper")
        run(dest, expect_success=False)
        victim.write_bytes(pristine)

        victim.unlink()
        run(dest, expect_success=False)
        victim.write_bytes(pristine)

        victim.unlink()
        victim.symlink_to(dest / "generated/v1/catalog.json")
        run(dest, expect_success=False)
        victim.unlink()
        victim.write_bytes(pristine)

        manifest_path = dest / "generated/v1/distribution.json"
        unmodified = manifest_path.read_bytes()
        corrupted = json.loads(unmodified)
        corrupted["artifacts"].append(dict(corrupted["artifacts"][0]))
        manifest_path.write_text(json.dumps(corrupted))
        run(dest, expect_success=False)
        manifest_path.write_bytes(unmodified)

        assert run(dest, expect_success=True) == original

    misuse = subprocess.run(
        ["cargo", "run", "--locked", "--quiet", "-p", "ludographium", "--",
         "--verify-runtime", "--platform", "gb"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert misuse.returncode != 0
    assert "--verify-runtime" in misuse.stderr
    print("PASS: full runtime verification, tampering, missing files, symlinks, and CLI misuse")


if __name__ == "__main__":
    main()
