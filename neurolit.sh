#!/usr/bin/env bash

dir="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$dir"

if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found. Please run install script first."
    exit 1
fi

source .venv/bin/activate
python3 main.py
