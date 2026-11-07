"""Prepare & Run: model registry, reversible preparation and inference lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from eclipse.core.hardware import detect_host_hardware
from eclipse.model_intelligence import build_model_atlas
from eclipse.model_intelligence.preparation import (
    PreparationError,
    find_quantize_tool,
    prepare_model,
    remove_prepared_package,
    verify_prepared_package,
)
from eclipse.runtime import (
    CancellationToken,
    ChatError,
    ChatMessage,
    ProfileSpec,
    intent_choices,
    last_known_good_profile,
    resolve_profile,
    run_benchmark,
)

from .context import AppContext
from .formatting import human_bytes, human_count
from .widgets import add_fact, add_plain_text, add_text, clear_layout, make_card, make_header


class _AtlasWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path

    def run(self) -> None:
        try:
            self.succeeded.emit(build_model_atlas(self.path))
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _RegisterWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, context: AppContext, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.path = path

    def run(self) -> None:
        try:
            atlas = build_model_atlas(self.path)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        summary = atlas.get("summary") or {}
        components = atlas.get("components") or {}
        size = None
        if isinstance(components.get("gguf"), dict):
            size = components["gguf"].get("file_size_bytes")
        model = self.context.store.add_model(
            name=str(atlas.get("source_name") or Path(self.path).name),
            source_path=str(Path(self.path).resolve()),
            source_kind=str(atlas.get("source_kind") or "unknown"),
            atlas=atlas,
            file_size_bytes=size if isinstance(size, int) else None,
            parameters=summary.get("total_parameters") if isinstance(summary.get("total_parameters"), int) else None,
            architecture=(atlas.get("architecture") or {}).get("architecture"),
        )
        self.succeeded.emit(model)


class _StartWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        context: AppContext,
        model: dict[str, Any],
        spec: dict[str, Any],
        prepared_path: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.model = model
        self.spec = spec
        self.prepared_path = prepared_path

    def run(self) -> None:
        try:
            result = self.context.runtime.start(self.model, self.spec, prepared_path=self.prepared_path)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.succeeded.emit({"status": result.status, "spec": result.spec, "warnings": result.warnings})


class _StopWorker(QThread):
    finished_with = Signal(dict)
    failed = Signal(str)

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context

    def run(self) -> None:
        try:
            self.finished_with.emit(self.context.runtime.stop())
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class _PrepareWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        context: AppContext,
        model: dict[str, Any],
        copy: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.model = model
        self.copy = copy

    def run(self) -> None:
        try:
            package = prepare_model(
                self.model["source_path"],
                self.context.paths.prepared_dir,
                mode="copy" if self.copy else "index",
                atlas=self.model.get("atlas") or None,
            )
            variant = self.context.store.add_variant(
                model_id=self.model["id"],
                name=package.directory.name,
                kind=package.manifest["method"]["mode"],
                path=str(package.directory),
                status=package.manifest["integrity"]["status"],
                manifest=package.manifest,
            )
            self.succeeded.emit(variant)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _TestWorker(QThread):
    delta = Signal(str)
    finished_with = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        context: AppContext,
        prompt: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.prompt = prompt
        self.cancel = CancellationToken()

    def run(self) -> None:
        try:
            parts: list[str] = []
            for chunk in self.context.runtime.stream_chat(
                [ChatMessage(role="user", content=self.prompt)], cancel=self.cancel
            ):
                if chunk.text:
                    parts.append(chunk.text)
                    self.delta.emit(chunk.text)
            runs = self.context.store.list_runs(limit=1)
            metrics = runs[0]["metrics"] if runs and runs[0]["kind"] == "generation" else {}
            self.finished_with.emit({"text": "".join(parts), "metrics": metrics})
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def stop(self) -> None:
        self.cancel.cancel()


class _BenchmarkWorker(QThread):
    finished_with = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        context: AppContext,
        prompt: str,
        runs: int = 3,
        warmup: int = 1,
        max_tokens: int = 32,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.prompt = prompt
        self.runs = runs
        self.warmup = warmup
        self.max_tokens = max_tokens

    def run(self) -> None:
        try:
            result = run_benchmark(
                self.context.runtime,
                prompt=self.prompt,
                runs=self.runs,
                warmup=self.warmup,
                max_tokens=self.max_tokens,
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            self.failed.emit(str(exc))
            return
        self.finished_with.emit(result)


class _VerifyWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path

    def run(self) -> None:
        try:
            package = verify_prepared_package(self.path)
            integrity = package.manifest.get("integrity") or {}
            self.succeeded.emit(
                {
                    "integrity": integrity,
                    "verified_files": len(integrity.get("verified_files") or []),
                }
            )
        except PreparationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ModelRuntimePanel(QWidget):
    """Real model loading, generation, preparation and telemetry."""

    status_changed = Signal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self._workers: list[QThread] = []
        self._test_worker: _TestWorker | None = None
        self._benchmark_worker: _BenchmarkWorker | None = None
        self._selected_model: dict[str, Any] | None = None
        self._register_worker: _RegisterWorker | None = None
        self._verify_worker: _VerifyWorker | None = None
        self.setObjectName("ModelRuntimePanel")
        self.setAccessibleName("Model preparation and inference")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("ResultsScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(44, 34, 44, 44)
        layout.setSpacing(18)

        layout.addWidget(
            make_header(
                "Prepare & run",
                "Register a model, create a reversible prepared package and manage a real "
                "inference process through a supported backend.",
            )
        )

        status_card, status_layout = make_card(
            "Runtime",
            "Every state below comes from the actual backend process.",
        )
        status_row = QHBoxLayout()
        self._state_label = QLabel("Not loaded")
        self._state_label.setObjectName("RuntimeState")
        self._state_detail = QLabel("No model is loaded.")
        self._state_detail.setObjectName("Muted")
        self._state_detail.setWordWrap(True)
        status_row.addWidget(self._state_label, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addWidget(self._state_detail, 1)
        status_layout.addLayout(status_row)

        buttons = QHBoxLayout()
        self._start_button = QPushButton("Load selected model")
        self._start_button.setObjectName("PrimaryButton")
        self._start_button.clicked.connect(self._start_runtime)
        self._restart_button = QPushButton("Restart")
        self._restart_button.clicked.connect(self._restart_runtime)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setObjectName("DangerButton")
        self._stop_button.clicked.connect(self._stop_runtime)
        self._stop_button.setEnabled(False)
        buttons.addWidget(self._start_button)
        buttons.addWidget(self._restart_button)
        buttons.addWidget(self._stop_button)
        buttons.addStretch(1)
        status_layout.addLayout(buttons)
        add_fact(status_layout, "Endpoint", "—")
        self._endpoint_label = status_layout.itemAt(status_layout.count() - 1).layout().itemAt(1).widget()  # type: ignore[union-attr]
        add_fact(status_layout, "Requested context", "—")
        self._context_label = status_layout.itemAt(status_layout.count() - 1).layout().itemAt(1).widget()  # type: ignore[union-attr]
        add_fact(status_layout, "Observed context", "—")
        self._observed_label = status_layout.itemAt(status_layout.count() - 1).layout().itemAt(1).widget()  # type: ignore[union-attr]
        self._log_label = add_plain_text(status_layout, "", "Faint")
        layout.addWidget(status_card)

        split = QSplitter()
        split.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        models_card, models_layout = make_card("Model registry", "Registered local models. Scanning is read-only.")
        self._model_list = QListWidget()
        self._model_list.setObjectName("ModelList")
        self._model_list.currentRowChanged.connect(self._on_model_selected)
        models_layout.addWidget(self._model_list)
        model_buttons = QHBoxLayout()
        self._register_file_button = QPushButton("Add file…")
        self._register_file_button.clicked.connect(self._choose_file)
        self._register_folder_button = QPushButton("Add folder…")
        self._register_folder_button.clicked.connect(self._choose_folder)
        model_buttons.addWidget(self._register_file_button)
        model_buttons.addWidget(self._register_folder_button)
        models_layout.addLayout(model_buttons)
        self._remove_button = QPushButton("Remove from registry")
        self._remove_button.clicked.connect(self._remove_model)
        self._remove_button.setEnabled(False)
        models_layout.addWidget(self._remove_button)
        left_layout.addWidget(models_card)

        variants_card, variants_layout = make_card(
            "Prepared variants",
            "Prepared packages never modify the original checkpoint.",
        )
        self._variant_list = QListWidget()
        variants_layout.addWidget(self._variant_list)
        prepare_row = QHBoxLayout()
        self._prepare_button = QPushButton("Prepare index")
        self._prepare_button.clicked.connect(lambda: self._prepare(copy=False))
        self._copy_button = QPushButton("Prepare copy")
        self._copy_button.clicked.connect(lambda: self._prepare(copy=True))
        prepare_row.addWidget(self._prepare_button)
        prepare_row.addWidget(self._copy_button)
        variants_layout.addLayout(prepare_row)
        variant_actions = QHBoxLayout()
        self._verify_button = QPushButton("Verify")
        self._verify_button.clicked.connect(self._verify_variant)
        self._rollback_button = QPushButton("Delete package")
        self._rollback_button.clicked.connect(self._delete_variant)
        variant_actions.addWidget(self._verify_button)
        variant_actions.addWidget(self._rollback_button)
        variants_layout.addLayout(variant_actions)
        self._quantize_button = QPushButton("Quantize GGUF…")
        self._quantize_button.clicked.connect(self._quantize)
        self._quantize_button.setEnabled(find_quantize_tool() is not None)
        if find_quantize_tool() is None:
            self._quantize_button.setToolTip("llama-quantize was not found on PATH")
        variants_layout.addWidget(self._quantize_button)
        left_layout.addWidget(variants_card)
        left_layout.addStretch(1)
        split.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        profile_card, profile_layout = make_card(
            "Execution profile",
            "Intent presets resolve to explicit settings. Backend support is declared, not assumed.",
        )
        form = QFormLayout()
        form.setSpacing(10)
        self._backend_combo = QComboBox()
        self._backend_combo.addItem("llama.cpp server (managed)", "llamacpp_server")
        self._backend_combo.addItem("OpenAI-compatible endpoint", "openai_compatible")
        self._backend_combo.currentIndexChanged.connect(self._backend_changed)
        form.addRow("Backend", self._backend_combo)
        self._intent_combo = QComboBox()
        for item in intent_choices():
            self._intent_combo.addItem(item["label"], item["value"])
            self._intent_combo.setItemData(self._intent_combo.count() - 1, item["description"], Qt.ItemDataRole.ToolTipRole)
        self._intent_combo.setCurrentIndex(1)
        form.addRow("Intent", self._intent_combo)
        self._context_spin = QSpinBox()
        self._context_spin.setRange(512, 1_048_576)
        self._context_spin.setSingleStep(1024)
        self._context_spin.setValue(8192)
        form.addRow("Context tokens", self._context_spin)
        self._gpu_layers = QSpinBox()
        self._gpu_layers.setRange(-1, 999)
        self._gpu_layers.setValue(-1)
        self._gpu_layers.setSpecialValueText("All layers")
        form.addRow("GPU layers", self._gpu_layers)
        self._threads = QSpinBox()
        self._threads.setRange(0, 128)
        self._threads.setValue(0)
        self._threads.setSpecialValueText("Auto")
        form.addRow("CPU threads", self._threads)
        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.setValue(0.7)
        form.addRow("Temperature", self._temperature)
        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(16, 32768)
        self._max_tokens.setValue(1024)
        form.addRow("Max reply tokens", self._max_tokens)
        self._endpoint_edit = QLineEdit()
        self._endpoint_edit.setPlaceholderText("http://127.0.0.1:8080")
        form.addRow("Endpoint URL", self._endpoint_edit)
        self._model_name_edit = QLineEdit()
        self._model_name_edit.setPlaceholderText("Optional served model name")
        form.addRow("Served model name", self._model_name_edit)
        self._binary_edit = QLineEdit()
        self._binary_edit.setPlaceholderText("Auto-discover llama-server")
        binary_row = QHBoxLayout()
        binary_row.addWidget(self._binary_edit, 1)
        browse_binary = QPushButton("Browse…")
        browse_binary.clicked.connect(self._choose_binary)
        binary_row.addWidget(browse_binary)
        form.addRow("llama-server", binary_row)
        profile_layout.addLayout(form)
        self._profile_note = add_text(profile_layout, "", "Faint")

        profile_row = QHBoxLayout()
        self._profile_combo = QComboBox()
        self._profile_combo.setObjectName("SavedProfileCombo")
        self._profile_combo.setAccessibleName("Saved execution profiles")
        self._profile_combo.setToolTip("Profiles are saved after a successful load and marked good after a successful generation.")
        self._apply_profile_button = QPushButton("Apply saved")
        self._apply_profile_button.clicked.connect(self._apply_saved_profile)
        self._save_profile_button = QPushButton("Save profile")
        self._save_profile_button.clicked.connect(self._save_current_profile)
        self._restore_profile_button = QPushButton("Restore last good")
        self._restore_profile_button.clicked.connect(self._restore_last_good)
        profile_row.addWidget(self._profile_combo, 1)
        profile_row.addWidget(self._apply_profile_button)
        profile_row.addWidget(self._save_profile_button)
        profile_row.addWidget(self._restore_profile_button)
        profile_layout.addLayout(profile_row)
        right_layout.addWidget(profile_card)

        telemetry_card, telemetry_layout = make_card(
            "Last measured generation",
            "Measured wall-clock stream telemetry. Missing sensors stay unknown.",
        )
        add_fact(telemetry_layout, "Time to first token", "—")
        self._ttft_label = telemetry_layout.itemAt(telemetry_layout.count() - 1).layout().itemAt(1).widget()  # type: ignore[union-attr]
        add_fact(telemetry_layout, "Tokens/second", "—")
        self._tps_label = telemetry_layout.itemAt(telemetry_layout.count() - 1).layout().itemAt(1).widget()  # type: ignore[union-attr]
        add_fact(telemetry_layout, "Completion tokens", "—")
        self._tokens_label = telemetry_layout.itemAt(telemetry_layout.count() - 1).layout().itemAt(1).widget()  # type: ignore[union-attr]
        add_fact(telemetry_layout, "Peak process memory", "—")
        self._memory_label = telemetry_layout.itemAt(telemetry_layout.count() - 1).layout().itemAt(1).widget()  # type: ignore[union-attr]
        right_layout.addWidget(telemetry_card)

        test_card, test_layout = make_card(
            "Quick generation test",
            "Runs through the same runtime and records real telemetry.",
        )
        self._test_prompt = QLineEdit()
        self._test_prompt.setPlaceholderText("Ask the loaded model something short…")
        self._test_prompt.returnPressed.connect(self._run_test)
        test_row = QHBoxLayout()
        test_row.addWidget(self._test_prompt, 1)
        self._test_button = QPushButton("Generate")
        self._test_button.clicked.connect(self._run_test)
        self._test_stop = QPushButton("Stop")
        self._test_stop.clicked.connect(self._stop_test)
        self._test_stop.setEnabled(False)
        test_row.addWidget(self._test_button)
        self._benchmark_button = QPushButton("Benchmark 3×")
        self._benchmark_button.setToolTip("Three measured runs plus one warm-up; this is not a quality score.")
        self._benchmark_button.clicked.connect(self._run_benchmark)
        test_row.addWidget(self._benchmark_button)
        test_row.addWidget(self._test_stop)
        test_layout.addLayout(test_row)
        self._test_output = QPlainTextEdit()
        self._test_output.setReadOnly(True)
        self._test_output.setMinimumHeight(150)
        test_layout.addWidget(self._test_output)
        right_layout.addWidget(test_card)
        right_layout.addStretch(1)
        split.addWidget(right)
        split.setSizes([420, 560])
        layout.addWidget(split)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._backend_changed()
        self.context.events.subscribe("runtime.state", self._on_runtime_event)
        self.context.events.subscribe("runtime.metrics", self._on_metrics_event)
        self.refresh_models()
        self.refresh_profiles()
        self._render_status()

    # -- model registry --------------------------------------------------

    def refresh_models(self) -> None:
        selected_id = self._selected_model["id"] if self._selected_model else None
        self._model_list.blockSignals(True)
        self._model_list.clear()
        models = self.context.store.list_models()
        current_row = -1
        for row, model in enumerate(models):
            item = QListWidgetItem(f"{model['name']}\n{model['source_kind']} · {human_bytes(model.get('file_size_bytes'))}")
            item.setData(Qt.ItemDataRole.UserRole, model["id"])
            self._model_list.addItem(item)
            if model["id"] == selected_id:
                current_row = row
        self._model_list.blockSignals(False)
        if current_row >= 0:
            self._model_list.setCurrentRow(current_row)
        elif models:
            self._model_list.setCurrentRow(0)
        else:
            self._selected_model = None
            self._on_model_selected(-1)

    def _on_model_selected(self, row: int) -> None:
        model_id = None
        if row >= 0:
            item = self._model_list.item(row)
            if item is not None:
                model_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_model = self.context.store.get_model(model_id) if model_id else None
        self._remove_button.setEnabled(self._selected_model is not None)
        self._prepare_button.setEnabled(self._selected_model is not None)
        self._copy_button.setEnabled(self._selected_model is not None)
        self._start_button.setEnabled(
            self._selected_model is not None or self._backend_combo.currentData() == "openai_compatible"
        )
        if self._selected_model is not None:
            self.context.settings.set("active_model_id", self._selected_model["id"])
            atlas = self._selected_model.get("atlas") or {}
            details = (atlas.get("architecture") or {}).get("details") or {}
            declared = details.get("context_length", {}).get("value") if isinstance(details, dict) else None
            if isinstance(declared, int) and declared > 0:
                self._context_spin.setValue(min(declared, 16384))
            self._profile_note.setText(
                f"{human_count((atlas.get('summary') or {}).get('total_parameters'))} parameters · "
                f"{human_bytes((atlas.get('summary') or {}).get('total_storage_bytes'))} on disk · "
                f"declared context {human_count(declared) if declared else 'unknown'}"
            )
            self.refresh_variants()
        else:
            self.refresh_variants()
        self.refresh_profiles()

    def refresh_profiles(self) -> None:
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        model_id = self._selected_model["id"] if self._selected_model else None
        profiles = self.context.store.list_profiles(model_id) if model_id else []
        for profile in profiles:
            marker = " · last good" if profile.get("last_known_good") else ""
            self._profile_combo.addItem(
                f"{profile['name']} ({profile['intent']}){marker}",
                profile["id"],
            )
        self._profile_combo.blockSignals(False)
        has_profiles = bool(profiles)
        self._apply_profile_button.setEnabled(has_profiles)
        self._restore_profile_button.setEnabled(
            any(profile.get("last_known_good") for profile in profiles)
        )
        self._save_profile_button.setEnabled(self._selected_model is not None)

    def _apply_record(self, record: dict[str, Any]) -> None:
        spec = ProfileSpec.from_payload(record.get("payload") or {})
        index = self._backend_combo.findData(spec.backend)
        if index >= 0:
            self._backend_combo.setCurrentIndex(index)
        intent_index = self._intent_combo.findData(spec.intent)
        if intent_index >= 0:
            self._intent_combo.setCurrentIndex(intent_index)
        self._context_spin.setValue(spec.context_tokens)
        self._gpu_layers.setValue(spec.gpu_layers)
        self._threads.setValue(spec.threads or 0)
        self._temperature.setValue(spec.temperature)
        self._max_tokens.setValue(spec.max_tokens)
        self._endpoint_edit.setText(spec.endpoint or "")
        self._model_name_edit.setText(spec.model_name or "")
        self._binary_edit.setText(spec.binary or "")
        self._profile_note.setText(
            f"Applied '{record['name']}'. Review the values, then Load selected model."
        )

    def _apply_saved_profile(self) -> None:
        profile_id = self._profile_combo.currentData()
        if not profile_id:
            return
        record = self.context.store.get_profile(str(profile_id))
        if record is None:
            QMessageBox.warning(self, "Profile", "The saved profile no longer exists.")
            self.refresh_profiles()
            return
        try:
            self._apply_record(record)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profile", str(exc))

    def _save_current_profile(self) -> None:
        if self._selected_model is None:
            return
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self,
            "Save profile",
            "Profile name",
            text=f"{self._selected_model['name']} · {self._intent_combo.currentData()}",
        )
        if not ok or not name.strip():
            return
        try:
            payload = self._profile_payload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profile", str(exc))
            return
        record = self.context.store.add_profile(
            name=name.strip(),
            intent=str(payload.get("intent") or "custom"),
            payload=payload,
            model_id=self._selected_model["id"],
        )
        self.refresh_profiles()
        index = self._profile_combo.findData(record["id"])
        if index >= 0:
            self._profile_combo.setCurrentIndex(index)

    def _restore_last_good(self) -> None:
        model_id = self._selected_model["id"] if self._selected_model else None
        record = last_known_good_profile(self.context.store, model_id or None)
        if record is None:
            QMessageBox.information(
                self,
                "Restore last good",
                "No profile has completed a successful generation yet.",
            )
            return
        try:
            self._apply_record(record)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profile", str(exc))

    def refresh_variants(self) -> None:
        self._variant_list.clear()
        verifying = self._verify_worker is not None and self._verify_worker.isRunning()
        if self._selected_model is None:
            self._verify_button.setEnabled(False)
            self._rollback_button.setEnabled(False)
            return
        variants = self.context.store.list_variants(self._selected_model["id"])
        for variant in variants:
            item = QListWidgetItem(
                f"{variant['kind']} · {variant['status']}\n{variant['name']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, variant["id"])
            self._variant_list.addItem(item)
        self._verify_button.setEnabled(bool(variants) and not verifying)
        self._rollback_button.setEnabled(bool(variants) and not verifying)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a model file", "", "Model files (*.gguf *.safetensors)"
        )
        if path:
            self._register(path)

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select a Hugging Face model folder")
        if path:
            self._register(path)

    def _register(self, path: str) -> None:
        worker = _RegisterWorker(self.context, path, self)
        self._register_worker = worker
        worker.succeeded.connect(self._registered)
        worker.failed.connect(self._show_error)
        worker.finished.connect(lambda: setattr(self, "_register_worker", None))
        self._register_file_button.setEnabled(False)
        self._register_folder_button.setEnabled(False)
        self._state_detail.setText("Inspecting the model headers and indexes…")
        worker.start()

    def _registered(self, model: dict[str, Any]) -> None:
        self._register_file_button.setEnabled(True)
        self._register_folder_button.setEnabled(True)
        self.refresh_models()
        self._state_detail.setText(f"Registered {model['name']}. Choose a profile and load it.")
        self.status_changed.emit()

    def _remove_model(self) -> None:
        if self._selected_model is None:
            return
        answer = QMessageBox.question(
            self,
            "Remove model",
            f"Remove '{self._selected_model['name']}' from the registry?\n"
            "The model file itself is never modified or deleted.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            if self.context.runtime.status.model_id == self._selected_model["id"]:
                self.context.runtime.stop()
            self.context.store.delete_model(self._selected_model["id"])
            self._selected_model = None
            self.refresh_models()
            self._render_status()

    # -- preparation -----------------------------------------------------

    def _prepare(self, *, copy: bool) -> None:
        if self._selected_model is None:
            return
        answer = QMessageBox.question(
            self,
            "Create prepared package",
            "This computes SHA-256 hashes for every checkpoint file and writes a "
            "manifest to the prepared store. The source is opened read-only.\n\n"
            + ("A full copy will also be created." if copy else "Only an index and manifest will be created."),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        worker = _PrepareWorker(self.context, self._selected_model, copy, self)
        worker.succeeded.connect(self._prepared)
        worker.failed.connect(self._show_error)
        self._prepare_button.setEnabled(False)
        self._copy_button.setEnabled(False)
        worker.start()

    def _prepared(self, variant: dict[str, Any]) -> None:
        self._prepare_button.setEnabled(True)
        self._copy_button.setEnabled(True)
        self.refresh_variants()
        QMessageBox.information(
            self,
            "Prepared",
            f"Created {variant['name']} ({variant['status']}).\n"
            "The original checkpoint was not modified.",
        )

    def _variant(self) -> dict[str, Any] | None:
        item = self._variant_list.currentItem()
        if item is None:
            return None
        variant_id = item.data(Qt.ItemDataRole.UserRole)
        return self.context.store.get_variant(variant_id)

    def _verify_variant(self) -> None:
        variant = self._variant()
        if variant is None or self._verify_worker is not None:
            return
        # Re-hashing a multi-gigabyte package on the GUI thread froze the window
        # for the whole check, so run it on a worker thread.
        self._verify_button.setEnabled(False)
        self._rollback_button.setEnabled(False)
        worker = _VerifyWorker(variant["path"], self)
        self._verify_worker = worker
        worker.succeeded.connect(self._verified)
        worker.failed.connect(self._verify_failed)
        worker.finished.connect(self._verify_finished)
        worker.start()

    def _verified(self, result: dict[str, Any]) -> None:
        integrity = result.get("integrity") or {}
        QMessageBox.information(
            self,
            "Prepared package",
            f"Integrity: {integrity.get('status')}\n"
            f"Files checked: {result.get('verified_files')}",
        )

    def _verify_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Integrity check failed", message)

    def _verify_finished(self) -> None:
        worker = self._verify_worker
        self._verify_worker = None
        if worker is not None:
            worker.deleteLater()
        self.refresh_variants()

    def _delete_variant(self) -> None:
        variant = self._variant()
        if variant is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete prepared package",
            "Delete this derived package? The original model file is not touched.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            remove_prepared_package(variant["path"], self.context.paths.prepared_dir)
        except PreparationError as exc:
            QMessageBox.warning(self, "Not removed", str(exc))
            return
        self.context.store.delete_variant(variant["id"])
        self.refresh_variants()

    def _quantize(self) -> None:
        if self._selected_model is None:
            return
        source = self._selected_model["source_path"]
        if not source.lower().endswith(".gguf"):
            QMessageBox.warning(self, "Quantization", "Select a GGUF model to quantize.")
            return
        from PySide6.QtWidgets import QInputDialog

        types = ["Q4_K_M", "Q4_K_S", "Q5_K_M", "Q6_K", "Q8_0", "Q3_K_M", "Q2_K"]
        quant, ok = QInputDialog.getItem(self, "Quantize GGUF", "Quantization type", types, 0, False)
        if not ok:
            return
        from eclipse.model_intelligence.preparation import quantize_gguf

        try:
            result = quantize_gguf(source, self.context.paths.prepared_dir, quant_type=quant)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Quantization failed", str(exc))
            return
        variant = self.context.store.add_variant(
            model_id=self._selected_model["id"],
            name=result.output_path.name,
            kind=f"quantized:{quant}",
            path=str(result.output_path.parent),
            status=result.manifest["integrity"]["status"],
            manifest=result.manifest,
        )
        self.refresh_variants()
        QMessageBox.information(
            self,
            "Quantized",
            f"Created {variant['name']}.\nQuality is unmeasured until an evaluation runs.",
        )

    # -- runtime ---------------------------------------------------------

    def _backend_changed(self) -> None:
        backend = self._backend_combo.currentData()
        managed = backend == "llamacpp_server"
        self._endpoint_edit.setEnabled(not managed)
        self._model_name_edit.setEnabled(not managed)
        self._gpu_layers.setEnabled(managed)
        self._threads.setEnabled(managed)
        self._binary_edit.setEnabled(managed)
        self._start_button.setEnabled(
            (self._selected_model is not None and managed) or not managed
        )

    def _choose_binary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select llama-server executable")
        if path:
            self._binary_edit.setText(path)

    def _profile_payload(self) -> dict[str, Any]:
        backend = str(self._backend_combo.currentData())
        overrides: dict[str, Any] = {
            "context_tokens": self._context_spin.value(),
            "gpu_layers": self._gpu_layers.value(),
            "threads": self._threads.value() or None,
            "temperature": self._temperature.value(),
            "max_tokens": self._max_tokens.value(),
            "extra_args": [],
        }
        if backend == "openai_compatible":
            overrides["endpoint"] = self._endpoint_edit.text().strip()
            overrides["model_name"] = self._model_name_edit.text().strip() or None
        elif self._binary_edit.text().strip():
            overrides["binary"] = self._binary_edit.text().strip()
        atlas = (self._selected_model or {}).get("atlas") or {}
        try:
            host = detect_host_hardware().to_dict()
        except Exception:  # noqa: BLE001 - host probing is optional
            host = {}
        spec = resolve_profile(
            intent=str(self._intent_combo.currentData()),
            backend=backend,
            atlas=atlas,
            host=host,
            settings=self.context.settings,
            overrides=overrides,
        )
        return spec.to_payload()

    def _start_runtime(self) -> None:
        backend = str(self._backend_combo.currentData())
        if backend == "openai_compatible":
            model = self._selected_model or {
                "id": None,
                "name": self._model_name_edit.text().strip() or "external endpoint",
                "source_path": "",
                "source_kind": "remote",
                "atlas": {},
            }
        else:
            if self._selected_model is None:
                QMessageBox.information(self, "No model", "Register and select a model first.")
                return
            model = self._selected_model
        try:
            spec = self._profile_payload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profile", str(exc))
            return
        prepared_path = None
        variant = self._variant()
        if variant is not None and variant["status"] == "verified" and self._selected_model:
            manifest = variant.get("manifest") or {}
            if manifest.get("method", {}).get("mode") == "copy":
                output_root = manifest.get("identity", {}).get("output_root") or ""
                candidate = Path(variant["path"]) / output_root
                if candidate.exists():
                    prepared_path = str(candidate)
        self._state_detail.setText("Starting the backend…")
        self._start_button.setEnabled(False)
        worker = _StartWorker(self.context, model, spec, prepared_path, self)
        worker.succeeded.connect(self._started)
        worker.failed.connect(self._start_failed)
        worker.finished.connect(lambda: self._start_button.setEnabled(True))
        worker.start()

    def _started(self, payload: dict[str, Any]) -> None:
        warnings = payload.get("warnings") or []
        applied = payload.get("applied", True)
        self.refresh_profiles()
        self._render_status()
        if not applied:
            self._state_detail.setText(
                "Settings not applied. "
                + ("; ".join(warnings) if warnings else "Restart the runtime to apply them.")
            )
        elif warnings:
            self._state_detail.setText(f"{self._state_detail.text()} {'; '.join(warnings)}")
        else:
            self._state_detail.setText("Ready. The backend accepted the load.")
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self.status_changed.emit()

    def _start_failed(self, message: str) -> None:
        self._render_status()
        QMessageBox.critical(self, "Model load failed", message)
        self.status_changed.emit()

    def _stop_runtime(self) -> None:
        self._stop_button.setEnabled(False)
        worker = _StopWorker(self.context, self)
        worker.finished_with.connect(lambda _payload: self._after_stop())
        worker.failed.connect(self._show_error)
        worker.start()
        self._stop_worker = worker

    def _after_stop(self) -> None:
        self._render_status()
        self._start_button.setEnabled(True)
        self.status_changed.emit()

    def _restart_runtime(self) -> None:
        if self.context.runtime.status.state.value == "not_loaded":
            self._start_runtime()
            return
        model = self.context.active_model() or self._selected_model
        if model is None:
            QMessageBox.information(self, "Restart", "No loaded model to restart.")
            return
        try:
            spec = self._profile_payload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profile", str(exc))
            return
        self._stop_runtime()
        if getattr(self, "_restart_unsubscribe", None) is not None:
            self._restart_unsubscribe()
        self._restart_unsubscribe = self.context.events.subscribe(
            "runtime.state",
            lambda event: self._start_after_restart(event, model, spec),
        )

    def _start_after_restart(self, event: Any, model: dict[str, Any], spec: dict[str, Any]) -> None:
        if event.payload.get("state") == "not_loaded":
            unsubscribe = getattr(self, "_restart_unsubscribe", None)
            self._restart_unsubscribe = None
            if unsubscribe is not None:
                unsubscribe()
            worker = _StartWorker(self.context, model, spec, None, self)
            worker.succeeded.connect(self._started)
            worker.failed.connect(self._start_failed)
            worker.start()

    def _render_status(self) -> None:
        status = self.context.runtime.status
        label = {
            "not_loaded": "Not loaded",
            "preparing": "Preparing",
            "starting": "Starting",
            "loading": "Loading",
            "ready": "Ready",
            "generating": "Generating",
            "stopping": "Stopping",
            "unloading": "Unloading",
            "restart_required": "Restart required",
            "failed": "Failed",
            "needs_attention": "Needs attention",
        }.get(status.state.value, status.state.value.title())
        self._state_label.setText(label)
        self._state_label.setProperty("runtime", status.state.value)
        self._state_label.style().unpolish(self._state_label)
        self._state_label.style().polish(self._state_label)
        detail = status.detail or ""
        if status.error:
            detail = f"{detail} ({status.error})"
        self._state_detail.setText(detail)
        self._endpoint_label.setText(status.endpoint or "—")
        self._context_label.setText(human_count(status.requested_context))
        self._observed_label.setText(
            human_count(status.observed_context)
            if status.observed_context is not None
            else "Unknown — backend did not report it"
        )
        self._log_label.setText(f"Log: {status.log_path}" if status.log_path else "")
        running = status.state.value in {"ready", "generating", "restart_required"}
        self._stop_button.setEnabled(running or status.state.value in {"starting", "loading"})
        self._test_button.setEnabled(running)
        self._benchmark_button.setEnabled(running)
        self._test_prompt.setEnabled(running)
        self._start_button.setEnabled(not running and status.state.value != "loading")

    def _on_runtime_event(self, event: Any) -> None:
        self._render_status()

    def _on_metrics_event(self, event: Any) -> None:
        metrics = event.payload.get("metrics") or {}
        self._render_metrics(metrics, event.payload.get("resources") or {})

    def _render_metrics(self, metrics: dict[str, Any], resources: dict[str, Any]) -> None:
        ttft = metrics.get("time_to_first_token_seconds")
        tps = metrics.get("tokens_per_second")
        completion = metrics.get("completion_tokens")
        peak = (resources.get("process") or {}).get("resident_bytes")
        if peak is None:
            peak = (resources.get("samples") or {}).get("peak_process_resident_bytes")
        self._ttft_label.setText(f"{ttft:.3f} s" if isinstance(ttft, (int, float)) else "Unknown")
        self._tps_label.setText(
            f"{tps:.2f} tok/s (measured)" if isinstance(tps, (int, float)) else "Unknown — token count not reported"
        )
        self._tokens_label.setText(human_count(completion) if isinstance(completion, int) else "Unknown")
        self._memory_label.setText(human_bytes(peak) if isinstance(peak, int) else "Unknown")

    # -- generation test -------------------------------------------------

    def _run_test(self) -> None:
        prompt = self._test_prompt.text().strip()
        if not prompt:
            return
        if self._test_worker is not None:
            return
        self._test_output.clear()
        self._test_output.setPlainText("")
        self._test_button.setEnabled(False)
        self._test_stop.setEnabled(True)
        worker = _TestWorker(self.context, prompt, self)
        self._test_worker = worker
        worker.delta.connect(self._test_output.insertPlainText)
        worker.finished_with.connect(self._test_finished)
        worker.failed.connect(self._test_failed)
        worker.finished.connect(self._test_cleanup)
        worker.start()

    def _test_finished(self, payload: dict[str, Any]) -> None:
        self._render_metrics(payload.get("metrics") or {}, {})
        runs = self.context.store.list_runs(limit=1)
        if runs:
            metrics = (runs[0].get("metrics") or {})
            self._render_metrics(metrics, metrics.get("resources") or {})
        self.refresh_profiles()

    # -- benchmark -------------------------------------------------------

    def _run_benchmark(self) -> None:
        if self._test_worker is not None or self._benchmark_worker is not None:
            return
        prompt = self._test_prompt.text().strip() or "Reply with one short sentence confirming you are ready."
        self._test_output.setPlainText("Running one warm-up and three measured generations…")
        self._test_button.setEnabled(False)
        self._benchmark_button.setEnabled(False)
        self._test_stop.setEnabled(False)
        worker = _BenchmarkWorker(self.context, prompt, parent=self)
        self._benchmark_worker = worker
        worker.finished_with.connect(self._benchmark_finished)
        worker.failed.connect(self._benchmark_failed)
        worker.finished.connect(self._benchmark_cleanup)
        worker.start()

    def _benchmark_finished(self, result: dict[str, Any]) -> None:
        summary = result.get("summary") or {}
        ttft = summary.get("time_to_first_token_seconds") or {}
        tps = summary.get("tokens_per_second") or {}
        total = summary.get("total_seconds") or {}
        self._render_metrics(
            {
                "time_to_first_token_seconds": ttft.get("median"),
                "tokens_per_second": tps.get("median"),
                "completion_tokens": (summary.get("completion_tokens") or {}).get("median"),
            },
            {},
        )
        self._test_output.setPlainText(
            f"Benchmark {result.get('status')}: {len(result.get('samples') or [])} samples\n"
            f"TTFT median {ttft.get('median')} s (range {ttft.get('min')}–{ttft.get('max')})\n"
            f"Tokens/s median {tps.get('median')} (stdev {tps.get('stdev')})\n"
            f"Total median {total.get('median')} s\n\n{result.get('note', '')}"
        )
        self.refresh_profiles()

    def _benchmark_failed(self, message: str) -> None:
        self._test_output.setPlainText(f"Benchmark failed: {message}")

    def _benchmark_cleanup(self) -> None:
        self._benchmark_worker = None
        self._test_button.setEnabled(True)
        self._benchmark_button.setEnabled(True)

    def _test_failed(self, message: str) -> None:
        self._test_output.setPlainText(f"Generation failed: {message}")

    def _stop_test(self) -> None:
        if self._test_worker is not None:
            self._test_worker.stop()
            self._test_stop.setEnabled(False)

    def _test_cleanup(self) -> None:
        self._test_worker = None
        self._test_button.setEnabled(True)
        self._benchmark_button.setEnabled(True)
        self._test_stop.setEnabled(False)

    # -- misc ------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self._register_file_button.setEnabled(True)
        self._register_folder_button.setEnabled(True)
        self._prepare_button.setEnabled(self._selected_model is not None)
        self._copy_button.setEnabled(self._selected_model is not None)
        QMessageBox.warning(self, "ECLIPSE", message)

    def shutdown(self) -> None:
        worker = self._test_worker
        if worker is not None:
            worker.stop()
            worker.wait(3000)
        if self._benchmark_worker is not None:
            self._benchmark_worker.wait(5000)
        if self._register_worker is not None:
            self._register_worker.wait(5000)
        if self._verify_worker is not None:
            self._verify_worker.wait(5000)
