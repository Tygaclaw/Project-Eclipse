# Testing Strategy

## Current automated suite

The core inspection suite uses only Python's standard library and synthetic binary fixtures. The desktop tests additionally require PySide6 `6.12.0` and skip when it is not installed. Together the suite currently contains 131 tests and covers:

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
- Model Atlas core: GGUF/Safetensors/folder dispatch, tensor-element and storage aggregation, evidence labels, missing/corrupt shard incompleteness, unreferenced-shard exclusion, tensor-data total reconciliation, unsupported input and shard limits, plus the tokenizer section for folder/GGUF sources and the honest unavailable section for Safetensors.
- Tokenizer and chat templates (`tests/test_tokenizer.py`): asset inventory (`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`, `vocab.json`, `vocab.txt`, `merges.txt`, SentencePiece models as inventory-only), tokenizer class/model/pre-tokenizer/decoder/normalizer, observed vs declared vocabulary candidates, added and special tokens, documented chat-template precedence, additional named templates, legacy `chat_template.json`, conflict detection, bounded previews and template-size limits, invalid JSON and symlink safety, entry limits, non-directory/missing-path errors, GGUF tokenizer metadata summarisation, the `inspect-tokenizer` CLI and the no-execution invariants (`templates_rendered`, `jinja_imported`).
- Desktop boundary (`tests/test_atlas_client.py`): argument-list command construction, a real synthetic GGUF integration run, invalid JSON/contract rejection, payload-safety invariant rejection, bounded output, stderr propagation, cancellation and timeout.
- Desktop smoke (`tests/test_desktop_smoke.py`): offscreen Qt startup, all three navigation destinations, navigation switching, honest placeholder checks, empty state and Atlas section rendering, including the "Tokenizer and chat format" card and the `Declared` evidence label.

Run (desktop tests need PySide6; use an offscreen platform on headless machines):

```powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
```

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m unittest discover -s tests -v
```

## Local verification evidence

- Tokenizer/chat-template increment, Python 3.14.4 with PySide6 `6.12.0`: `python -m compileall -q src tests` passed; `PYTHONPATH=src python -m unittest discover -s tests` → **131 tests passed, 0 skipped**. This is local evidence; GitHub Actions evidence for this increment is produced once the branch is pushed.

## Verified GitHub Actions evidence

- Latest dedicated Windows desktop run [#42173214699](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42173214699): all **110 tests passed** with PySide6 installed, including all 8 offscreen UI tests; PyInstaller created the Windows x64 app; the packaged `ECLIPSE.exe --atlas-backend --help` smoke test passed; the ZIP was uploaded as `ECLIPSE-windows-x64` (50,929,741 bytes).
- Latest core CI matrix [#42173214668](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42173214668): all four Windows jobs passed Python 3.11–3.14. The 8 Qt UI tests were skipped in this matrix because PySide6 is optional there; they ran without skips in the dedicated desktop job.

## Manual Windows 11 smoke test

- User-confirmed: the packaged application launched on Windows 11 and all three workspace pages were clickable and displayed successfully.
- User-confirmed: selected `Qwen3.5-9B-Q4_K_M.gguf` in the Model Intelligence workspace and ran Inspect model. The Atlas displayed GGUF v3, architecture `qwen35`, model name `Qwen3.5-9B`, 427 tensors, 8,953,803,264 parameters, 5,669,554,176 bytes (5.28 GiB) registry-derived tensor storage and a 5.29 GiB file size; storage coverage was complete.
- The UI safety panel reported 0 tensor payload bytes read, payloads not loaded and source not modified. The displayed warning correctly notes the GGUF storage calculation has not yet been reconciled against a trusted full-checkpoint loader.
- This validates the packaged UI-to-Atlas integration with one real GGUF on Windows 11. It does not validate inference, GPU feasibility, Safetensors files or multi-shard Hugging Face folders.

## Test evidence boundaries

Synthetic tests prove parser behavior for the cases represented by their fixtures. They do not establish compatibility with every real-world GGUF variant or multi-shard folder layout. A real-file Windows test is a separate acceptance gate. One GGUF now passes that manual gate; further format/architecture coverage and an independent storage cross-check remain necessary. GitHub Actions results must be inspected before claiming CI has passed.

## Next tests

1. Real GGUF files from additional architectures and quantization types.
2. Large metadata arrays and resource-limit behavior on Windows.
3. Real Safetensors files and multi-shard Hugging Face folders on Windows.
4. Compare metadata/tensor descriptor output and derived sizes with a trusted upstream loader.
5. Run the tokenizer/chat-format card against a real multi-file Hugging Face folder (including `additional_chat_templates/*.jinja`) and a real GGUF with embedded `tokenizer.chat_template`.
6. Add the static memory/VRAM feasibility estimator, then separately validate runtime correctness and preparation integrity.
