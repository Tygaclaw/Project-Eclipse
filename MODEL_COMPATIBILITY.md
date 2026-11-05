# Model Compatibility Register

## Current status

| Format | Inspection status | Limits |
|---|---|---|
| GGUF v2 | Implemented | Metadata and tensor descriptors; no tensor payload decoding or exact storage-size calculation |
| GGUF v3 | Implemented | Little-endian and big-endian header/index parsing; metadata and tensor descriptors |
| Safetensors | Not implemented | Planned bounded header parser |
| Hugging Face model folders | Not implemented | Planned config/tokenizer/shard-index discovery |

## Evidence rules

- **Observed:** read directly from a checkpoint header or metadata field.
- **Derived:** calculated deterministically from observed values.
- **Published:** stated in a cited model card or architecture document.
- **Estimated:** produced by a documented formula and stated assumptions.
- **Unknown:** not available or not yet validated.

Static metadata cannot prove workload routing frequency, semantic expert specialization, actual tokens/second, or quality loss from a transformation. Those require separate evidence and, in relevant cases, behavioral tests.

Unknown tensor type IDs remain unknown. Exact quantized tensor payload sizes must not be estimated until a versioned block-size/type-size registry has been checked against the upstream GGML implementation.
