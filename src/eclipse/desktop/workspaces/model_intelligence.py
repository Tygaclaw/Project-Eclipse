"""Model Intelligence & Inference Platform workspace."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..atlas_client import AtlasCancelledError, AtlasClient, AtlasClientError
from ..formatting import (
    completeness_text,
    distribution_rows,
    evidence_text,
    human_bytes,
    human_count,
    source_kind_text,
)
from ..widgets import (
    add_fact,
    add_plain_text,
    add_text,
    clear_layout,
    make_card,
    make_disclosure,
    make_empty_card,
    make_header,
)


_SPECIAL_TOKEN_ORDER = ("bos", "eos", "unk", "pad", "sep", "cls", "mask")


def _special_token_summary(special: Any) -> str:
    if not isinstance(special, dict):
        return ""
    parts: list[str] = []
    for key in _SPECIAL_TOKEN_ORDER:
        entry = special.get(key)
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        token_id = entry.get("id")
        if content and token_id is not None:
            parts.append(f"{key}: {content} (#{token_id})")
        elif content:
            parts.append(f"{key}: {content}")
        elif token_id is not None:
            parts.append(f"{key}: #{token_id}")
    return ", ".join(parts)


def _special_token_evidence(special: Any) -> str:
    if not isinstance(special, dict) or not special:
        return "unknown"
    labels: set[str] = set()
    for entry in special.values():
        if not isinstance(entry, dict):
            continue
        labels.add(str(entry.get("id_evidence") or "unknown"))
        labels.add(str(entry.get("content_evidence") or "unknown"))
    if "declared" in labels:
        return "declared"
    if "observed" in labels:
        return "observed"
    return "unknown"


def _render_assets(layout: QVBoxLayout, assets: Any) -> None:
    if not isinstance(assets, list) or not assets:
        return
    add_plain_text(layout, "Tokenizer files", "FactLabel")
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "unknown")
        kind = str(asset.get("kind") or "unknown").replace("_", " ")
        pieces = [name, kind]
        size = asset.get("size_bytes")
        if isinstance(size, int) and not isinstance(size, bool):
            pieces.append(human_bytes(size))
        status = asset.get("status")
        if status and status != "present":
            pieces.append(f"status: {status}")
        add_plain_text(layout, "  ".join(pieces), "Muted", monospace=True)


def _render_templates(layout: QVBoxLayout, sources: Any) -> None:
    if not isinstance(sources, list) or not sources:
        return
    add_plain_text(layout, "Chat template sources", "FactLabel")
    for template in sources:
        if not isinstance(template, dict):
            continue
        name = str(template.get("name") or "default")
        origin = str(template.get("origin") or "unknown")
        kind = str(template.get("kind") or "unknown").replace("_", " ")
        add_plain_text(layout, f"{name} - {origin} ({kind})", "Muted")
        preview = template.get("preview")
        if isinstance(preview, str) and preview.strip():
            add_plain_text(layout, preview, "CodeBlock", monospace=True)


def _render_gguf_fields(layout: QVBoxLayout, fields: Any) -> None:
    if not isinstance(fields, list) or not fields:
        return
    add_plain_text(layout, "GGUF tokenizer metadata", "FactLabel")
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "unknown")
        value_type = str(field.get("value_type") or "unknown")
        count = field.get("count")
        if isinstance(count, int) and not isinstance(count, bool):
            detail = f"{value_type} [{human_count(count)}]"
        elif "value" in field:
            detail = f"{value_type} = {field.get('value')!r}"
        else:
            detail = value_type
        add_plain_text(layout, f"{key}: {detail}", "Muted", monospace=True)


class _InspectionWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, client: AtlasClient, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._path = str(path)
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        try:
            document = self._client.build(self._path, cancel_event=self._cancel_event)
        except AtlasCancelledError:
            self.cancelled.emit()
        except AtlasClientError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("An unexpected error stopped the inspection.")
        else:
            self.succeeded.emit(document)


class ModelIntelligenceWorkspace(QWidget):
    """Static Model Atlas workspace connected to the existing Python backend."""

    def __init__(self, client: AtlasClient | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModelIntelligenceWorkspace")
        self.setAccessibleName("Model Intelligence and Inference Platform")
        self._client = client or AtlasClient()
        self._source: Path | None = None
        self._worker: _InspectionWorker | None = None
        self._last_atlas: dict[str, Any] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("ResultsScroll")
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(44, 40, 44, 48)
        layout.setSpacing(22)

        layout.addWidget(
            make_header(
                "Model Intelligence & Inference Platform",
                "Inspect a model's headers and tensor index, then read a clear, evidence-labelled "
                "Model Atlas. Tensor weights are never loaded.",
            )
        )

        source_card, source_layout = make_card(
            "Model source",
            "Choose a GGUF file, a Safetensors file, or a local Hugging Face model folder. "
            "Inspection is read-only and does not upload anything.",
        )
        self._source_label = QLabel("No model selected")
        self._source_label.setObjectName("FactValue")
        self._source_label.setWordWrap(True)
        source_layout.addWidget(self._source_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self._choose_file_button = QPushButton("Choose model file…")
        self._choose_file_button.setObjectName("PrimaryButton")
        self._choose_file_button.setAccessibleName("Choose a GGUF or Safetensors model file")
        self._choose_file_button.clicked.connect(self._choose_file)

        self._choose_folder_button = QPushButton("Choose Hugging Face folder…")
        self._choose_folder_button.setObjectName("QuietButton")
        self._choose_folder_button.setAccessibleName("Choose a Hugging Face model folder")
        self._choose_folder_button.clicked.connect(self._choose_folder)

        self._inspect_button = QPushButton("Inspect model")
        self._inspect_button.setObjectName("PrimaryButton")
        self._inspect_button.setAccessibleName("Inspect the selected model")
        self._inspect_button.setEnabled(False)
        self._inspect_button.clicked.connect(self._start_inspection)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("DangerButton")
        self._cancel_button.setAccessibleName("Cancel the running inspection")
        self._cancel_button.setVisible(False)
        self._cancel_button.clicked.connect(self._cancel_inspection)

        button_row.addWidget(self._choose_file_button)
        button_row.addWidget(self._choose_folder_button)
        button_row.addWidget(self._inspect_button)
        button_row.addWidget(self._cancel_button)
        button_row.addStretch(1)
        source_layout.addLayout(button_row)

        self._status_label = QLabel(
            "No model selected. Choose a supported file or folder to begin."
        )
        self._status_label.setObjectName("StatusLine")
        self._status_label.setWordWrap(True)
        self._status_label.setAccessibleName("Inspection status")
        source_layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        self._progress.setAccessibleName("Inspection in progress")
        source_layout.addWidget(self._progress)

        add_text(
            source_layout,
            "Safety: headers and indexes only. No tensor payloads are read or mapped, source "
            "checkpoints are never modified, and no model code is executed.",
            "Faint",
        )
        layout.addWidget(source_card)

        self._results_layout = QVBoxLayout()
        self._results_layout.setSpacing(18)
        layout.addLayout(self._results_layout)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._show_empty(
            "No model inspected yet",
            "Choose a supported model source above, then select Inspect model. The resulting Atlas "
            "will show architecture, counts, storage, type distribution, warnings and evidence labels.",
        )

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a model file",
            "",
            "Model files (*.gguf *.safetensors);;GGUF files (*.gguf);;Safetensors files (*.safetensors);;All files (*)",
        )
        if path:
            self._set_source(Path(path))

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a Hugging Face model folder")
        if path:
            self._set_source(Path(path))

    def _set_source(self, path: Path) -> None:
        self._source = path
        self._last_atlas = None
        self._source_label.setText(path.name)
        self._status_label.setText("Ready to inspect the selected model.")
        self._inspect_button.setEnabled(True)
        self._show_empty(
            "Ready to inspect",
            "Select Inspect model to read headers and build the Atlas. The full local path is not "
            "included in the Atlas report.",
        )

    def _start_inspection(self) -> None:
        if self._worker is not None or self._source is None:
            return
        self._show_empty(
            "Inspecting headers…",
            "Reading the checkpoint header and tensor index. Large files should not freeze this "
            "window; use Cancel to stop.",
        )
        self._status_label.setObjectName("StatusLine")
        self._status_label.setStyleSheet("")
        self._status_label.setText("Inspecting the selected model…")
        self._set_running(True)

        worker = _InspectionWorker(self._client, self._source, self)
        self._worker = worker
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_failure)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(lambda: self._worker_finished(worker))
        worker.start()

    def _cancel_inspection(self) -> None:
        if self._worker is not None:
            self._status_label.setText("Cancelling inspection…")
            self._cancel_button.setEnabled(False)
            self._worker.cancel()

    def _worker_finished(self, worker: _InspectionWorker) -> None:
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _set_running(self, running: bool) -> None:
        self._choose_file_button.setEnabled(not running)
        self._choose_folder_button.setEnabled(not running)
        self._inspect_button.setEnabled(not running and self._source is not None)
        self._cancel_button.setVisible(running)
        self._cancel_button.setEnabled(running)
        self._progress.setVisible(running)

    def _on_success(self, document: dict[str, Any]) -> None:
        self._set_running(False)
        self._last_atlas = document
        self._status_label.setObjectName("SuccessText")
        self._status_label.setText(
            "Atlas ready. Static read-only inspection completed with 0 tensor payload bytes read."
        )
        self._render_atlas(document)

    def _on_failure(self, message: str) -> None:
        self._set_running(False)
        self._last_atlas = None
        self._status_label.setObjectName("StatusLine")
        self._status_label.setText("The model could not be inspected.")
        self._show_error(message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self._last_atlas = None
        self._status_label.setObjectName("StatusLine")
        self._status_label.setText("Inspection cancelled.")
        self._show_empty(
            "Inspection cancelled",
            "No Atlas was produced. You can choose the same model again and restart inspection.",
        )

    def _clear_results(self) -> None:
        clear_layout(self._results_layout)

    def _show_empty(self, title: str, body: str) -> None:
        self._clear_results()
        self._results_layout.addWidget(make_empty_card(title, body))

    def _show_error(self, message: str) -> None:
        self._clear_results()
        self._results_layout.addWidget(
            make_empty_card(
                "Inspection could not start or could not finish",
                "Check that the file or folder is a supported, complete model and try again.",
            )
        )
        error = QLabel(message)
        error.setObjectName("ErrorBox")
        error.setWordWrap(True)
        error.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._results_layout.addWidget(error)

    def apply_atlas(self, document: dict[str, Any]) -> None:
        """Render an already-validated Atlas. Used by the worker and UI tests."""

        self._last_atlas = document
        self._render_atlas(document)

    def _render_atlas(self, document: dict[str, Any]) -> None:
        self._clear_results()
        summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
        architecture = (
            document.get("architecture") if isinstance(document.get("architecture"), dict) else {}
        )
        evidence = document.get("evidence") if isinstance(document.get("evidence"), dict) else {}
        inspection = (
            document.get("inspection") if isinstance(document.get("inspection"), dict) else {}
        )
        components = (
            document.get("components") if isinstance(document.get("components"), dict) else {}
        )
        source_kind = document.get("source_kind")
        source_name = document.get("source_name")

        model_card, model_layout = make_card(
            "Model & architecture",
            "Only facts reported by the static inspectors are shown here.",
        )
        add_fact(
            model_layout,
            "Source",
            str(source_name) if source_name else "Unknown",
        )
        add_fact(model_layout, "Source type", source_kind_text(source_kind))
        add_fact(
            model_layout,
            "Architecture",
            str(architecture.get("architecture") or "Unknown"),
            architecture.get("evidence") or "unknown",
        )
        model_name = architecture.get("name")
        if model_name:
            add_fact(model_layout, "Model name", str(model_name))
        self._results_layout.addWidget(model_card)

        size_card, size_layout = make_card(
            "Parameters and storage",
            "Tensor element totals and checkpoint storage, with no inferred runtime performance.",
        )
        add_fact(
            size_layout,
            "Tensor count",
            human_count(summary.get("tensor_count")),
            "observed",
        )
        add_fact(
            size_layout,
            "Total parameters",
            human_count(summary.get("total_parameters")),
            summary.get("parameters_evidence"),
        )
        add_fact(
            size_layout,
            "Tensor storage",
            human_bytes(summary.get("total_storage_bytes")),
            summary.get("storage_evidence"),
        )
        add_fact(
            size_layout,
            "Storage coverage",
            completeness_text(summary.get("total_storage_is_complete")),
        )
        if summary.get("total_storage_is_complete") is not True:
            add_text(
                size_layout,
                "Some tensor storage could not be measured. Treat the total as partial until the "
                "warnings below are resolved.",
                "WarningText",
            )
        add_text(
            size_layout,
            "These values describe the checkpoint only. This build does not claim VRAM feasibility, "
            "inference speed, supported runtime behaviour or quality.",
            "Faint",
        )
        self._results_layout.addWidget(size_card)

        distribution = summary.get("distribution")
        distribution_card, distribution_layout = make_card(
            "Type / dtype distribution",
            "Tensor counts grouped by the label reported by the inspector.",
        )
        rows = distribution_rows(distribution)
        if rows:
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(8)
            for column, heading in enumerate(("Type", "Tensors", "Share")):
                label = QLabel(heading)
                label.setObjectName("Faint")
                grid.addWidget(label, 0, column)
            for index, (name, count, share) in enumerate(rows, start=1):
                name_label = QLabel(name)
                name_label.setObjectName("FactValue")
                count_label = QLabel(human_count(count))
                count_label.setObjectName("Muted")
                share_label = QLabel(f"{share * 100:.1f}%")
                share_label.setObjectName("Muted")
                grid.addWidget(name_label, index, 0)
                grid.addWidget(count_label, index, 1)
                grid.addWidget(share_label, index, 2)
            grid.setColumnStretch(0, 1)
            distribution_layout.addLayout(grid)
        else:
            add_text(distribution_layout, "No tensor types were reported.", "Muted")
        self._results_layout.addWidget(distribution_card)

        self._results_layout.addWidget(self._tokenizer_card(document))

        warnings_card, warnings_layout = make_card(
            "Warnings",
            "Limits, truncated data, unresolved tensor types and other inspector findings.",
        )
        warnings = [item for item in document.get("warnings", []) if isinstance(item, str)]
        if warnings:
            for warning in warnings:
                add_text(warnings_layout, warning, "WarningText")
        else:
            add_text(warnings_layout, "No warnings were reported.", "SuccessText")
        self._results_layout.addWidget(warnings_card)

        evidence_card, evidence_layout = make_card(
            "Evidence labels",
            "Observed values were read directly from the file. Derived values were calculated from "
            "a pinned registry. Unknown values were not measured or not recognised.",
        )
        for label, key in (
            ("Parameters", "parameters"),
            ("Storage", "storage_bytes"),
            ("Architecture", "architecture"),
            ("Tokenizer", "tokenizer"),
        ):
            value = evidence.get(key)
            add_fact(evidence_layout, label, evidence_text(value), value or "unknown")
        self._results_layout.addWidget(evidence_card)

        safety_card, safety_layout = make_card(
            "Inspection safety",
            "This build never loads tensor payloads, modifies the checkpoint, or executes model code.",
        )
        add_fact(
            safety_layout,
            "Mode",
            str(inspection.get("mode") or "unknown").replace("_", " "),
        )
        add_fact(
            safety_layout,
            "Tensor payload bytes read",
            human_count(inspection.get("tensor_payload_bytes_read")),
        )
        add_fact(
            safety_layout,
            "Tensor payloads loaded",
            "No" if inspection.get("tensor_payloads_loaded") is False else "Unknown",
        )
        add_fact(
            safety_layout,
            "Source modified",
            "No" if inspection.get("source_modified") is False else "Unknown",
        )
        self._results_layout.addWidget(safety_card)

        self._results_layout.addWidget(self._advanced_card(document, components, source_kind))

    def _tokenizer_card(self, document: dict[str, Any]) -> QWidget:
        tokenizer = document.get("tokenizer") if isinstance(document.get("tokenizer"), dict) else {}
        card, layout = make_card(
            "Tokenizer and chat format",
            "Facts read from the tokenizer's control files. Chat templates are shown as plain text "
            "and are never imported, compiled or run.",
        )
        if tokenizer.get("available") is not True:
            message = (
                tokenizer.get("note")
                or tokenizer.get("error")
                or "No tokenizer or chat-template files were found for this source."
            )
            add_text(layout, str(message), "Muted")
            return card

        class_name = tokenizer.get("class")
        add_fact(layout, "Tokenizer class", str(class_name) if class_name else "Unknown")
        vocab_size = tokenizer.get("vocab_size")
        add_fact(
            layout,
            "Vocabulary size",
            human_count(vocab_size) if vocab_size is not None else "Unknown",
            tokenizer.get("vocab_size_evidence") or "unknown",
        )
        model_type = tokenizer.get("tokenizer_model_type") or tokenizer.get("model_label")
        add_fact(layout, "Tokenizer model", str(model_type) if model_type else "Unknown")
        added = tokenizer.get("added_token_count")
        add_fact(
            layout,
            "Added tokens",
            human_count(added) if added is not None else "Unknown",
        )
        special = tokenizer.get("special_tokens")
        add_fact(
            layout,
            "Special tokens",
            _special_token_summary(special) or "None declared",
            _special_token_evidence(special),
        )

        templates = (
            tokenizer.get("chat_templates")
            if isinstance(tokenizer.get("chat_templates"), dict)
            else {}
        )
        count = templates.get("count")
        add_fact(
            layout,
            "Chat templates",
            human_count(count) if count is not None else "0",
            "observed" if count else "unknown",
        )
        default = templates.get("default")
        if isinstance(default, dict):
            add_fact(
                layout,
                "Default template",
                f"{default.get('origin')} ({str(default.get('kind') or 'unknown').replace('_', ' ')})",
            )

        details_layout = make_disclosure(layout)
        add_fact(details_layout, "Tokenizer source", str(tokenizer.get("source") or "Unknown"))
        add_fact(
            details_layout,
            "Vocabulary evidence",
            str(tokenizer.get("vocab_size_source") or "Unknown"),
        )
        candidates = tokenizer.get("vocab_size_candidates")
        if isinstance(candidates, dict) and candidates:
            detail = ", ".join(
                f"{key}={human_count(value)}" for key, value in sorted(candidates.items())
            )
            add_plain_text(details_layout, f"Vocabulary candidates: {detail}")

        for label, key in (
            ("Pre-tokenizer", "pre_tokenizer_type"),
            ("Decoder", "decoder_type"),
            ("Normalizer", "normalizer_type"),
            ("Padding side", "padding_side"),
            ("Truncation side", "truncation_side"),
        ):
            value = tokenizer.get(key)
            if value not in (None, ""):
                add_fact(details_layout, label, str(value))
        max_length = tokenizer.get("max_length")
        if max_length is not None:
            add_fact(details_layout, "Declared max length", human_count(max_length))

        source = tokenizer.get("source")
        _render_assets(details_layout, tokenizer.get("assets"))
        _render_templates(details_layout, templates.get("sources"))
        if source == "gguf_metadata":
            _render_gguf_fields(details_layout, tokenizer.get("fields"))

        warnings = [item for item in tokenizer.get("warnings", []) if isinstance(item, str)]
        if warnings:
            add_plain_text(details_layout, "Tokenizer warnings", "FactLabel")
            for warning in warnings:
                add_text(details_layout, warning, "WarningText")
        return card

    def _advanced_card(
        self,
        document: dict[str, Any],
        components: dict[str, Any],
        source_kind: Any,
    ) -> QWidget:
        frame, layout = make_card(
            "Advanced technical details",
            "Hidden by default. These values are not required to understand the model.",
        )
        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 6, 0, 0)
        details_layout.setSpacing(8)
        details.setVisible(False)

        toggle = QToolButton()
        toggle.setObjectName("Disclosure")
        toggle.setCheckable(True)
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        toggle.setText("Show technical details")
        toggle.setAccessibleName("Show or hide advanced technical details")

        def update_details(checked: bool) -> None:
            details.setVisible(checked)
            toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
            toggle.setText("Hide technical details" if checked else "Show technical details")

        toggle.toggled.connect(update_details)
        layout.addWidget(toggle)

        summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
        add_fact(details_layout, "Exact tensor storage", human_count(summary.get("total_storage_bytes")) + " bytes")

        if source_kind == "gguf":
            gguf = components.get("gguf") if isinstance(components.get("gguf"), dict) else {}
            add_fact(details_layout, "Format version", str(gguf.get("version", "Unknown")))
            add_fact(details_layout, "Byte order", str(gguf.get("endianness", "Unknown")))
            add_fact(details_layout, "File size", human_bytes(gguf.get("file_size_bytes")))
            add_fact(details_layout, "GGML registry revision", str(gguf.get("registry_revision", "Unknown")))
        elif source_kind == "safetensors":
            safetensors = (
                components.get("safetensors")
                if isinstance(components.get("safetensors"), dict)
                else {}
            )
            add_fact(details_layout, "File size", human_bytes(safetensors.get("file_size_bytes")))
            add_fact(details_layout, "Header length", human_bytes(safetensors.get("header_length_bytes")))
            add_fact(details_layout, "Tensor data region", human_bytes(safetensors.get("data_region_bytes")))
        elif source_kind == "huggingface_folder":
            folder = components.get("folder") if isinstance(components.get("folder"), dict) else {}
            add_fact(details_layout, "Shard count", human_count(folder.get("shard_count")))
            add_fact(details_layout, "Available shards", human_count(folder.get("available_shard_count")))
            add_fact(details_layout, "Missing shards", human_count(folder.get("missing_shard_count")))
            add_fact(details_layout, "Inspected shards", human_count(folder.get("inspected_shard_count")))

        layout.addWidget(details)
        return frame

    def shutdown(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait(5_000)