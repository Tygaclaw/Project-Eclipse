"""CLI commands for the complete ECLIPSE application.

These commands exercise the same Core used by the desktop: registry,
preparation, runtime lifecycle, capability tasks, knowledge and corrections.
They exist for automation, diagnostics and honest end-to-end verification.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from eclipse.agent import AgentService
from eclipse.capability import (
    CapabilityEngine,
    CorrectionMemory,
    KnowledgeBase,
    KnowledgeError,
    classify_task,
    default_checks,
)
from eclipse.capability.memory import MemoryError
from eclipse.core.config import AppPaths, Settings
from eclipse.core.events import EventBus
from eclipse.core.storage import Store
from eclipse.model_intelligence import build_model_atlas
from eclipse.model_intelligence.preparation import (
    PreparationError,
    find_quantize_tool,
    prepare_model,
    prepared_summary,
    quantize_gguf,
    remove_prepared_package,
    verify_prepared_package,
)
from eclipse.runtime import (
    CancellationToken,
    ChatMessage,
    RuntimeManager,
    intent_choices,
    resolve_profile,
    support_matrix_report,
)
from eclipse.core.hardware import detect_host_hardware


class CliError(Exception):
    """An expected command failure with a user-facing message."""


@dataclass
class CliApp:
    paths: AppPaths
    settings: Settings
    store: Store
    events: EventBus
    runtime: RuntimeManager
    knowledge: KnowledgeBase
    memory: CorrectionMemory
    capability: CapabilityEngine
    agent: AgentService
    workspace: str | None

    def close(self) -> None:
        self.runtime.shutdown()
        self.store.close()


def open_app(args: argparse.Namespace) -> CliApp:
    root = getattr(args, "home", None)
    paths = AppPaths.discover(root).ensure()
    settings = Settings(paths.settings_path)
    store = Store(paths.database_path)
    events = EventBus()
    runtime = RuntimeManager(store, settings, paths, events=events)
    knowledge = KnowledgeBase(paths.knowledge_dir, store)
    knowledge.ensure_vault()
    memory = CorrectionMemory(store)
    workspace = getattr(args, "workspace", None) or os.getcwd()
    capability = CapabilityEngine(
        store, runtime, paths, events=events, memory=memory, knowledge=knowledge, workspace_root=workspace
    )
    agent = AgentService(
        store,
        runtime,
        paths,
        events=events,
        knowledge=knowledge,
        memory=memory,
        workspace_root=workspace,
    )
    return CliApp(
        paths=paths,
        settings=settings,
        store=store,
        events=events,
        runtime=runtime,
        knowledge=knowledge,
        memory=memory,
        capability=capability,
        agent=agent,
        workspace=workspace,
    )


def cli_approver(auto_approve: bool):
    def approve(action: str, target: str, detail: str) -> bool:
        if auto_approve:
            print(f"[approved] {action}: {target}", file=sys.stderr)
            return True
        if not sys.stdin.isatty():
            print(f"[denied] {action}: {target} (no interactive approval available)", file=sys.stderr)
            return False
        answer = input(f"Approve {action}?\n  {target}\n  {detail}\n[y/N] ").strip().lower()
        return answer in {"y", "yes"}

    return approve


# -- command registration -------------------------------------------------


def register_commands(subparsers: Any) -> None:
    backends = subparsers.add_parser("backends", help="show the inference backend support matrix")
    backends.add_argument("--compact", action="store_true")

    registry_add = subparsers.add_parser("registry-add", help="inspect and register a model in the shared registry")
    registry_add.add_argument("path")
    registry_add.add_argument("--name")
    registry_add.add_argument("--compact", action="store_true")

    registry_list = subparsers.add_parser("registry-list", help="list registered models and variants")
    registry_list.add_argument("--compact", action="store_true")

    prepare = subparsers.add_parser("prepare", help="create a reversible prepared package with SHA-256 lineage")
    prepare.add_argument("path")
    prepare.add_argument("--copy", action="store_true", help="copy the checkpoint into the prepared store")
    prepare.add_argument("--name")
    prepare.add_argument("--register", action="store_true", help="also register the source model")
    prepare.add_argument("--compact", action="store_true")

    verify_package = subparsers.add_parser("verify-package", help="recompute hashes for a prepared package")
    verify_package.add_argument("directory")

    quantize = subparsers.add_parser("quantize", help="run llama-quantize when the tool is installed")
    quantize.add_argument("path")
    quantize.add_argument("--type", default="Q4_K_M")
    quantize.add_argument("--compact", action="store_true")

    chat = subparsers.add_parser("chat", help="load a model or attach an endpoint and send one prompt")
    chat.add_argument("--prompt", required=True)
    chat.add_argument("--system")
    chat.add_argument("--model-id")
    chat.add_argument("--gguf")
    chat.add_argument("--endpoint")
    chat.add_argument("--model-name")
    chat.add_argument("--backend", choices=("llamacpp_server", "openai_compatible"))
    chat.add_argument("--intent", default="balanced", choices=tuple(item["value"] for item in intent_choices()))
    chat.add_argument("--context", type=int)
    chat.add_argument("--gpu-layers", type=int)
    chat.add_argument("--temperature", type=float)
    chat.add_argument("--max-tokens", type=int)
    chat.add_argument("--server-binary")
    chat.add_argument("--no-stream", action="store_true")
    chat.add_argument("--json", action="store_true")

    task = subparsers.add_parser("task", help="create or run a capability task")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_new = task_sub.add_parser("new", help="create a plan without running it")
    task_new.add_argument("goal")
    task_new.add_argument("--mode", default="auto", choices=("auto", "fast", "balanced", "enhanced"))
    task_new.add_argument("--workspace")
    task_new.add_argument("--compact", action="store_true")
    task_run = task_sub.add_parser("run", help="plan, execute and verify a task")
    task_run.add_argument("goal")
    task_run.add_argument("--mode", default="auto", choices=("auto", "fast", "balanced", "enhanced"))
    task_run.add_argument("--workspace")
    task_run.add_argument("--yes", action="store_true", help="approve scoped writes and commands")
    task_run.add_argument("--compact", action="store_true")
    task_list = task_sub.add_parser("list")
    task_list.add_argument("--compact", action="store_true")

    knowledge = subparsers.add_parser("knowledge", help="inspect and maintain the Obsidian vault")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command", required=True)
    k_list = knowledge_sub.add_parser("list")
    k_list.add_argument("--status")
    k_list.add_argument("--compact", action="store_true")
    k_search = knowledge_sub.add_parser("search")
    k_search.add_argument("query")
    k_search.add_argument("--compact", action="store_true")
    k_propose = knowledge_sub.add_parser("propose")
    k_propose.add_argument("--title", required=True)
    k_propose.add_argument("--body", required=True)
    k_propose.add_argument("--source", default="cli")
    k_read = knowledge_sub.add_parser("read")
    k_read.add_argument("note_id")
    k_approve = knowledge_sub.add_parser("approve")
    k_approve.add_argument("note_id")
    k_approve.add_argument("--folder", required=True)
    k_approve.add_argument("--verification", default="")
    k_reject = knowledge_sub.add_parser("reject")
    k_reject.add_argument("note_id")
    k_reject.add_argument("--reason", default="")

    corrections = subparsers.add_parser("corrections", help="verified correction memory")
    corrections_sub = corrections.add_subparsers(dest="corrections_command", required=True)
    c_list = corrections_sub.add_parser("list")
    c_list.add_argument("--status")
    c_list.add_argument("--compact", action="store_true")
    c_propose = corrections_sub.add_parser("propose")
    c_propose.add_argument("--title", required=True)
    c_propose.add_argument("--issue", required=True)
    c_propose.add_argument("--root-cause", required=True)
    c_propose.add_argument("--fix", required=True)
    c_propose.add_argument("--scope", required=True)
    c_promote = corrections_sub.add_parser("promote")
    c_promote.add_argument("correction_id")
    c_promote.add_argument("--evidence", required=True)
    c_promote.add_argument("--regression", required=True)

    status = subparsers.add_parser("app-status", help="show the complete application status")
    status.add_argument("--compact", action="store_true")

    diagnostics = subparsers.add_parser("diagnostics", help="runtime and environment diagnostics")
    diagnostics.add_argument("--compact", action="store_true")

    checks = subparsers.add_parser("detect-checks", help="show the verification commands for a workspace")
    checks.add_argument("--workspace")
    checks.add_argument("--compact", action="store_true")


# -- dispatch -------------------------------------------------------------


def dispatch(args: argparse.Namespace) -> int | None:
    command = args.command
    handlers = {
        "backends": _cmd_backends,
        "registry-add": _cmd_registry_add,
        "registry-list": _cmd_registry_list,
        "prepare": _cmd_prepare,
        "verify-package": _cmd_verify_package,
        "quantize": _cmd_quantize,
        "chat": _cmd_chat,
        "task": _cmd_task,
        "knowledge": _cmd_knowledge,
        "corrections": _cmd_corrections,
        "app-status": _cmd_status,
        "diagnostics": _cmd_diagnostics,
        "detect-checks": _cmd_detect_checks,
    }
    handler = handlers.get(command)
    if handler is None:
        return None
    try:
        return handler(args)
    except CliError as exc:
        print(f"ECLIPSE: {exc}", file=sys.stderr)
        return 2
    except (OSError, MemoryError, KnowledgeError, ValueError, RuntimeError) as exc:
        print(f"ECLIPSE: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def _emit(payload: Any, compact: bool) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=None if compact else 2, allow_nan=False))


def _register_model(app: CliApp, path: str, name: str | None = None) -> dict[str, Any]:
    atlas = build_model_atlas(path)
    summary = atlas.get("summary", {})
    existing = next(
        (model for model in app.store.list_models() if model["source_path"] == str(Path(path).resolve())),
        None,
    )
    if existing is not None:
        return existing
    architecture = (atlas.get("architecture") or {}).get("architecture")
    return app.store.add_model(
        name=name or str(atlas.get("source_name") or Path(path).name),
        source_path=str(Path(path).resolve()),
        source_kind=str(atlas.get("source_kind") or "unknown"),
        file_size_bytes=(atlas.get("components") or {}).get("gguf", {}).get("file_size_bytes"),
        parameters=summary.get("total_parameters"),
        architecture=architecture,
        atlas=atlas,
    )


def _cmd_backends(args: argparse.Namespace) -> int:
    _emit(support_matrix_report(), args.compact)
    return 0


def _cmd_registry_add(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        model = _register_model(app, args.path, args.name)
        _emit(model, args.compact)
        return 0
    finally:
        app.close()


def _cmd_registry_list(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        models = app.store.list_models()
        for model in models:
            model["variants"] = app.store.list_variants(model["id"])
        _emit({"models": models, "count": len(models)}, args.compact)
        return 0
    finally:
        app.close()


def _cmd_prepare(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        package = prepare_model(
            args.path,
            app.paths.prepared_dir,
            mode="copy" if args.copy else "index",
            name=args.name,
        )
        record = {
            "package": prepared_summary(package.directory),
            "manifest": package.manifest,
        }
        if args.register:
            model = _register_model(app, str(Path(args.path).resolve()))
            variant = app.store.add_variant(
                model_id=model["id"],
                name=package.directory.name,
                kind=package.manifest["method"]["mode"],
                path=str(package.directory),
                status=package.manifest["integrity"]["status"],
                manifest=package.manifest,
            )
            record["model_id"] = model["id"]
            record["variant_id"] = variant["id"]
        _emit(record, args.compact)
        return 0
    finally:
        app.close()


def _cmd_verify_package(args: argparse.Namespace) -> int:
    try:
        package = verify_prepared_package(args.directory)
    except PreparationError as exc:
        raise CliError(str(exc)) from exc
    _emit(package.to_dict(), False)
    return 0


def _cmd_quantize(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        if find_quantize_tool() is None:
            raise CliError(
                "llama-quantize was not found on PATH. Install llama.cpp to enable quantization."
            )
        result = quantize_gguf(args.path, app.paths.prepared_dir, quant_type=args.type)
        _emit(
            {
                "output": str(result.output_path),
                "manifest": result.manifest,
            },
            args.compact,
        )
        return 0
    finally:
        app.close()


def _profile_for_chat(app: CliApp, args: argparse.Namespace, model: Mapping[str, Any] | None):
    overrides: dict[str, Any] = {}
    if args.context:
        overrides["context_tokens"] = args.context
    if args.gpu_layers is not None:
        overrides["gpu_layers"] = args.gpu_layers
    if args.temperature is not None:
        overrides["temperature"] = args.temperature
    if args.max_tokens is not None:
        overrides["max_tokens"] = args.max_tokens
    if args.endpoint:
        overrides["endpoint"] = args.endpoint
    if args.model_name:
        overrides["model_name"] = args.model_name
    if args.server_binary:
        overrides["binary"] = args.server_binary
    atlas = (model or {}).get("atlas") or {}
    if not atlas and isinstance(model, Mapping) and model.get("source_kind"):
        atlas = {"source_kind": model["source_kind"]}
    backend = args.backend or ("openai_compatible" if args.endpoint else "llamacpp_server")
    host = detect_host_hardware().to_dict()
    return resolve_profile(
        intent=args.intent,
        backend=backend,
        atlas=atlas,
        host=host,
        settings=app.settings,
        overrides=overrides,
    )


def _cmd_chat(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        model = None
        prepared_path = None
        if args.model_id:
            model = app.store.get_model(args.model_id)
            if model is None:
                raise CliError("No registered model has that id")
            variants = [item for item in app.store.list_variants(model["id"]) if item["status"] == "verified"]
            if variants:
                from eclipse.model_intelligence.preparation import load_manifest

                manifest = load_manifest(variants[0]["path"])
                output_root = manifest["identity"].get("output_root") or ""
                if manifest.get("method", {}).get("mode") == "copy":
                    prepared_path = str(Path(variants[0]["path"]) / output_root)
        elif args.gguf:
            model = _register_model(app, args.gguf)
        elif args.endpoint:
            model = {
                "id": None,
                "name": args.model_name or "external endpoint",
                "source_path": "",
                "source_kind": "remote",
                "atlas": {},
            }
        else:
            raise CliError("Provide --model-id, --gguf or --endpoint")
        spec = _profile_for_chat(app, args, model)
        app.runtime.start(model, spec.to_payload(), prepared_path=prepared_path)
        messages = []
        if args.system:
            messages.append(ChatMessage(role="system", content=args.system))
        messages.append(ChatMessage(role="user", content=args.prompt))
        parts: list[str] = []
        for chunk in app.runtime.stream_chat(messages, emit_deltas=False):
            if chunk.text:
                parts.append(chunk.text)
                if not args.no_stream and not args.json:
                    print(chunk.text, end="", flush=True)
        answer = "".join(parts)
        if not args.no_stream and not args.json:
            print()
        runs = app.store.list_runs(limit=10)
        generation_run = next((item for item in runs if item["kind"] == "generation"), None)
        metrics = generation_run["metrics"] if generation_run is not None else {}
        if args.json:
            _emit(
                {
                    "answer": answer,
                    "profile": spec.to_payload(),
                    "status": app.runtime.status.to_dict(),
                    "metrics": metrics,
                },
                False,
            )
        else:
            print(
                f"\n[state={app.runtime.status.state.value} "
                f"context_requested={spec.context_tokens} "
                f"context_observed={app.runtime.status.observed_context} "
                f"ttft={metrics.get('time_to_first_token_seconds')}s "
                f"tokens_per_second={metrics.get('tokens_per_second')}]",
                file=sys.stderr,
            )
        return 0
    finally:
        app.close()


def _cmd_task(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        if args.task_command == "list":
            _emit({"tasks": app.store.list_tasks()}, args.compact)
            return 0
        workspace = args.workspace or app.workspace
        if not workspace:
            raise CliError("A --workspace folder is required")
        task = app.capability.create_task(args.goal, mode=args.mode, workspace_root=workspace)
        if args.task_command == "new":
            _emit(task, args.compact)
            return 0
        approver = cli_approver(args.yes)
        run = app.capability.run_task(task["id"], approver=approver)
        _emit(run.to_dict(), args.compact)
        return 0 if run.status == "completed" else 1
    finally:
        app.close()


def _cmd_knowledge(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        if args.knowledge_command == "list":
            _emit({"notes": app.knowledge.list_notes(status=args.status)}, args.compact)
        elif args.knowledge_command == "search":
            _emit({"hits": app.knowledge.search(args.query)}, args.compact)
        elif args.knowledge_command == "propose":
            note = app.knowledge.propose_note(title=args.title, body=args.body, source=args.source)
            _emit(note, False)
        elif args.knowledge_command == "read":
            _emit(app.knowledge.read_note(args.note_id), False)
        elif args.knowledge_command == "approve":
            _emit(
                app.knowledge.approve_note(
                    args.note_id, target_folder=args.folder, verification=args.verification
                ),
                False,
            )
        elif args.knowledge_command == "reject":
            _emit(app.knowledge.reject_note(args.note_id, reason=args.reason), False)
        return 0
    finally:
        app.close()


def _cmd_corrections(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        if args.corrections_command == "list":
            _emit({"corrections": app.store.list_corrections(status=args.status)}, args.compact)
        elif args.corrections_command == "propose":
            _emit(
                app.memory.propose(
                    title=args.title,
                    issue=args.issue,
                    root_cause=args.root_cause,
                    fix=args.fix,
                    scope=args.scope,
                ),
                False,
            )
        elif args.corrections_command == "promote":
            _emit(
                app.memory.promote(
                    args.correction_id, evidence=args.evidence, regression=args.regression
                ),
                False,
            )
        return 0
    finally:
        app.close()


def _cmd_status(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        payload = {
            "paths": app.paths.to_dict(),
            "counts": app.store.counts(),
            "runtime": app.runtime.status.to_dict(),
            "backends": [item["key"] for item in support_matrix_report()["backends"]],
            "workspace": app.workspace,
            "models": [
                {"id": model["id"], "name": model["name"], "kind": model["source_kind"]}
                for model in app.store.list_models()
            ],
        }
        _emit(payload, args.compact)
        return 0
    finally:
        app.close()


def _cmd_diagnostics(args: argparse.Namespace) -> int:
    app = open_app(args)
    try:
        payload = app.runtime.diagnostics()
        payload["counts"] = app.store.counts()
        payload["backends"] = support_matrix_report()
        _emit(payload, args.compact)
        return 0
    finally:
        app.close()


def _cmd_detect_checks(args: argparse.Namespace) -> int:
    workspace = args.workspace or os.getcwd()
    if not Path(workspace).is_dir():
        raise CliError("The workspace folder does not exist")
    checks = default_checks(workspace)
    _emit({"workspace": workspace, "checks": checks}, args.compact)
    return 0
