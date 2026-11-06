# Testing Strategy

## Current automated suite

The static-inspection suite uses only Python's standard library and synthetic binary fixtures. It currently contains 74 tests and covers:

- GGUF v2/v3 and big-endian v3 header handling.
- Metadata and tensor descriptor parsing.
- Unknown tensor type preservation.
- Bounded array previews.
- Invalid magic/version and truncated headers.
- Excessive counts, duplicate keys/names, invalid alignment, bad dimensions and out-of-region offsets.
- Read-only behavior, path privacy and JSON CLI output.
- GGML type registry block/type sizes, derived exact GGUF storage bytes, non-block-multiple rows and truncated-file warnings.
- Safetensors header parsing, metadata, unknown dtypes, shape/range mismatch warnings, overlapping/out-of-range/negative offsets, invalid JSON, header limits and read-only behavior.
- Hugging Face folder discovery: `config.json` summaries, shard-index weight-map parsing, missing/unreferenced shard warnings, declared-total mismatch warnings, path-separator rejection, entry limits, symlink skipping and read-only behavior.

Run:

```powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
```

## Test evidence boundaries

Synthetic tests prove parser behavior for the cases represented by their fixtures. They do not establish compatibility with every real-world GGUF variant or multi-shard folder layout. A real-file Windows test is a separate acceptance gate. GitHub Actions results must be inspected before claiming CI has passed.

## Next tests

1. Real GGUF files from multiple architectures and quantization types.
2. Large metadata arrays and resource-limit behavior on Windows.
3. Real multi-shard Safetensors folders and shard-index fixtures.
4. Compare metadata/tensor descriptor output and derived sizes with a trusted upstream loader.
5. Tokenizer/chat-template file inspection and remote model-card metadata (not yet in scope).
5. Later: static memory estimator, preparation integrity, runtime correctness and capability evaluation.
