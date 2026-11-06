# Testing Strategy

## Current automated suite

The core inspection suite uses only Python's standard library and synthetic binary fixtures. The desktop tests additionally require PySide6 `6.12.0` and skip when it is not installed. Together the suite currently contains 110 tests and covers:

- GGUF v2/v3 and big-endian v3 header handling.
- Metadata and tensor descriptor parsing.
- Unknown tensor type preservation.
- Bounded array previews.
- Invalid magic/version and truncated headers.
- Excessive counts, duplicate keys/names, invalid alignment, bad dimensions and out-of-region offsets.
- Read-only behavior, path privacy and JSON CLI output.
- GGML type registry block/type sizes, derived exact GGUF storage bytes, non-block-multiple rows and truncated-file warnings.
- Safetensors header parsing, metadata, unknown dtypes, shape/range mismatch warnings, overlapping/out-of-range/negative offsets, invalid JSON, header limits and read-only behavior.
- Hugging Face folder discovery: `config.json` summaries, shard-index weight-map parsing, referenced/missing/unreferenced shard handling, bounded lazy directory enumeration, capped control-file reads, path-separator rejection, symlink skipping and read-only behavior.
- Model Atlas core: GGUF/Safetensors/folder dispatch, tensor-element and storage aggregation, evidence labels, missing/corrupt shard incompleteness, unreferenced-shard exclusion, tensor-data total reconciliation, unsupported input and shard limits.
- Desktop boundary (`tests/test_atlas_client.py`): argument-list command construction, a real synthetic GGUF integration run, invalid JSON/contract rejection, payload-safety invariant rejection, bounded output, stderr propagation, cancellation and timeout.
- Desktop smoke (`tests/test_desktop_smoke.py`): offscreen Qt startup, all three navigation destinations, navigation switching, honest placeholder checks, empty state and Atlas section rendering.

Run (desktop tests need PySide6; use an offscreen platform on headless machines):

```powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
```

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m unittest discover -s tests -v
```

## Verified GitHub Actions evidence

- Latest dedicated Windows desktop run [#42170364882](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42170364882): all **110 tests passed** with PySide6 installed, including all 8 offscreen UI tests; PyInstaller created the Windows x64 app; the packaged `ECLIPSE.exe --atlas-backend --help` smoke test passed; the ZIP was uploaded as `ECLIPSE-windows-x64` (50,929,677 bytes).
- Latest core CI matrix [#42170364898](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42170364898): all four Windows jobs passed Python 3.11–3.14. The 8 Qt UI tests were skipped in this matrix because PySide6 is optional there; they ran without skips in the dedicated desktop job.

## Manual Windows 11 smoke test

- User-confirmed: the packaged application launched on Windows 11 and all three workspace pages were clickable and displayed successfully.
- Not yet confirmed: selecting and inspecting a real local model file from the desktop UI.

## Test evidence boundaries

Synthetic tests prove parser behavior for the cases represented by their fixtures. They do not establish compatibility with every real-world GGUF variant or multi-shard folder layout. A real-file Windows test is a separate acceptance gate. GitHub Actions results must be inspected before claiming CI has passed.

## Next tests

1. Real GGUF files from multiple architectures and quantization types.
2. Large metadata arrays and resource-limit behavior on Windows.
3. Real multi-shard Safetensors folders and shard-index fixtures.
4. Compare metadata/tensor descriptor output and derived sizes with a trusted upstream loader.
5. Tokenizer/chat-template file inspection and remote model-card metadata (not yet in scope).
6. Windows desktop build: run `packaging/eclipse-desktop.spec` on `windows-latest`, assert `dist\ECLIPSE\ECLIPSE.exe --atlas-backend --help` and the `ECLIPSE-windows-x64` artifact.
7. Later: static memory estimator, preparation integrity, runtime correctness and capability evaluation.
