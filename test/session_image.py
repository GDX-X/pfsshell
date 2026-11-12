"""Check repeated mounts and exact space reporting on a disposable image, never a physical disk."""
import hashlib
import errno
from pathlib import Path
import subprocess
import sys
import tempfile

exe = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix="pfsshell-session-") as directory:
    root = Path(directory)
    with (root / "test.img").open("wb") as stream:
        stream.truncate(2 * 1024**3)
    payload = root / "game.bin"
    payload.write_bytes(bytes(range(256)) * 4096)
    expected = hashlib.sha256(payload.read_bytes()).digest()

    def run(commands, error=None, initializing=False):
        result = subprocess.run([exe], cwd=root, text=True,
            input="\n".join(["device test.img", *commands, "exit", ""]),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        assert result.returncode == 0, result.stdout
        if error is None:
            assert ("Exit code is" not in result.stdout if initializing else "(!)" not in result.stdout), result.stdout
        else:
            assert f"Exit code is {error}" in result.stdout, result.stdout
        return result.stdout

    run(["initialize yes"], error=None, initializing=True)
    run(["rmpart __net", "mkpart first 128M PFS"])
    output = run(["mount first", "mkdir nested", "cd nested", "umount",
                  "mount __system", "put game.bin", "df64", "umount",
                  "mount __system", "ls", "umount"])
    payload.unlink()
    run(["mount __system", "get game.bin", "umount"])
    assert hashlib.sha256(payload.read_bytes()).digest() == expected
    import re
    match = re.search(r"PFS_SPACE_V1 (\d+) (\d+)", output)
    assert match, output
    total, available = map(int, match.groups())
    assert 0 <= available < total <= 2 * 1024**3, (total, available)
    print("PASS: multiple mounts reset cwd, file round trip, df64 byte counts")
