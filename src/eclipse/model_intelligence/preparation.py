"""Reversible model preparation with explicit lineage and integrity checks.

Prepared packages never modify the source checkpoint. ``index`` mode writes a
portable manifest plus a full SHA-256 inventory; ``copy`` mode additionally
copies the checkpoint into the prepared store and verifies the copy against the
recorded hashes. Quantization is offered only when a real ``llama-quantize``
executable is discovered, and the result is recorded as a derived variant with
a rollback path to the untouched source.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Callable, Iterable, Mapping

from .model_atlas import build_model_atlas

PREPARE_FORMAT = "eclipse_prepared_model"
PREPARE_VERSION = 1
_HASH_CHUNK = 1024 * 1024
_MAX_HASH_BYTES = 200 * 1024**3


class PreparationError(Exception):
    """Base class for expected preparation failures."""


class PreparationUnavailable(PreparationError):
    """The requested transformation needs a tool that is not installed."""


class IntegrityError(PreparationError):
    """A prepared package does not match its recorded hashes."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str, limit: int = 48) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return (cleaned or "model")[:limit]


def hash_file(path: str | os.PathLike[str], *, max_bytes: int = _MAX_HASH_BYTES) -> str:
    digest = hashlib.sha256()
    seen = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK)
            if not chunk:
                break
            seen += len(chunk)
            if seen > max_bytes:
                raise PreparationError(
                    f"File exceeds the {max_bytes // 1024**3} GiB hashing budget"
                )
            digest.update(chunk)
    return digest.hexdigest()


def _source_files(source: Path) -> list[Path]:
    if source.is_dir():
        files = [
            path
            for path in sorted(source.rglob("*"))
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in {".safetensors", ".json", ".txt", ".model", ".jinja"}
        ]
        if not files:
            raise PreparationError("The model folder contains no inspectable files")
        return files
    if source.is_file():
        return [source]
    raise PreparationError("The model source does not exist")


def build_inventory(
    source: str | os.PathLike[str],
    *,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    """Record size and SHA-256 for every checkpoint file, read-only."""

    root = Path(source).expanduser().resolve()
    files = _source_files(root)
    inventory: list[dict[str, Any]] = []
    for index, path in enumerate(files, start=1):
        relative = path.name if root.is_file() else str(path.relative_to(root))
        if progress is not None:
            progress(index, len(files), relative)
        inventory.append(
            {
                "name": relative,
                "size_bytes": path.stat().st_size,
                "sha256": hash_file(path),
                "evidence": "observed",
            }
        )
    return inventory


@dataclass(frozen=True, slots=True)
class PreparedPackage:
    directory: Path
    manifest: dict[str, Any]

    @property
    def model_path(self) -> Path:
        return self.directory / self.manifest["output_root"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": str(self.directory),
            "manifest": self.manifest,
        }


def prepare_model(
    source: str | os.PathLike[str],
    prepared_root: str | os.PathLike[str],
    *,
    mode: str = "index",
    name: str | None = None,
    progress: Callable[[int, int, str], None] | None = None,
    atlas: Mapping[str, Any] | None = None,
) -> PreparedPackage:
    """Create a reversible prepared package for a model file or folder."""

    if mode not in {"index", "copy"}:
        raise PreparationError("mode must be 'index' or 'copy'")
    root = Path(source).expanduser().resolve()
    if not root.exists():
        raise PreparationError("The model source does not exist")
    prepared = Path(prepared_root).expanduser().resolve()
    prepared.mkdir(parents=True, exist_ok=True)

    document = dict(atlas) if atlas is not None else build_model_atlas(root)
    inventory = build_inventory(root, progress=progress)
    fingerprint = hashlib.sha256(
        json.dumps(
            [(item["name"], item["size_bytes"], item["sha256"]) for item in inventory],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    label = _slug(name or (root.stem if root.is_file() else root.name))
    directory = prepared / f"{label}-{fingerprint[:12]}"
    if directory.exists():
        manifest_path = directory / "manifest.json"
        if manifest_path.is_file():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            return PreparedPackage(directory=directory, manifest=existing)
        raise PreparationError(
            "A different prepared package already exists at the target directory"
        )
    directory.mkdir(parents=True)

    output_root = root.name
    output_bytes = sum(item["size_bytes"] for item in inventory)
    if mode == "copy":
        target = directory / "model"
        target.mkdir(parents=True, exist_ok=True)
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    continue
                relative = path.relative_to(root)
                destination = target / relative
                if path.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif path.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
        else:
            shutil.copy2(root, target / root.name)
        output_root = str(Path("model") / ("" if root.is_dir() else root.name))

    manifest: dict[str, Any] = {
        "format": PREPARE_FORMAT,
        "prepare_version": PREPARE_VERSION,
        "identity": {
            "source_name": root.name,
            "source_path": str(root),
            "source_kind": "directory" if root.is_dir() else "file",
            "source_fingerprint_sha256": fingerprint,
            "output_root": output_root,
        },
        "method": {
            "mode": mode,
            "description": (
                "Lossless index and integrity manifest; the checkpoint was not rewritten."
                if mode == "index"
                else "Lossless copy into the prepared store, verified by SHA-256."
            ),
            "parameters": {},
        },
        "tool": {
            "name": "eclipse",
            "version": _eclipse_version(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "source_size_bytes": output_bytes,
        "files": inventory,
        "atlas": document,
        "created_at": utc_now_iso(),
        "source_modified": False,
        "integrity": {"status": "unverified", "checked_at": None},
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    result = verify_prepared_package(directory)
    return result


def _eclipse_version() -> str:
    try:
        from eclipse import __version__

        return __version__
    except Exception:  # noqa: BLE001 - version reporting must not fail prep
        return "unknown"


def load_manifest(package_dir: str | os.PathLike[str]) -> dict[str, Any]:
    path = Path(package_dir) / "manifest.json"
    if not path.is_file():
        raise PreparationError("The prepared package has no manifest.json")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreparationError("The prepared manifest is unreadable") from exc
    if manifest.get("format") != PREPARE_FORMAT:
        raise PreparationError("The prepared manifest has an unexpected format")
    if not isinstance(manifest.get("files"), list):
        raise PreparationError("The prepared manifest has no file inventory")
    return manifest


def verify_prepared_package(package_dir: str | os.PathLike[str]) -> PreparedPackage:
    """Recompute every recorded hash and update the integrity status."""

    directory = Path(package_dir).expanduser().resolve()
    manifest = load_manifest(directory)
    output_root = manifest["identity"].get("output_root")
    if not isinstance(output_root, str) or not output_root:
        raise PreparationError("The prepared manifest has no output root")
    base = (directory / output_root).resolve()
    try:
        base.relative_to(directory)
    except ValueError as exc:
        raise PreparationError("The prepared output root escapes its package") from exc

    mode = manifest.get("method", {}).get("mode")
    problems: list[str] = []
    checked: list[str] = []
    source = None
    if mode == "index":
        source_value = manifest["identity"].get("source_path")
        if isinstance(source_value, str) and source_value:
            source = Path(source_value).expanduser()
            if not source.exists():
                problems.append("the recorded source checkpoint no longer exists")
    for item in manifest["files"]:
        if not isinstance(item, Mapping):
            problems.append("invalid inventory record")
            continue
        name = item.get("name")
        if not isinstance(name, str):
            problems.append("inventory record without a name")
            continue
        if mode == "copy":
            candidate = (base / name).resolve()
            if base.is_file():
                candidate = base if name == base.name else base / name
            try:
                candidate.relative_to(base if base.is_dir() else base.parent)
            except ValueError:
                problems.append(f"{name}: path escapes the prepared package")
                continue
        else:
            # Index-only packages reference the original source, which stays
            # read-only and external to the package. Re-hash it to prove the
            # manifest still describes the checkpoint on disk.
            if source is None:
                problems.append("missing recorded source path")
                continue
            candidate = source / name if source.is_dir() else source
            if not candidate.is_file():
                problems.append(f"{name}: source file is missing")
                continue
        if not candidate.is_file():
            problems.append(f"{name}: missing")
            continue
        if candidate.stat().st_size != item.get("size_bytes"):
            problems.append(f"{name}: size changed")
            continue
        if hash_file(candidate) != item.get("sha256"):
            problems.append(f"{name}: hash changed")
            continue
        checked.append(name)

    status = "verified" if not problems else "failed"
    manifest["integrity"] = {
        "status": status,
        "checked_at": utc_now_iso(),
        "verified_files": checked,
        "problems": problems,
        "note": (
            "Index-only package: the original source is re-hashed in place; it was "
            "never copied or modified."
            if mode == "index"
            else "All copied files match their recorded SHA-256 hashes."
        ),
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    if problems:
        raise IntegrityError("; ".join(problems[:8]))
    return PreparedPackage(directory=directory, manifest=manifest)


def remove_prepared_package(
    package_dir: str | os.PathLike[str],
    prepared_root: str | os.PathLike[str],
) -> None:
    """Delete a derived package while refusing to touch the model source."""

    directory = Path(package_dir).expanduser().resolve()
    root = Path(prepared_root).expanduser().resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise PreparationError(
            "Refusing to remove a directory outside the prepared store"
        ) from exc
    if directory == root:
        raise PreparationError("Refusing to remove the prepared store itself")
    if not directory.exists():
        return
    shutil.rmtree(directory)


def find_quantize_tool() -> Path | None:
    for name in ("llama-quantize", "llama-quantize.exe", "quantize"):
        located = shutil.which(name)
        if located:
            return Path(located)
    return None


@dataclass(frozen=True, slots=True)
class TransformationResult:
    output_path: Path
    manifest: dict[str, Any]


def quantize_gguf(
    source: str | os.PathLike[str],
    prepared_root: str | os.PathLike[str],
    *,
    quant_type: str = "Q4_K_M",
    executable: str | os.PathLike[str] | None = None,
    progress: Callable[[str], None] | None = None,
    timeout_seconds: int = 7200,
) -> TransformationResult:
    """Run a real llama.cpp quantization when the tool is installed.

    The source is never modified; the output is a separate .gguf file with its
    own SHA-256 and a manifest recording the exact method, tool and parameters.
    """

    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file() or source_path.suffix.lower() != ".gguf":
        raise PreparationError("Quantization requires a GGUF source file")
    tool = Path(executable) if executable else find_quantize_tool()
    if tool is None or not tool.exists():
        raise PreparationUnavailable(
            "llama-quantize was not found. Install llama.cpp and make sure "
            "llama-quantize is on PATH to enable GGUF quantization."
        )
    if quant_type not in {"Q2_K", "Q3_K_S", "Q3_K_M", "Q3_K_L", "Q4_0", "Q4_K_S", "Q4_K_M", "Q5_0", "Q5_K_S", "Q5_K_M", "Q6_K", "Q8_0", "F16"}:
        raise PreparationError(f"Unsupported quantization type: {quant_type}")

    root = Path(prepared_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    source_hash = hash_file(source_path)
    directory = root / f"{_slug(source_path.stem)}-{quant_type.lower()}-{source_hash[:8]}"
    if directory.exists() and (directory / "manifest.json").is_file():
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        output = directory / manifest["output"]["name"]
        return TransformationResult(output_path=output, manifest=manifest)
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{_slug(source_path.stem)}-{quant_type.lower()}.gguf"

    argv = [str(tool), str(source_path), str(output), quant_type, "1"]
    if progress is not None:
        progress(f"Running {Path(tool).name} ({quant_type})")
    process = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=timeout_seconds,
        check=False,
    )
    if process.returncode != 0 or not output.is_file():
        stderr = process.stderr.decode("utf-8", errors="replace")[-2000:]
        raise PreparationError(
            f"Quantization failed (exit {process.returncode}): {stderr.strip()}"
        )
    output_hash = hash_file(output)
    manifest = {
        "format": PREPARE_FORMAT,
        "prepare_version": PREPARE_VERSION,
        "identity": {
            "source_name": source_path.name,
            "source_sha256": source_hash,
            "output_name": output.name,
        },
        "method": {
            "mode": "quantize",
            "description": "Derived GGUF produced by llama-quantize; the source is untouched.",
            "parameters": {"quant_type": quant_type, "threads": 1},
        },
        "tool": {
            "name": "llama-quantize",
            "path_name": Path(tool).name,
            "version": _probe_version(tool),
        },
        "output": {
            "name": output.name,
            "size_bytes": output.stat().st_size,
            "sha256": output_hash,
        },
        "atlas": build_model_atlas(output),
        "created_at": utc_now_iso(),
        "source_modified": False,
        "rollback": {
            "action": "delete_derived_package",
            "source_sha256": source_hash,
            "note": "The original checkpoint is unchanged and remains the rollback target.",
        },
        "integrity": {
            "status": "verified" if hash_file(output) == output_hash else "failed",
            "checked_at": utc_now_iso(),
        },
        "quality": {
            "status": "unmeasured",
            "note": "No capability evaluation has been run for this derived variant.",
        },
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return TransformationResult(output_path=output, manifest=manifest)


def _probe_version(tool: Path) -> str:
    try:
        completed = subprocess.run(
            [str(tool), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    text = completed.stdout.decode("utf-8", errors="replace").strip().splitlines()
    return text[0][:200] if text else "unknown"


def prepared_summary(package_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Public, log-safe summary of a prepared package."""

    manifest = load_manifest(package_dir)
    return {
        "directory_name": Path(package_dir).name,
        "mode": manifest.get("method", {}).get("mode"),
        "source_name": manifest.get("identity", {}).get("source_name"),
        "source_fingerprint_sha256": manifest.get("identity", {}).get("source_fingerprint_sha256"),
        "created_at": manifest.get("created_at"),
        "integrity": manifest.get("integrity", {}).get("status"),
        "file_count": len(manifest.get("files", [])),
    }
