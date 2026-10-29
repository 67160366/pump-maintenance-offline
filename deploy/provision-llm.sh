#!/bin/sh
# Explicit ONLINE provisioning, after setup_pi.py. Never called by dashboard runtime.
set -eu
cd "$(dirname "$0")/.."
PYTHON=${PYTHON:-.venv/bin/python}
for command in git cmake c++; do
    command -v "$command" >/dev/null || { echo "Install build tools first: sudo apt-get install git cmake build-essential" >&2; exit 1; }
done
revision=$("$PYTHON" -c 'import json; print(json.load(open("deploy/pi-lock.json"))["llama_cpp_commit"])')
mkdir -p local
if [ ! -d local/llama.cpp ]; then
    git init local/llama.cpp
    git -C local/llama.cpp remote add origin https://github.com/ggml-org/llama.cpp.git
fi
actual=$(git -C local/llama.cpp rev-parse --verify HEAD 2>/dev/null) || actual=''
if [ -n "$actual" ] && [ "$actual" != "$revision" ]; then
    echo 'Existing local/llama.cpp differs from lock; preserve/move it before provisioning.' >&2
    exit 1
fi
if [ -z "$actual" ]; then
    git -C local/llama.cpp fetch --depth 1 origin "$revision"
    git -C local/llama.cpp checkout --detach FETCH_HEAD
fi
"$PYTHON" deploy/patch_completion.py
cmake -S local/llama.cpp -B local/llama.cpp/build -DCMAKE_BUILD_TYPE=Release \
    -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_BACKEND_DL=OFF -DGGML_CPU_ALL_VARIANTS=OFF \
    -DGGML_OPENMP=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
cmake --build local/llama.cpp/build --config Release -j 2 --target llama-completion
chmod +x deploy/llama-local
"$PYTHON" deploy/fetch_model.py
local/llama.cpp/build/bin/llama-completion --version
echo 'Provisioned. Test: .venv/bin/python pi_check.py --benchmark --llama-cli deploy/llama-local --gguf models/qwen2.5-0.5b-instruct-q4_k_m.gguf --output evidence/pi-llm.json'
