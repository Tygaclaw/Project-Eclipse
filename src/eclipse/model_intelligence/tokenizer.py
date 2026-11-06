"""Bounded, read-only tokenizer and chat-template inspection.

This module statically describes the tokenizer assets and chat format of a
local Hugging Face model folder. It reads only small control files and bounded
UTF-8 templates. It never imports Jinja, compiles or renders a template,
executes repository code, loads a tokenizer runtime, or reads tensor payloads.

Every discovered value carries an explicit evidence label (``observed``,
``declared``, ``derived`` or ``unknown``) so callers can tell measured facts
apart from values a file merely claims. Chat templates are treated as
untrusted text and are never interpreted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

_JSON_ASSETS = frozenset(
    {
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "vocab.json",
        "chat_template.json",
    }
)
_TEXT_ASSETS = frozenset({"merges.txt", "vocab.txt", "chat_template.jinja"})
_SENTENCEPIECE_MODELS = frozenset(
    {
        "tokenizer.model",
        "spiece.model",
        "sentencepiece.model",
        "sentencepiece.bpe.model",
    }
)

_ADDITIONAL_TEMPLATES_DIR = "additional_chat_templates"
_JINJA_SUFFIX = ".jinja"
_CHAT_TEMPLATE_JINJA = "chat_template.jinja"
_CHAT_TEMPLATE_JSON = "chat_template.json"
_TOKENIZER_CONFIG = "tokenizer_config.json"

_SPECIAL_TOKEN_FIELDS = (
    ("bos", "bos_token", "bos_token_id"),
    ("eos", "eos_token", "eos_token_id"),
    ("unk", "unk_token", "unk_token_id"),
    ("pad", "pad_token", "pad_token_id"),
    ("sep", "sep_token", "sep_token_id"),
    ("cls", "cls_token", "cls_token_id"),
    ("mask", "mask_token", "mask_token_id"),
)

# llama.cpp/GGUF uses different key names for a few tokens than Transformers.
_GGUF_SPECIAL_TOKEN_KEYS = (
    ("bos", "bos_token_id"),
    ("eos", "eos_token_id"),
    ("unk", "unknown_token_id"),
    ("pad", "padding_token_id"),
    ("sep", "separator_token_id"),
    ("cls", "cls_token_id"),
    ("mask", "mask_token_id"),
)

_TEMPLATE_KIND_RANK = {
    "standalone_jinja": 0,
    "additional_named_jinja": 1,
    "embedded_tokenizer_config": 2,
    "legacy_chat_template_json": 3,
    "gguf_metadata": 0,
}

_CHAT_PRECEDENCE_REFERENCE = (
    "https://huggingface.co/docs/transformers/en/chat_templating_writing"
)


class TokenizerError(Exception):
    """Base class for expected tokenizer inspection failures."""


class TokenizerFormatError(TokenizerError):
    """The input folder is malformed or unsupported."""


class TokenizerResourceLimitError(TokenizerError):
    """The tokenizer assets exceed a configured inspection limit."""


@dataclass(frozen=True, slots=True)
class TokenizerLimits:
    """Hard limits for untrusted tokenizer folders and chat templates."""

    max_entries: int = 100_000
    max_name_bytes: int = 65_536
    max_json_bytes: int = 128 * 1024 * 1024
    max_text_bytes: int = 128 * 1024 * 1024
    max_template_bytes: int = 4 * 1024 * 1024
    max_template_count: int = 256
    max_template_preview_bytes: int = 4096
    max_token_preview_items: int = 16
    max_string_preview_chars: int = 256

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in (
            "max_json_bytes",
            "max_text_bytes",
            "max_template_bytes",
            "max_template_preview_bytes",
            "max_string_preview_chars",
        ):
            if getattr(self, name) == 0:
                raise ValueError(f"{name} must be greater than zero")


def _clip_text(text: str, max_bytes: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    return encoded[:max_bytes].decode("utf-8", errors="ignore"), True


def _clip_string(value: Any, limits: TokenizerLimits) -> str | None:
    if not isinstance(value, str):
        return None
    clipped, _ = _clip_text(value, limits.max_string_preview_chars)
    return clipped


def _json_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _read_bounded(path: Path, max_bytes: int) -> tuple[bytes | None, str | None]:
    # Read at most max_bytes + 1 so a file changed between a stat() call and the
    # read cannot bypass the memory limit.
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        return None, f"{path.name} could not be read: {exc}"
    if len(data) > max_bytes:
        return None, f"{path.name} exceeds the {max_bytes:,}-byte read limit"
    return data, None


def _asset_entry(
    name: str,
    size_bytes: int,
    kind: str,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "size_bytes": size_bytes,
        "kind": kind,
        "status": status,
        "reason": reason,
        "evidence": "observed",
    }


def _token_content(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, str):
            return content
    return None


def _scan_entries(
    base: Path,
    limits: TokenizerLimits,
) -> tuple[dict[str, int], list[str], list[str], int, list[str]]:
    files: dict[str, int] = {}
    directories: list[str] = []
    symlinks: list[str] = []
    warnings: list[str] = []
    entry_count = 0
    try:
        with os.scandir(base) as entries:
            for entry in entries:
                entry_count += 1
                if entry_count > limits.max_entries:
                    raise TokenizerResourceLimitError(
                        f"Folder has more than {limits.max_entries:,} entries"
                    )
                if len(entry.name.encode("utf-8")) > limits.max_name_bytes:
                    raise TokenizerResourceLimitError(
                        f"Folder entry name exceeds {limits.max_name_bytes:,} bytes"
                    )
                if entry.is_symlink():
                    symlinks.append(entry.name)
                elif entry.is_dir(follow_symlinks=False):
                    directories.append(entry.name)
                elif entry.is_file(follow_symlinks=False):
                    try:
                        files[entry.name] = entry.stat(follow_symlinks=False).st_size
                    except OSError as exc:
                        warnings.append(f"Could not read the size of {entry.name!r}: {exc}")
    except OSError as exc:
        raise TokenizerError(f"Cannot list input folder: {exc}") from exc
    return files, directories, symlinks, entry_count, warnings


def _load_json_assets(
    base: Path,
    files: dict[str, int],
    limits: TokenizerLimits,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    parsed: dict[str, Any] = {}
    assets: list[dict[str, Any]] = []
    warnings: list[str] = []
    for name in sorted(files):
        if name not in _JSON_ASSETS:
            continue
        size = files[name]
        data, reason = _read_bounded(base / name, limits.max_json_bytes)
        if reason is not None:
            assets.append(_asset_entry(name, size, "json", "skipped", reason))
            warnings.append(f"Did not parse {name}: {reason}")
            continue
        try:
            document = json.loads((data or b"").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            reason = f"{name} is not valid UTF-8 JSON"
            assets.append(_asset_entry(name, size, "json", "error", reason))
            warnings.append(reason)
            continue
        parsed[name] = document
        assets.append(_asset_entry(name, size, "json", "parsed"))
    return parsed, assets, warnings


def _load_text_assets(
    base: Path,
    files: dict[str, int],
    limits: TokenizerLimits,
) -> tuple[dict[str, str], list[dict[str, Any]], list[str]]:
    texts: dict[str, str] = {}
    assets: list[dict[str, Any]] = []
    warnings: list[str] = []
    for name in sorted(files):
        if name not in _TEXT_ASSETS:
            continue
        size = files[name]
        data, reason = _read_bounded(base / name, limits.max_text_bytes)
        if reason is not None:
            assets.append(_asset_entry(name, size, "text", "skipped", reason))
            warnings.append(f"Did not read {name}: {reason}")
            continue
        try:
            texts[name] = (data or b"").decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            reason = f"{name} is not valid UTF-8"
            assets.append(_asset_entry(name, size, "text", "error", reason))
            warnings.append(reason)
            continue
        assets.append(_asset_entry(name, size, "text", "parsed"))
    return texts, assets, warnings


def _sentencepiece_inventory(
    files: dict[str, int],
) -> tuple[list[dict[str, Any]], list[str]]:
    assets: list[dict[str, Any]] = []
    warnings: list[str] = []
    for name in sorted(files):
        if name not in _SENTENCEPIECE_MODELS:
            continue
        reason = "SentencePiece model is binary and was inventoried only, not parsed"
        assets.append(_asset_entry(name, files[name], "sentencepiece_model", "inventory_only", reason))
    if any(entry["kind"] == "sentencepiece_model" for entry in assets):
        warnings.append(
            "SentencePiece model files were inventoried by name and size only; their "
            "vocabulary and special tokens were not parsed."
        )
    return assets, warnings


def _added_token_map(documents: dict[str, Any]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    tokenizer_json = documents.get("tokenizer.json")
    if isinstance(tokenizer_json, dict):
        added = tokenizer_json.get("added_tokens")
        if isinstance(added, list):
            for item in added:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                identifier = item.get("id")
                if isinstance(content, str) and isinstance(identifier, int) and not isinstance(identifier, bool):
                    lookup.setdefault(content, identifier)
    config = documents.get(_TOKENIZER_CONFIG)
    if isinstance(config, dict):
        decoder = config.get("added_tokens_decoder")
        if isinstance(decoder, dict):
            for key, item in decoder.items():
                content = _token_content(item)
                identifier: int | None = None
                if isinstance(key, str) and key.isdigit():
                    identifier = int(key)
                elif isinstance(item, dict) and isinstance(item.get("id"), int):
                    identifier = item["id"]
                if content is not None and identifier is not None:
                    lookup.setdefault(content, identifier)
    added_tokens = documents.get("added_tokens.json")
    if isinstance(added_tokens, dict):
        for content, identifier in added_tokens.items():
            if isinstance(content, str) and isinstance(identifier, int) and not isinstance(identifier, bool):
                lookup.setdefault(content, identifier)
    return lookup


def _added_token_summary(
    documents: dict[str, Any],
    lookup: dict[str, int],
    limits: TokenizerLimits,
) -> dict[str, Any]:
    preview: list[dict[str, Any]] = []
    count: int | None = None
    source: str | None = None

    tokenizer_json = documents.get("tokenizer.json")
    config = documents.get(_TOKENIZER_CONFIG)
    added_tokens_json = documents.get("added_tokens.json")

    if isinstance(tokenizer_json, dict) and isinstance(tokenizer_json.get("added_tokens"), list):
        items = tokenizer_json["added_tokens"]
        count = len(items)
        source = "tokenizer.json:added_tokens"
        for item in items[: limits.max_token_preview_items]:
            if not isinstance(item, dict):
                continue
            entry: dict[str, Any] = {
                "id": item.get("id") if isinstance(item.get("id"), int) else None,
                "content": _clip_string(item.get("content"), limits),
            }
            if "special" in item:
                entry["special"] = item.get("special") if isinstance(item.get("special"), bool) else None
            preview.append(entry)
    elif isinstance(config, dict) and isinstance(config.get("added_tokens_decoder"), dict):
        decoder = config["added_tokens_decoder"]
        count = len(decoder)
        source = "tokenizer_config.json:added_tokens_decoder"
        for key, item in list(decoder.items())[: limits.max_token_preview_items]:
            identifier = int(key) if isinstance(key, str) and key.isdigit() else None
            preview.append(
                {
                    "id": identifier,
                    "content": _clip_string(_token_content(item), limits),
                    "special": item.get("special") if isinstance(item, dict) and isinstance(item.get("special"), bool) else None,
                }
            )
    elif isinstance(added_tokens_json, dict):
        count = len(added_tokens_json)
        source = "added_tokens.json"
        for content, identifier in list(added_tokens_json.items())[: limits.max_token_preview_items]:
            preview.append(
                {
                    "id": identifier if isinstance(identifier, int) and not isinstance(identifier, bool) else None,
                    "content": _clip_string(content, limits),
                    "special": None,
                }
            )

    return {
        "added_token_count": count,
        "added_token_count_source": source,
        "added_tokens_preview": preview,
        "added_tokens_preview_truncated": bool(count is not None and count > len(preview)),
    }


def _special_token_summary(
    documents: dict[str, Any],
    lookup: dict[str, int],
    limits: TokenizerLimits,
) -> dict[str, Any]:
    config = documents.get(_TOKENIZER_CONFIG) if isinstance(documents.get(_TOKENIZER_CONFIG), dict) else {}
    special_map = (
        documents.get("special_tokens_map.json")
        if isinstance(documents.get("special_tokens_map.json"), dict)
        else {}
    )
    result: dict[str, Any] = {}
    for label, content_key, id_key in _SPECIAL_TOKEN_FIELDS:
        content_value = config.get(content_key)
        source = _TOKENIZER_CONFIG
        if content_value is None and content_key in special_map:
            content_value = special_map.get(content_key)
            source = "special_tokens_map.json"
        content = _token_content(content_value)

        identifier: int | None = None
        id_evidence = "unknown"
        declared_id = config.get(id_key)
        if isinstance(declared_id, int) and not isinstance(declared_id, bool):
            identifier = declared_id
            id_evidence = "declared"
        elif content is not None and content in lookup:
            identifier = lookup[content]
            id_evidence = "observed"

        if content is None and identifier is None:
            continue
        if content_value is None and identifier is not None:
            source = _TOKENIZER_CONFIG
        result[label] = {
            "content": _clip_string(content, limits),
            "id": identifier,
            "id_evidence": id_evidence,
            "content_evidence": "declared" if content is not None else "unknown",
            "source": source,
        }
    return result


def _vocab_size_summary(
    documents: dict[str, Any],
    texts: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    tokenizer_json = documents.get("tokenizer.json")
    if isinstance(tokenizer_json, dict):
        model = tokenizer_json.get("model")
        if isinstance(model, dict):
            vocab = model.get("vocab")
            if isinstance(vocab, (dict, list)):
                candidates.append(
                    {
                        "source": "tokenizer.json:model.vocab",
                        "count": len(vocab),
                        "evidence": "observed",
                    }
                )

    vocab_json = documents.get("vocab.json")
    if isinstance(vocab_json, dict):
        candidates.append(
            {"source": "vocab.json", "count": len(vocab_json), "evidence": "observed"}
        )
    elif isinstance(vocab_json, list):
        candidates.append({"source": "vocab.json", "count": len(vocab_json), "evidence": "observed"})

    if "vocab.txt" in texts:
        candidates.append(
            {
                "source": "vocab.txt",
                "count": len(texts["vocab.txt"].splitlines()),
                "evidence": "observed",
            }
        )

    declared = config.get("vocab_size")
    if isinstance(declared, int) and not isinstance(declared, bool) and declared >= 0:
        candidates.append(
            {"source": _TOKENIZER_CONFIG + ":vocab_size", "count": declared, "evidence": "declared"}
        )

    chosen = candidates[0] if candidates else None
    return {
        "vocab_size": chosen["count"] if chosen else None,
        "vocab_size_evidence": chosen["evidence"] if chosen else "unknown",
        "vocab_size_source": chosen["source"] if chosen else None,
        "vocab_size_candidates": candidates,
    }


def _template_entry(
    name: str,
    origin: str,
    kind: str,
    text: str,
    size_bytes: int,
    limits: TokenizerLimits,
) -> dict[str, Any]:
    preview, truncated = _clip_text(text, limits.max_template_preview_bytes)
    return {
        "name": name,
        "origin": origin,
        "kind": kind,
        "size_bytes": size_bytes,
        "status": "parsed",
        "preview": preview,
        "preview_truncated": truncated,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "evidence": "observed",
    }


def _embedded_templates(
    value: Any,
    origin: str,
    kind: str,
    limits: TokenizerLimits,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(value, str):
        entries.append(_template_entry("default", origin, kind, value, len(value.encode("utf-8")), limits))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, dict):
                name = item.get("name")
                text = item.get("template")
            else:
                name = None
                text = item
            if not isinstance(text, str):
                continue
            template_name = name if isinstance(name, str) and name else f"template_{index}"
            entries.append(
                _template_entry(
                    template_name,
                    origin,
                    kind,
                    text,
                    len(text.encode("utf-8")),
                    limits,
                )
            )
    elif isinstance(value, dict):
        for name, text in value.items():
            if not isinstance(text, str):
                continue
            template_name = name if isinstance(name, str) and name else "default"
            entries.append(
                _template_entry(
                    template_name,
                    origin,
                    kind,
                    text,
                    len(text.encode("utf-8")),
                    limits,
                )
            )
    return entries


def _read_template_file(
    path: Path,
    name: str,
    kind: str,
    limits: TokenizerLimits,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    try:
        size = path.stat().st_size
    except OSError as exc:
        reason = f"{path.name} could not be read: {exc}"
        asset = _asset_entry(path.name, 0, kind, "error", reason)
        warnings.append(reason)
        return None, asset, warnings
    data, reason = _read_bounded(path, limits.max_template_bytes)
    if reason is not None:
        asset = _asset_entry(path.name, size, kind, "skipped", reason)
        warnings.append(reason)
        return None, asset, warnings
    try:
        text = (data or b"").decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        reason = f"{path.name} is not valid UTF-8"
        asset = _asset_entry(path.name, size, kind, "error", reason)
        warnings.append(reason)
        return None, asset, warnings
    asset = _asset_entry(path.name, size, kind, "parsed")
    return _template_entry(name, path.name, kind, text, size, limits), asset, warnings


def _chat_templates_summary(
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        by_name.setdefault(source["name"], []).append(source)

    conflicts: list[dict[str, Any]] = []
    for name, group in sorted(by_name.items()):
        hashes = {entry["content_sha256"] for entry in group}
        if len(group) > 1 and len(hashes) > 1:
            conflicts.append(
                {
                    "name": name,
                    "origins": [entry["origin"] for entry in group],
                    "reason": "multiple sources define this template name with different content",
                }
            )

    defaults = [entry for entry in sources if entry["name"] == "default"]
    effective_default: dict[str, Any] | None = None
    if defaults:
        chosen = min(defaults, key=lambda entry: _TEMPLATE_KIND_RANK.get(entry["kind"], 99))
        effective_default = {
            "name": chosen["name"],
            "origin": chosen["origin"],
            "kind": chosen["kind"],
            "evidence": "documented_loader_precedence",
        }

    return {
        "count": len(sources),
        "sources": sources,
        "has_multiple": len(sources) > 1,
        "default": effective_default,
        "conflicts": conflicts,
        "precedence": {
            "order": [
                "standalone_jinja (chat_template.jinja, default)",
                "additional_named_jinja (additional_chat_templates/*.jinja)",
                "embedded_tokenizer_config (tokenizer_config.json chat_template)",
                "legacy_chat_template_json (chat_template.json)",
            ],
            "evidence": "documented_loader_precedence",
            "reference": _CHAT_PRECEDENCE_REFERENCE,
        },
        "note": (
            "Static inspection only. Templates are untrusted text and are never compiled, "
            "rendered or executed, and runtime compatibility is not claimed."
        ),
    }


def _collect_chat_templates(
    base: Path,
    documents: dict[str, Any],
    files: dict[str, int],
    add_dir_files: dict[str, int],
    limits: TokenizerLimits,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    sources: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    warnings: list[str] = []

    config = documents.get(_TOKENIZER_CONFIG)
    if isinstance(config, dict) and "chat_template" in config:
        embedded = _embedded_templates(
            config.get("chat_template"),
            f"{_TOKENIZER_CONFIG}:chat_template",
            "embedded_tokenizer_config",
            limits,
        )
        sources.extend(embedded)
        if not embedded:
            warnings.append(
                f"{_TOKENIZER_CONFIG} chat_template was present but had no usable string template"
            )

    legacy = documents.get(_CHAT_TEMPLATE_JSON)
    if isinstance(legacy, dict):
        embedded = _embedded_templates(
            legacy.get("chat_template"),
            f"{_CHAT_TEMPLATE_JSON}:chat_template",
            "legacy_chat_template_json",
            limits,
        )
        sources.extend(embedded)
        if not embedded:
            warnings.append(
                f"{_CHAT_TEMPLATE_JSON} did not contain a usable chat_template string"
            )

    if _CHAT_TEMPLATE_JINJA in files:
        entry, asset, entry_warnings = _read_template_file(
            base / _CHAT_TEMPLATE_JINJA, "default", "standalone_jinja", limits
        )
        warnings.extend(entry_warnings)
        if asset is not None:
            assets.append(asset)
        if entry is not None:
            sources.append(entry)

    for name in sorted(add_dir_files):
        if not name.endswith(_JINJA_SUFFIX):
            continue
        stem = name[: -len(_JINJA_SUFFIX)]
        template_name = stem if stem else name
        entry, asset, entry_warnings = _read_template_file(
            base / _ADDITIONAL_TEMPLATES_DIR / name,
            template_name,
            "additional_named_jinja",
            limits,
        )
        warnings.extend(entry_warnings)
        if asset is not None:
            assets.append(asset)
        if entry is not None:
            sources.append(entry)

    summary = _chat_templates_summary(sources)
    if summary["conflicts"]:
        warnings.append(
            "Conflicting chat-template sources were found: "
            + ", ".join(conflict["name"] for conflict in summary["conflicts"][:10])
        )
    return summary, assets, warnings


def _scan_additional_templates(
    base: Path,
    limits: TokenizerLimits,
) -> tuple[dict[str, int], list[str], list[str]]:
    directory = base / _ADDITIONAL_TEMPLATES_DIR
    files: dict[str, int] = {}
    warnings: list[str] = []
    try:
        is_dir = directory.is_dir() and not directory.is_symlink()
    except OSError:
        is_dir = False
    if not is_dir:
        return files, [], warnings

    count = 0
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                if count > limits.max_template_count:
                    warnings.append(
                        f"{_ADDITIONAL_TEMPLATES_DIR} has more than "
                        f"{limits.max_template_count:,} entries; only the first were considered"
                    )
                    break
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    continue
                name = entry.name
                if not name.endswith(_JINJA_SUFFIX):
                    continue
                if len(name.encode("utf-8")) > limits.max_name_bytes:
                    warnings.append(f"Template name {name!r} exceeds the name size limit and was skipped")
                    continue
                try:
                    files[name] = entry.stat(follow_symlinks=False).st_size
                except OSError as exc:
                    warnings.append(f"Could not read the size of {_ADDITIONAL_TEMPLATES_DIR}/{name}: {exc}")
    except OSError as exc:
        warnings.append(f"Could not list {_ADDITIONAL_TEMPLATES_DIR}: {exc}")
    return files, sorted(files), warnings


def _extract_config_fields(config: dict[str, Any]) -> dict[str, Any]:
    class_value = config.get("tokenizer_class")
    max_length = config.get("model_max_length")
    if isinstance(max_length, bool) or not isinstance(max_length, int) or max_length < 0:
        max_length = None
    padding_side = config.get("padding_side")
    truncation_side = config.get("truncation_side")
    return {
        "class": class_value if isinstance(class_value, str) else None,
        "class_source": _TOKENIZER_CONFIG if isinstance(class_value, str) else None,
        "max_length": max_length,
        "max_length_source": _TOKENIZER_CONFIG if max_length is not None else None,
        "padding_side": padding_side if isinstance(padding_side, str) else None,
        "truncation_side": truncation_side if isinstance(truncation_side, str) else None,
    }


def _extract_tokenizer_json_fields(tokenizer_json: Any, limits: TokenizerLimits) -> dict[str, Any]:
    if not isinstance(tokenizer_json, dict):
        return {
            "tokenizer_model_type": None,
            "pre_tokenizer_type": None,
            "decoder_type": None,
            "normalizer_type": None,
            "version": None,
            "truncation": None,
        }
    model = tokenizer_json.get("model")
    model_type = None
    if isinstance(model, dict) and isinstance(model.get("type"), str):
        model_type = model["type"]

    def component_type(key: str) -> str | None:
        component = tokenizer_json.get(key)
        if isinstance(component, dict) and isinstance(component.get("type"), str):
            return component["type"]
        return None

    version = tokenizer_json.get("version")
    truncation = tokenizer_json.get("truncation")
    truncation_summary = None
    if isinstance(truncation, dict):
        truncation_summary = {}
        for key in ("direction", "strategy", "max_length"):
            value = truncation.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                truncation_summary[key] = value

    return {
        "tokenizer_model_type": model_type,
        "pre_tokenizer_type": component_type("pre_tokenizer"),
        "decoder_type": component_type("decoder"),
        "normalizer_type": component_type("normalizer"),
        "version": version if isinstance(version, str) else None,
        "truncation": truncation_summary,
    }


def _empty_tokenizer_summary() -> dict[str, Any]:
    return {
        "class": None,
        "class_source": None,
        "tokenizer_model_type": None,
        "vocab_size": None,
        "vocab_size_evidence": "unknown",
        "vocab_size_source": None,
        "vocab_size_candidates": [],
        "added_token_count": None,
        "added_token_count_source": None,
        "added_tokens_preview": [],
        "added_tokens_preview_truncated": False,
        "special_tokens": {},
        "additional_special_tokens": {"count": 0, "preview": [], "source": None},
        "max_length": None,
        "max_length_source": None,
        "padding_side": None,
        "truncation_side": None,
        "pre_tokenizer_type": None,
        "decoder_type": None,
        "normalizer_type": None,
        "version": None,
        "tokenizer_json_truncation": None,
    }


def inspect_tokenizer(
    path: str | os.PathLike[str],
    limits: TokenizerLimits | None = None,
) -> dict[str, Any]:
    """Statically summarize tokenizer assets and chat templates in a folder."""

    base = Path(path)
    limits = limits or TokenizerLimits()
    try:
        base.stat()
    except OSError as exc:
        raise TokenizerError(f"Cannot access input folder: {exc}") from exc
    if not base.is_dir():
        raise TokenizerFormatError("Input path is not a directory")

    files, directories, symlinks, entry_count, scan_warnings = _scan_entries(base, limits)
    warnings: list[str] = list(scan_warnings)

    documents, json_assets, json_warnings = _load_json_assets(base, files, limits)
    texts, text_assets, text_warnings = _load_text_assets(base, files, limits)
    sp_assets, sp_warnings = _sentencepiece_inventory(files)
    add_dir_files, add_dir_names, add_dir_warnings = _scan_additional_templates(base, limits)
    warnings.extend(json_warnings)
    warnings.extend(text_warnings)
    warnings.extend(sp_warnings)
    warnings.extend(add_dir_warnings)

    config = documents.get(_TOKENIZER_CONFIG)
    config_dict = config if isinstance(config, dict) else {}

    summary = _empty_tokenizer_summary()
    summary.update(_extract_config_fields(config_dict))
    summary.update(_extract_tokenizer_json_fields(documents.get("tokenizer.json"), limits))

    lookup = _added_token_map(documents)
    summary.update(_added_token_summary(documents, lookup, limits))
    summary["special_tokens"] = _special_token_summary(documents, lookup, limits)
    summary.update(_vocab_size_summary(documents, texts, config_dict))

    additional_preview: list[Any] = []
    additional_count = 0
    additional_source = None
    for source_name, source_doc in (
        (_TOKENIZER_CONFIG, config_dict),
        ("special_tokens_map.json", documents.get("special_tokens_map.json")),
    ):
        if isinstance(source_doc, dict):
            value = source_doc.get("additional_special_tokens")
            if isinstance(value, list):
                additional_count = len(value)
                additional_source = source_name
                additional_preview = [
                    item if isinstance(item, str) else _token_content(item)
                    for item in value[: limits.max_token_preview_items]
                ]
    summary["additional_special_tokens"] = {
        "count": additional_count,
        "preview": [item for item in additional_preview if isinstance(item, str)],
        "source": additional_source,
    }

    chat_templates, template_assets, template_warnings = _collect_chat_templates(
        base, documents, files, add_dir_files, limits
    )
    warnings.extend(template_warnings)

    assets = [*json_assets, *text_assets, *sp_assets, *template_assets]
    assets.sort(key=lambda entry: (entry["kind"], entry["name"]))

    if symlinks:
        warnings.append(
            "Symbolic links were not followed: "
            + ", ".join(sorted(symlinks)[:10])
            + (" ..." if len(symlinks) > 10 else "")
        )

    evidence = {
        "assets": "observed" if assets else "unknown",
        "tokenizer_class": "observed" if summary["class"] is not None else "unknown",
        "tokenizer_model_type": "observed" if summary["tokenizer_model_type"] is not None else "unknown",
        "vocab_size": summary["vocab_size_evidence"],
        "added_tokens": "observed" if summary["added_token_count"] is not None else "unknown",
        "special_tokens": "observed" if summary["special_tokens"] else "unknown",
        "chat_templates": "observed" if chat_templates["count"] else "unknown",
        "file_sizes": "observed",
    }

    return {
        "format": "eclipse_tokenizer_inspection",
        "folder_name": base.name or str(base),
        "entry_count": entry_count,
        "directory_count": len(directories),
        "symlink_count": len(symlinks),
        "assets": assets,
        "directories": sorted(directories),
        "additional_chat_template_files": add_dir_names,
        "tokenizer": summary,
        "chat_templates": chat_templates,
        "evidence": evidence,
        "inspection": {
            "mode": "static_read_only",
            "tensor_payload_bytes_read": 0,
            "tensor_payloads_loaded": False,
            "source_modified": False,
            "templates_rendered": False,
            "jinja_imported": False,
        },
        "warnings": warnings,
    }


def summarize_gguf_tokenizer(
    metadata: dict[str, Any],
    limits: TokenizerLimits | None = None,
) -> dict[str, Any]:
    """Summarize tokenizer metadata already read by the GGUF inspector.

    Only the bounded previews produced by the GGUF parser are used. This never
    rereads the file, expands a large array, or copies a complete vocabulary.
    """

    limits = limits or TokenizerLimits()
    fields: list[dict[str, Any]] = []
    chat_sources: list[dict[str, Any]] = []
    warnings: list[str] = []

    tokenizer_keys = sorted(
        key for key in metadata if isinstance(key, str) and key.startswith("tokenizer.")
    )

    for key in tokenizer_keys:
        value = metadata[key]
        if key == "tokenizer.chat_template":
            continue
        if isinstance(value, dict) and value.get("kind") == "array":
            fields.append(
                {
                    "key": key,
                    "value_type": "array",
                    "element_type": value.get("element_type"),
                    "count": value.get("count"),
                    "preview": value.get("preview"),
                    "preview_truncated": value.get("preview_truncated"),
                    "evidence": "observed",
                }
            )
        else:
            if isinstance(value, str):
                bounded: Any = _clip_text(value, limits.max_string_preview_chars)[0]
            elif isinstance(value, (bool, int, float)) or value is None:
                bounded = value
            else:
                bounded = None
            fields.append(
                {
                    "key": key,
                    "value_type": _json_type_name(value),
                    "value": bounded,
                    "evidence": "observed",
                }
            )

    chat_template = metadata.get("tokenizer.chat_template")
    if isinstance(chat_template, str):
        chat_sources.append(
            _template_entry(
                "default",
                "tokenizer.chat_template",
                "gguf_metadata",
                chat_template,
                len(chat_template.encode("utf-8")),
                limits,
            )
        )
    elif chat_template is not None:
        warnings.append("tokenizer.chat_template was present but was not a string")

    tokens_field = metadata.get("tokenizer.ggml.tokens")
    vocab_size = None
    vocab_preview: list[Any] = []
    vocab_truncated = False
    if isinstance(tokens_field, dict) and tokens_field.get("kind") == "array":
        count = tokens_field.get("count")
        if isinstance(count, int) and not isinstance(count, bool):
            vocab_size = count
        preview = tokens_field.get("preview")
        if isinstance(preview, list):
            vocab_preview = preview[: limits.max_token_preview_items]
        vocab_truncated = bool(tokens_field.get("preview_truncated")) or bool(
            isinstance(count, int) and count > len(vocab_preview)
        )

    special_tokens: dict[str, Any] = {}
    for label, id_key in _GGUF_SPECIAL_TOKEN_KEYS:
        value = metadata.get(f"tokenizer.ggml.{id_key}")
        if isinstance(value, int) and not isinstance(value, bool):
            special_tokens[label] = {
                "content": None,
                "id": value,
                "id_evidence": "declared",
                "content_evidence": "unknown",
                "source": "gguf metadata",
            }

    model_value = metadata.get("tokenizer.ggml.model")
    pre_value = metadata.get("tokenizer.ggml.pre")

    chat_templates = _chat_templates_summary(chat_sources)

    available = bool(fields) or bool(chat_templates["count"])
    if not available:
        warnings.append("No tokenizer.* metadata was present in the GGUF file")

    return {
        "available": available,
        "source": "gguf_metadata",
        "class": None,
        "class_source": None,
        "tokenizer_model_type": model_value if isinstance(model_value, str) else None,
        "model_label": model_value if isinstance(model_value, str) else None,
        "pre_tokenizer_label": pre_value if isinstance(pre_value, str) else None,
        "pre_tokenizer_type": pre_value if isinstance(pre_value, str) else None,
        "vocab_size": vocab_size,
        "vocab_size_evidence": "observed" if vocab_size is not None else "unknown",
        "vocab_size_source": "gguf:tokenizer.ggml.tokens" if vocab_size is not None else None,
        "vocab_size_candidates": [],
        "vocab_tokens_preview": vocab_preview,
        "vocab_tokens_preview_truncated": vocab_truncated,
        "added_token_count": None,
        "added_token_count_source": None,
        "added_tokens_preview": [],
        "added_tokens_preview_truncated": False,
        "special_tokens": special_tokens,
        "additional_special_tokens": {"count": 0, "preview": [], "source": None},
        "max_length": None,
        "max_length_source": None,
        "padding_side": None,
        "truncation_side": None,
        "decoder_type": None,
        "normalizer_type": None,
        "version": None,
        "tokenizer_json_truncation": None,
        "fields": fields,
        "assets": [],
        "chat_templates": chat_templates,
        "evidence": {
            "tokenizer_model_type": "observed" if isinstance(model_value, str) else "unknown",
            "vocab_size": "observed" if vocab_size is not None else "unknown",
            "special_tokens": "observed" if special_tokens else "unknown",
            "chat_templates": "observed" if chat_templates["count"] else "unknown",
        },
        "warnings": warnings,
    }
