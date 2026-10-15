"""Build an adapter against a pinned, unmodified PHAT release."""
import argparse
import hashlib
import json
import subprocess
import tarfile
import urllib.request
from pathlib import Path

COMMIT = "a74705e4628e447084d47dbf13a16dfb6d2ebd9a"
ARCHIVE_SHA256 = "0b03a652ca9855eab3bda980a735588fed7c947f43cdf06a1ea8212ca7b8c271"
URL = f"https://bitbucket.org/phat-code/phat/get/{COMMIT}.tar.gz"
FLAGS = ["-O3", "-DNDEBUG", "-std=c++17"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(destination, archive=None):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    tarpath = destination / "phat-v1.7.tar.gz"
    if archive:
        tarpath.write_bytes(Path(archive).read_bytes())
    else:
        urllib.request.urlretrieve(URL, tarpath)
    if digest(tarpath) != ARCHIVE_SHA256:
        raise ValueError("PHAT archive checksum mismatch")
    with tarfile.open(tarpath) as tar:
        tar.extractall(destination, filter="data")
    source = next(destination.glob("phat-code-phat-*/include")).parent
    worker = Path(__file__).with_name("worker.cpp").resolve()
    binary = destination / "phat_worker"
    command = ["g++", *FLAGS, "-I" + str(source / "include"), str(worker), "-o", str(binary)]
    result = subprocess.run(command, capture_output=True, text=True)
    (destination / "build.log").write_text(result.stdout + result.stderr)
    result.check_returncode()
    identity = dict(version="1.7", commit=COMMIT, source_url=URL,
                    archive_sha256=digest(tarpath), compiler=subprocess.check_output(
                        ["g++", "--version"], text=True), flags=FLAGS,
                    worker_sha256=digest(worker), binary_sha256=digest(binary),
                    source_headers={str(p.relative_to(source)): digest(p)
                                    for p in sorted((source / "include").rglob("*.h"))})
    (destination / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    print(binary)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("destination")
    p.add_argument("--archive")
    args = p.parse_args()
    build(args.destination, args.archive)
