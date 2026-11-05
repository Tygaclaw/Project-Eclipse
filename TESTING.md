# Testing Strategy

## Current automated suite

The first parser suite uses only Python's standard library and synthetic binary fixtures. It covers:

- GGUF v2/v3 and big-endian v3 header handling.
- Metadata and tensor descriptor parsing.
- Unknown tensor type preservation.
- Bounded array previews.
- Invalid magic/version and truncated headers.
- Excessive counts, duplicate keys/names, invalid alignment, bad dimensions and out-of-region offsets.
- Read-only behavior, path privacy and JSON CLI output.

Run:

```powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
```

## Test evidence boundaries

Synthetic tests prove parser behavior for the cases represented by their fixtures. They do not establish compatibility with every real-world GGUF variant. A real-file Windows test is a separate acceptance gate. GitHub Actions results must be inspected before claiming CI has passed.

## Next tests

1. Real GGUF files from multiple architectures and quantization types.
2. Large metadata arrays and resource-limit behavior on Windows.
3. Safetensors header and shard-index fixtures.
4. Compare metadata/tensor descriptor output with a trusted upstream loader.
5. Later: static memory estimator, preparation integrity, runtime correctness and capability evaluation.
