# Model Compatibility Register

## Current status

| Format | Inspection status | Limits |
|---|---|---|
| GGUF v2 | Implemented | Metadata, tensor descriptors and derived exact storage bytes; no tensor payload decoding |
| GGUF v3 | Implemented | Little-endian and big-endian header/index parsing; metadata, tensor descriptors and derived exact storage bytes |
| Safetensors | Implemented | Bounded header and tensor-index parser; declared byte ranges are observed, not payload-decoded |
| Hugging Face model folders | Implemented | Bounded `config.json` summary, `model.safetensors.index.json` shard-index discovery, and static tokenizer/chat-template inspection from bounded control files |
| Tokenizer and chat templates | Implemented | Static, read-only summary of tokenizer class/model, observed/declared vocabulary size, added/special tokens and chat templates; SentencePiece models are inventory-only and no template is ever rendered |

GGUF storage bytes are derived from the versioned GGML type registry in `src/eclipse/model_intelligence/ggml_types.py`; the registry records its pinned upstream revision. Safetensors storage bytes are observed directly from the header's declared `data_offsets`. Hugging Face folder discovery reads only the small control files (`config.json`, `model.safetensors.index.json`) and enumerates shard file sizes; it never reads shard payloads and does not follow symbolic links.

## Evidence rules

- **Observed:** read directly from a checkpoint header or metadata field.
- **Derived:** calculated deterministically from observed values.
- **Published:** stated in a cited model card or architecture document.
- **Estimated:** produced by a documented formula and stated assumptions.
- **Unknown:** not available or not yet validated.

Static metadata cannot prove workload routing frequency, semantic expert specialization, actual tokens/second, or quality loss from a transformation. Those require separate evidence and, in relevant cases, behavioral tests.

Unknown tensor type IDs remain unknown, and their storage sizes are not guessed. The GGML block-size/type-size registry is pinned to a reviewed upstream revision; re-review it before changing it. Derived GGUF sizes have not yet been reconciled against a full real checkpoint on Windows, which remains a separate acceptance gate.

Tokenizer/chat-template inspection enforces per-file and aggregate JSON/template byte limits, a shared template-count budget, a bounded added-token entry scan and clipped token previews. It never executes Jinja or reads full model vocabularies into the report. Hugging Face documents that root `chat_template.jinja` overrides an embedded config template and `additional_chat_templates/*.jinja` entries are merged by name. It also documents that processor repositories mixing legacy `chat_template.json` with modern `.jinja` files raise a load error; ECLIPSE reports this conditional incompatibility without guessing whether the inspected folder is a processor and leaves the effective default unresolved.

Hugging Face shard-index coverage is observed from the index file: missing referenced shards and shards not referenced by the index are reported, and the observed shard byte total is compared with the index `metadata.total_size`. Local tokenizer control files are summarised statically with `observed`, `declared` or `unknown` evidence; SentencePiece models are inventoried by name and size only, chat templates are kept as untrusted plain text with bounded previews, and remote repository metadata is not read.

The Model Atlas core (`src/eclipse/model_intelligence/model_atlas.py`) composes these parsers. Parameter counts come from observed tensor shapes, GGUF storage bytes are labelled `derived`, Safetensors/folder storage bytes are labelled `observed`, and an uninspectable shard makes the aggregate explicitly incomplete rather than silently partial.
