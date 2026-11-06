# GGUF Parser Scope — First Increment

## Source of truth

The initial parser follows the upstream GGUF specification: https://github.com/ggml-org/ggml/blob/master/docs/gguf.md

It reads the magic, version, tensor/metadata counts, metadata entries, tensor descriptors, alignment and tensor-data-relative offsets. GGUF v2/v3 lengths/counts use the documented 64-bit fields. v3 byte order is selected from the version field; v2 is little-endian.

## Deliberate limits

- Header/index byte budget, tensor count, metadata count, string length, total metadata array items, preview size and tensor dimension count are bounded.
- Nested arrays are rejected.
- Invalid UTF-8, invalid metadata keys, duplicate names/keys, invalid booleans, invalid alignment and out-of-range offsets fail explicitly.
- Tensor payload bytes are never read or memory-mapped.
- Unknown GGML tensor type IDs are retained as `unknown_<id>` with an unknown storage size.

## Exact tensor bytes

Quantized GGML tensors store blocks rather than a fixed whole-tensor bits-per-element value, so the encoded byte count is `type_size * elements / block_size`, and the innermost dimension must be a multiple of the block size. `src/eclipse/model_intelligence/ggml_types.py` holds this block-size/type-size registry, pinned to a reviewed upstream llama.cpp/GGML revision recorded in the module. Tensor storage bytes are reported with the evidence label `derived`.

A tensor whose type is not registered, or whose row length is not a block multiple, is reported with `storage_bytes: null`, an explicit `storage_bytes_unknown_reason` and a warning. When a declared storage region extends past the end of the file, the parser warns that the file may be truncated. These derived sizes have not yet been reconciled against a full real checkpoint on Windows; that remains a separate acceptance gate. `bits_per_weight` is available in the registry for display but is not treated as an exact file byte range.
