# Tools

This directory contains Python scripts for pack management and CI/CD operations.

## Scripts

- **`lint_packs.py`** - Validates pack manifests and enforces PAS/SCQA structure tokens
- **`build_index_payload.py`** - Builds JSON payloads for Azure Search indexing  
- **`offline_eval.py`** - Lightweight CI evaluation with groundedness metrics
- **`index_packs.py`** - Upserts docs to Azure AI Search via REST API
- **`wire_check.py`** - Verifies indexed docs are searchable

## Usage

See individual script help: `python tools/<script>.py --help`

