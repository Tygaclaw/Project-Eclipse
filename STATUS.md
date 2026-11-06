# ECLIPSE Project Status

**Status:** `ACTIVE — DESKTOP_SHELL_AND_MODEL_ATLAS_UI`

**Last updated:** 2026-11-06

## Completed in this repository increment

- [x] Confirmed the authenticated GitHub account and write access to `Tygaclaw/Project-Eclipse`.
- [x] Confirmed the existing `main` branch and preserved its initial commit.
- [x] Created/used an isolated feature branch for implementation.
- [x] Recorded the user-directed decision to continue in this existing repository.
- [x] Added a bounded, read-only GGUF v2/v3 parser for metadata and tensor descriptors.
- [x] Added a versioned GGML type registry (`ggml_types.py`) pinned to a reviewed upstream llama.cpp/GGML revision.
- [x] Derived exact GGUF tensor storage bytes, leaving unregistered types and non-block-multiple rows explicitly unknown.
- [x] Added a bounded, read-only Safetensors header and tensor-index parser.
- [x] Added bounded Hugging Face folder discovery (`config.json` summary and `model.safetensors.index.json` shard-index cross-check) without following symlinks or reading shard payloads.
- [x] Kept folder enumeration and bounded control-file reads within configured memory limits.
- [x] Added an evidence-labelled Model Atlas core that composes the three inspectors into one summary (parameters, storage bytes, type/dtype distribution).
- [x] Made Atlas completeness depend on the referenced shard set; unrelated shards are excluded and index `total_size` is reconciled against tensor-data bytes, not whole-file sizes.
- [x] Added JSON CLI output and standard-library synthetic tests.
- [x] Chose PySide6 `6.12.0` + PyInstaller `6.22.3` for the Windows-first desktop shell and recorded the comparison in `docs/ADR-001-desktop-framework.md` (D-011).
- [x] Built a three-workspace `MainWindow` (`Model Intelligence & Inference Platform`, `Capability Amplification & Knowledge System`, `ECLIPSE Agent`) with sidebar navigation and `Ctrl+1/2/3` shortcuts.
- [x] Connected the Model Intelligence workspace to the existing Model Atlas through a bounded, cancellable `AtlasClient` subprocess boundary; no parsing is duplicated in the UI.
- [x] Added honest Capability and Agent placeholder screens; the Agent screen has no chat input and reports that no adapter is connected.
- [x] Added desktop boundary and offscreen Qt smoke tests.
- [x] Added a PyInstaller spec/launcher and pinned desktop requirements.
- [x] Installed the Windows x64 desktop build workflow at `.github/workflows/desktop.yml` using the owner-level GitHub connection; the reference copy remains at `docs/desktop-build-workflow.yml`.

## What works now

- `py -3 -m eclipse inspect-gguf <file.gguf>` parses GGUF header, metadata, tensor index and per-tensor derived storage bytes without loading weights.
- `py -3 -m eclipse inspect-safetensors <file.safetensors>` parses the header length, bounded JSON header and declared tensor byte ranges without loading weights.
- `py -3 -m eclipse inspect-hf-folder <folder>` summarizes `config.json`, enumerates shard sizes, and cross-checks the shard index against the files on disk.
- `py -3 -m eclipse build-atlas <path>` dispatches by input type and emits one evidence-labelled JSON atlas.
- `eclipse-desktop` opens the three-workspace shell; the Model Intelligence workspace selects a GGUF, Safetensors file or Hugging Face folder, runs the atlas with progress, cancellation and prior-inspection evidence, and renders model/architecture, parameters/storage, distribution, warnings, safety, evidence and an advanced disclosure.
- `packaging/launcher.py` + `packaging/eclipse-desktop.spec` build a windowed onedir `dist/ECLIPSE/ECLIPSE.exe`; `ECLIPSE.exe --atlas-backend ...` reuses the unchanged `build-atlas` CLI.
- Parser limits cap header/index bytes, tensor count, metadata entry count, strings, array elements, dimensions, header size, folder entries and shard count.
- Malformed or unsupported inputs fail with a clear error instead of being guessed.
- Unknown tensor types are retained as explicit unknown IDs with unknown storage size.

## Local verification evidence

- Windows GitHub Actions run [#42169639645](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42169639645), Python 3.12 + PySide6 `6.12.0`: **110 tests passed**, including all 8 offscreen desktop UI tests; none were skipped.
- Python GitHub Actions matrix run [#42169639803](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42169639803): all four Windows jobs passed Python 3.11–3.14. The 8 Qt UI tests were skipped in that dependency-free matrix; the dedicated desktop job above runs them with PySide6 installed.
- Python 3.14.4: `python -m compileall -q src tests packaging` — passed.
- Python 3.14.4: `inspect-safetensors --compact`, `inspect-hf-folder --compact`, `build-atlas --compact` and desktop offscreen startup smoke tests — exit 0 with valid JSON / a shown window.

## CI verification evidence

- Baseline CI on `main` (parent commit `122fc56`) is **success**: workflow "Python checks" run [#17](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42157195462) on `windows-latest`, Python 3.11, 3.12, 3.13 and 3.14, all four jobs passed "Run unit tests".
- The prior increment's pull-request CI run is **success**: PR #3 run [#42164928747](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42164928747), all four Windows jobs passed on Python 3.11, 3.12, 3.13 and 3.14; that suite contained **86 tests**.
- The active desktop workflow at `.github/workflows/desktop.yml` is now installed. Its first pull-request run against this increment must be inspected before claiming Windows build validation; no verified Windows desktop artifact exists yet.
- Real Windows/model-file validation has not run.

## Not completed / not claimed

- [ ] Real user GGUF/Safetensors/folder validated on Windows.
- [ ] Tokenizer/chat-template inspection and remote model-card metadata.
- [ ] Derived GGUF sizes reconciled against a trusted full checkpoint.
- [ ] Memory/VRAM feasibility planner.
- [ ] Windows desktop artifact built and smoke-tested on a Windows runner (workflow installed; run pending).
- [ ] Model preparation/transformation, runtime adapters or inference.
- [ ] Capability Amplification system, Obsidian integration, or a working ECLIPSE Agent (placeholder screens only).

## Run locally

From the repository root in normal PowerShell:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse inspect-gguf "D:\Models\model.gguf"
py -3 -m eclipse inspect-safetensors "D:\Models\model.safetensors"
py -3 -m eclipse inspect-hf-folder "D:\Models\YourModelFolder"
py -3 -m eclipse build-atlas "D:\Models\YourModelFolder"
py -3 -m unittest discover -s tests -v
```

To run the desktop shell from source, install the pinned desktop dependencies and launch it:

```powershell
py -3 -m pip install -r requirements-desktop.txt
$env:PYTHONPATH = "src"
py -3 -m eclipse.desktop.app
```

To build the Windows executable with PyInstaller:

```powershell
py -3 -m PyInstaller --noconfirm --clean packaging/eclipse-desktop.spec
```

The result is `dist\ECLIPSE\ECLIPSE.exe`. No administrator privileges, model runtime, API key or GPU are required for these commands.

## Known limitations

- GGUF v2/v3, Safetensors and Hugging Face model folders are supported; tokenizer files and remote metadata are not read.
- Tensor payloads are not decoded. GGUF sizes are derived from a pinned GGML registry; Safetensors and folder shard sizes are observed.
- Derived GGUF sizes are not yet reconciled against a trusted full checkpoint.
- Architecture-specific interpretation is still limited to metadata directly present in the checkpoint.
- The desktop shell is verified by offscreen Qt tests on Linux; the PyInstaller Windows build and the packaged executable have not been run on a Windows machine.
- The agent workspace is a placeholder with no model adapter and no chat input, by design.

## Free & Safe Checklist

- [x] Current parsers have no third-party runtime dependencies.
- [x] No paid API or cloud inference is required.
- [x] Source checkpoint opened read-only; payload bytes are not loaded.
- [x] No credentials, private prompts, or model weights in the repository.
- [x] No administrator privileges needed for current commands.
- [ ] Windows real-file validation pending.
- [ ] Secret/dependency scanning and repository settings review pending.
- [ ] License selection remains with repository owner.
- [ ] PySide6/Qt LGPL license notices, relinking instructions and corresponding-source offer need review and inclusion in the public release package before broader redistribution.

See `CONTINUATION.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TESTING.md`, `SECURITY.md` and `MODEL_COMPATIBILITY.md` for details.
