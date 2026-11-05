# GGUF Parser Scope — First Increment

## Source of truth

The initial parser follows the upstream GGUF specification: https://github.com/ggml-org/ggml/blob/master/docs/gguf.md

It reads the magic, version, tensor/metadata counts, metadata entries, tensor descriptors, alignment and tensor-data-relative offsets. GGUF v2/v3 lengths/counts use the documented 64-bit fields. v3 byte order is selected from the version field; v2 is little-endian.

## Deliberate limits

- Header/index byte budget, tensor count, metadata count, string length, total metadata array items, preview size and tensor dimension count are bounded.
- Nested arrays are rejected.
- Invalid UTF-8, invalid metadata keys, duplicate names/keys, invalid booleans, invalid alignment and out-of-range offsets fail explicitly.
- Tensor payload bytes are never read or memory-mapped.
- Unknown GGML tensor type IDs are retained as `unknown_<id>`.
- Storage byte size is `null` until the parser has a verified GGML block-size/type-size registry.

## Why exact tensor bytes are not reported yet

Quantized GGML tensors store blocks rather than a fixed whole-tensor bits-per-element value. Their encoded byte count depends on a type-specific block size and type size and on the valid row layout. An approximate bits-per-weight calculation is not equivalent to an exact file byte range. ECLIPSE therefore leaves this field unknown until a reviewed mapping and real-file reconciliation tests exist.
