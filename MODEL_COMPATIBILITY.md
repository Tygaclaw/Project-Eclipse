# Model Compatibility Register

## Current status

| Format | Inspection status | Limits |
|---|---|---|
| GGUF v2 | Implemented | Metadata, tensor descriptors and derived exact storage bytes; no tensor payload decoding |
| GGUF v3 | Implemented | Little-endian and big-endian header/index parsing; metadata, tensor descriptors and derived exact storage bytes |
| Safetensors | Implemented | Bounded header and tensor-index parser; declared byte ranges are observed, not payload-decoded |
| Hugging Face model folders | Implemented (partial) | Bounded `config.json` summary and `model.safetensors.index.json` shard-index discovery; tokenizer files not parsed |

GGUF storage bytes are derived from the versioned GGML type registry in `src/eclipse/model_intelligence/ggml_types.py`; the registry records its pinned upstream revision. Safetensors storage bytes are observed directly from the header's declared `data_offsets`. Hugging Face folder discovery reads only the small control files (`config.json`, `model.safetensors.index.json`) and enumerates shard file sizes; it never reads shard payloads and does not follow symbolic links.

## Evidence rules

- **Observed:** read directly from a checkpoint header or metadata field.
- **Derived:** calculated deterministically from observed values.
- **Published:** stated in a cited model card or architecture document.
- **Estimated:** produced by a documented formula and stated assumptions.
- **Unknown:** not available or not yet validated.

Static metadata cannot prove workload routing frequency, semantic expert specialization, actual tokens/second, or quality loss from a transformation. Those require separate evidence and, in relevant cases, behavioral tests.

Unknown tensor type IDs remain unknown, and their storage sizes are not guessed. The GGML block-size/type-size registry is pinned to a reviewed upstream revision; re-review it before changing it. Derived GGUF sizes have not yet been reconciled against a full real checkpoint on Windows, which remains a separate acceptance gate.

Hugging Face shard-index coverage is observed from the index file: missing referenced shards and shards not referenced by the index are reported, and the observed shard byte total is compared with the index `metadata.total_size`. Tokenizer files and remote repository metadata are not read.
