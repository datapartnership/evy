"""Check release artifacts and test clean installs without importing the checkout.

Run after `python -m build`: python scripts/check_distribution.py dist
Pass --tag vX.Y.Z in the release workflow to require matching release metadata.
"""

import argparse
from email.parser import Parser
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--tag")
    args = parser.parse_args()
    if args.tag and not re.fullmatch(r"v\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", args.tag):
        parser.error(
            "release tags must be vX.Y.Z, optionally followed by aN, bN, or rcN"
        )

    wheels = list(args.dist.glob("*.whl"))
    sources = list(args.dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        parser.error(
            "expected exactly one wheel and source archive; clean dist and rebuild"
        )
    wheel, source = wheels[0].resolve(), sources[0].resolve()
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
        )
        metadata = Parser().parsestr(archive.read(metadata_name).decode())
        assert "evy/__init__.py" in archive.namelist()
        assert not any(n.startswith(("tests/", "scripts/")) for n in archive.namelist())
    version = metadata["Version"]
    assert metadata["Name"] == "evy"
    if args.tag:
        assert version == args.tag[1:], (
            f"tag {args.tag} does not match package version {version}"
        )
    with tarfile.open(source) as archive:
        names = archive.getnames()
        root = names[0].split("/")[0]
        for required in (
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "CHANGELOG.md",
            "tests/test_contract.py",
            "tests/fixtures/laads-aqua-subset.nc4",
        ):
            assert f"{root}/{required}" in names, f"source archive missing {required}"
        package_info = archive.extractfile(f"{root}/PKG-INFO")
        assert package_info is not None
        assert Parser().parsestr(package_info.read().decode())["Version"] == version

    project = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "EVY_TEST_LAADS",
        "EVY_TEST_EARTHDATA",
    ):
        env.pop(name, None)
    # Each artifact gets a separate environment, outside the checkout. Dependencies
    # resolve afresh here; the development lockfile cannot hide missing requirements.
    for artifact in (wheel, source):
        with tempfile.TemporaryDirectory(prefix="evy-package-") as directory:
            work = Path(directory)
            venv = work / "venv"
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run(
                ["uv", "venv", "--python", sys.executable, str(venv)],
                check=True,
                cwd=work,
                env=env,
            )
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    str(artifact),
                    "pytest>=7",
                ],
                check=True,
                cwd=work,
                env=env,
            )
            subprocess.run(
                [
                    str(python),
                    "-I",
                    "-c",
                    "import evy, sys; from pathlib import Path; "
                    "from importlib.metadata import version; "
                    "assert Path(evy.__file__).is_relative_to(sys.prefix); "
                    "assert all(hasattr(evy, name) for name in evy.__all__); "
                    f"assert version('evy') == {version!r}",
                ],
                check=True,
                cwd=work,
                env=env,
            )
            shutil.copytree(
                project / "tests",
                work / "tests",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            shutil.copy(project / "pyproject.toml", work / "pyproject.toml")
            subprocess.run(
                [str(python), "-I", "-m", "pytest", "-m", "not live", "tests"],
                check=True,
                cwd=work,
                env=env,
            )
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    f"{artifact}[earthdata]",
                ],
                check=True,
                cwd=work,
                env=env,
            )
            subprocess.run(
                [str(python), "-I", "-m", "pytest", "tests/test_earthdata.py"],
                check=True,
                cwd=work,
                env=env,
            )
            print(f"Verified {artifact.name}", flush=True)


if __name__ == "__main__":
    main()
