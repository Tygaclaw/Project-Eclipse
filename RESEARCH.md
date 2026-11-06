# Research Notes and Engineering Hypotheses

## Ground rules

Published results from different hardware are research clues, not forecasts for the target Windows computer. Every performance claim must be measured on the actual model/backend/hardware profile.

## Current research anchors

- The upstream GGUF format specification defines the file header, metadata key/value types, tensor descriptors, alignment and tensor-data offsets. The parser is deliberately limited to these structures and does not read tensor payload bytes.
- The GGML type traits implementation is the authority for quantized block sizes and storage sizes. ECLIPSE derives exact GGUF tensor byte sizes from a single registry pinned to a reviewed upstream revision (`src/eclipse/model_intelligence/ggml_types.py`); re-review the upstream table before changing it.
- llama.cpp is a candidate proven inference engine because it supports multiple execution backends and quantization formats; support must be checked per architecture, operator, format and GPU path before integration.
- Colibri's hierarchical hot/warm/cold residency design and SSD-native MoE research are relevant comparisons. Their benchmark numbers are not transfer predictions for different GPUs, SSDs, CPUs or models.
- Neural Error-Correction Sidecars (NECS) are an experimental hypothesis. They must remain optional and need held-out evidence of quality gain and acceptable overhead before integration.

## Research references

- GGUF format: https://github.com/ggml-org/ggml/blob/master/docs/gguf.md
- GGML type traits: https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml.c
- llama.cpp: https://github.com/ggml-org/llama.cpp
- Colibri: https://github.com/JustVugg/colibri
- SSD-LLaMA paper: https://arxiv.org/abs/2609.18110

References are design inputs, not guarantees. Re-check upstream revisions before encoding format-specific assumptions into the parser or runtime.
