#!/bin/bash

source venv/bin/activate

aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --no-auto-commits \
      --map-tokens 1024 \
      "$@"
