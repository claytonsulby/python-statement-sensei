#!/bin/bash
uv run --project "$(dirname "$0")" python "$(dirname "$0")/cli.py" "$@"
