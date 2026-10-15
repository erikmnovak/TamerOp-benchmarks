#!/usr/bin/env python3
"""Build the pinned GAP runtime and packages without modifying their sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

URL = "https://github.com/gap-system/gap/releases/download/v4.16.1/gap-4.16.1-core.tar.gz"
SHA256 = "b4433a540a2f746d14b1645a0e95b3d499afb180aa421ebfd62b427f2b0cf74f"
PACKAGES = {
    "qpa": ("https://github.com/gap-packages/qpa.git", "fb02ce297db8ec44333ab9644bbc4258ce1503b6"),
    "gbnp": ("https://github.com/gap-packages/gbnp.git", "e0b46c1aac16f3fbabe743e3169dc6bd86bdc654"),
    "GAPDoc": ("https://github.com/frankluebeck/GAPDoc.git", "36cdebc0165d0635fcb629f6ee877895e5f15fdf"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    for command in ("make", "gcc", "g++", "git"):
        if not shutil.which(command):
            parser.error(f"Install {command} before preparing GAP.")
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "gap-4.16.1-core.tar.gz"
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        parser.error(f"GAP archive checksum mismatch: {archive}")
    target = root / "gap-4.16.1"
    if not target.exists():
        with tarfile.open(archive) as compressed:
            compressed.extractall(root, filter="data")
    marker = target / "tamerop-build.json"
    if marker.exists():
        print(target / "gap")
        return
    with (root / "gap-build.log").open("w") as log:
        subprocess.run(["./configure", "--without-readline"], cwd=target, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
        subprocess.run(["make", "-j2", "CPPFLAGS=-D_GNU_SOURCE -include time.h"], cwd=target,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        for package, (url, revision) in PACKAGES.items():
            path = target / "pkg" / package
            if not path.exists():
                subprocess.run(["git", "clone", url, str(path)], stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(["git", "checkout", "--detach", revision], cwd=path,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
            if actual != revision:
                raise ValueError(f"Wrong {package} revision: {actual}")
    marker.write_text(json.dumps({"gap_archive_sha256": SHA256, "source_edits": False,
        "configure": ["--without-readline"], "make": ["-j2", "CPPFLAGS=-D_GNU_SOURCE -include time.h"],
        "packages": PACKAGES}, indent=2) + "\n")
    print(target / "gap")


if __name__ == "__main__":
    main()
