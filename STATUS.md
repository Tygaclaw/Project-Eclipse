# ECLIPSE Project Status

**Status:** `ACTIVE — STATIC_INSPECTION_GGUF_AND_SAFETENSORS`

**Last updated:** 2026-11-06

## Completed in this repository increment

- [x] Confirmed the authenticated GitHub account and write access to `Tygaclaw/Project-Eclipse`.
- [x] Confirmed the existing `main` branch and preserved its initial commit.
- [x] Created/used an isolated feature branch for implementation.
- [x] Recorded the user-directed decision to continue in this existing repository.
- [x] Added a bounded, read-only GGUF v2/v3 parser for metadata and tensor descriptors.
- [x] Added a versioned GGML type registry (`ggml_types.py`) pinned to a reviewed upstream llama.cpp/GGML revision.
- [x] Derived exact GGUF tensor storage bytes, leaving unregistered types and non-block-multiple rows explicitly unknown.
- [x] Added a bounded, read-only Safetensors header and tensor-index parser.
- [x] Added JSON CLI output and standard-library synthetic tests.

## What works now

- `py -3 -m eclipse inspect-gguf <file.gguf>` parses GGUF header, metadata, tensor index and per-tensor derived storage bytes without loading weights.
- `py -3 -m eclipse inspect-safetensors <file.safetensors>` parses the header length, bounded JSON header and declared tensor byte ranges without loading weights.
- Parser limits cap header/index bytes, tensor count, metadata entry count, strings, array elements, dimensions and header size.
- Malformed or unsupported inputs fail with a clear error instead of being guessed.
- Unknown tensor types are retained as explicit unknown IDs with unknown storage size.

## Local verification evidence

- Python 3.14.4: `PYTHONPATH=src python -m unittest discover -s tests -v` — **60 tests passed**.
- Python 3.14.4: `python -m compileall -q src tests .github/scripts` — passed.
- Python 3.14.4: `inspect-safetensors --compact` CLI smoke test — exit 0 with valid JSON.

## CI verification evidence

- Baseline CI on `main` (parent commit `122fc56`) is **success**: workflow "Python checks" run [#17](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42157195462) on `windows-latest`, Python 3.11, 3.12, 3.13 and 3.14, all four jobs passed "Run unit tests".
- The increment's own CI run is created by the pull request and is pending; it has not been inspected in this environment.
- Real Windows/model-file validation has not run.

## Not completed / not claimed

- [ ] This increment's GitHub Actions run verified (baseline `main` CI is green).
- [ ] Real user GGUF/Safetensors file validated on Windows.
- [ ] Hugging Face model-folder and shard-index discovery.
- [ ] Derived GGUF sizes reconciled against a trusted full checkpoint.
- [ ] Model Atlas UI or feasibility planner.
- [ ] Model preparation/transformation, runtime adapters or inference.
- [ ] Capability Amplification system, Obsidian integration, or ECLIPSE Agent.
- [ ] Windows desktop application.

## Run locally

From the repository root in normal PowerShell:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse inspect-gguf "D:\Models\model.gguf"
py -3 -m eclipse inspect-safetensors "D:\Models\model.safetensors"
py -3 -m unittest discover -s tests -v
```

No administrator privileges, model runtime, API key or GPU are required for these commands.

## Known limitations

- GGUF v2/v3 and Safetensors are supported; Hugging Face model folders are not yet discovered.
- Tensor payloads are not decoded. GGUF sizes are derived from a pinned GGML registry; Safetensors sizes are observed header offsets.
- Derived GGUF sizes are not yet reconciled against a trusted full checkpoint.
- Architecture-specific interpretation is still limited to metadata directly present in the checkpoint.
- Desktop/backend technology comparison remains open.

## Free & Safe Checklist

- [x] Current parsers have no third-party runtime dependencies.
- [x] No paid API or cloud inference is required.
- [x] Source checkpoint opened read-only; payload bytes are not loaded.
- [x] No credentials, private prompts, or model weights in the repository.
- [x] No administrator privileges needed for current commands.
- [ ] Windows real-file validation pending.
- [ ] Secret/dependency scanning and repository settings review pending.
- [ ] License selection remains with repository owner.

See `CONTINUATION.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TESTING.md`, `SECURITY.md` and `MODEL_COMPATIBILITY.md` for details.
