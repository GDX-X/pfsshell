"""Check partition renaming on a disposable image, never a physical disk."""
import hashlib
import errno
from pathlib import Path
import subprocess
import sys
import tempfile

exe = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix="pfsshell-rename-") as directory:
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
    run(["rmpart __net", "mkpart __.POPS 128M PFS", "mount __.POPS",
         "put game.bin", "umount"])
    run(["rename __.POPS __.POPS1"])
    run(["mount __.POPS"], error=-2)
    payload.unlink()
    run(["mount __.POPS1", "get game.bin", "umount"])
    assert hashlib.sha256(payload.read_bytes()).digest() == expected
    run(["rename __.POPS1 __system"], error=-17)
    run(["rename missing __.POPS2"], error=-2)
    run(['rename __.POPS1 ""'], error=-22)
    run(["rename __.POPS1 " + "x" * 33], error=-errno.ENAMETOOLONG)
    # A full 32-byte APA name must not be truncated to 31 bytes.
    full_name = "p" * 32
    run([f"rename __.POPS1 {full_name}"])
    run([f"rename {full_name} __.POPS1"])
    run(["rename __.POPS1 __.POPS2", "rename __.POPS2 __.POPS1"])
    payload.unlink()
    run(["mount __.POPS1", "get game.bin", "umount"])
    assert hashlib.sha256(payload.read_bytes()).digest() == expected
    print("PASS: rename, persistence, SHA256, duplicate/missing/invalid names, 32-byte names")
