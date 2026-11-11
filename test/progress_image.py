"""Test the real binary on a newly created image; never select a physical disk."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

exe = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix="pfsshell-ci-") as directory:
    root = Path(directory)
    with (root / "test.img").open("wb") as stream:
        stream.truncate(2 * 1024**3)
    payload = root / "payload.bin"
    with payload.open("wb") as stream:
        for _ in range(32):
            stream.write(bytes(range(256)) * 4096)
    (root / "empty.bin").touch()

    def run(commands):
        result = subprocess.run([exe], cwd=root, text=True,
            input="\n".join(["device test.img", *commands, "exit", ""]),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        assert result.returncode == 0, result.stdout
        return result.stdout

    output = run(["initialize yes", "mount __net", "put payload.bin", "put empty.bin", "umount"])
    assert "PFS_ERROR" not in output, output
    assert "PFS_DONE 33554432 33554432" in output, output
    assert "PFS_DONE 0 0" in output, output
    expected = hashlib.sha256(payload.read_bytes()).digest()
    payload.unlink()
    output = run(["mount __net", "get payload.bin", "umount"])
    assert hashlib.sha256(payload.read_bytes()).digest() == expected, output
    output = run(["mount __net", "put missing.bin", "umount"])
    assert "PFS_ERROR 0 0" in output and "PFS_DONE" not in output, output
    with (root / "too-big.bin").open("wb") as stream:
        stream.truncate(160 * 1024**2)
    output = run(["mount __net", "put too-big.bin", "umount"])
    assert "PFS_ERROR" in output and "PFS_DONE" not in output, output
    print("PASS: SHA256 round trip, empty file, missing source, full partition")
