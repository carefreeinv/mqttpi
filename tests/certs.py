"""Generate a throw-away CA and server certificate with the openssl CLI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict

import pytest


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)


def make_ca(dirpath: Path, name: str) -> Dict[str, Path]:
    if shutil.which("openssl") is None:
        pytest.skip("openssl CLI not available")
    dirpath.mkdir(parents=True, exist_ok=True)
    key, crt = dirpath / f"{name}.key", dirpath / f"{name}.crt"
    _run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
         "-subj", f"/CN={name}", "-keyout", str(key), "-out", str(crt),
         "-addext", "basicConstraints=critical,CA:TRUE",
         "-addext", "keyUsage=critical,keyCertSign,cRLSign", cwd=dirpath)
    return {"key": key, "crt": crt}


def make_leaf(dirpath: Path, ca: Dict[str, Path], name: str, cn: str = "localhost") -> Dict[str, Path]:
    key, csr, crt = dirpath / f"{name}.key", dirpath / f"{name}.csr", dirpath / f"{name}.crt"
    ext = dirpath / f"{name}.ext"
    ext.write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=CA:FALSE\n")
    _run("req", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={cn}",
         "-keyout", str(key), "-out", str(csr), cwd=dirpath)
    _run("x509", "-req", "-in", str(csr), "-CA", str(ca["crt"]), "-CAkey", str(ca["key"]),
         "-CAcreateserial", "-days", "2", "-extfile", str(ext), "-out", str(crt), cwd=dirpath)
    return {"key": key, "crt": crt}
