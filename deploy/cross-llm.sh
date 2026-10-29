#!/bin/sh
# Source must already have been fetched/verified by provision-llm.sh.
set -eu
cd "$(dirname "$0")/.."
expected=$(sed -n 's/.*"llama_cpp_commit": "\([0-9a-f]*\)".*/\1/p' deploy/pi-lock.json)
test -n "$expected"
test "$(git -c safe.directory=/app/local/llama.cpp -C local/llama.cpp rev-parse HEAD)" = "$expected"
python3 deploy/patch_completion.py
cmake -S local/llama.cpp -B local/llama.cpp/build-cross \
    -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
    -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc -DCMAKE_CXX_COMPILER=aarch64-linux-gnu-g++ \
    -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8-a \
    -DGGML_BACKEND_DL=OFF -DGGML_CPU_ALL_VARIANTS=OFF -DGGML_OPENMP=OFF \
    -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
cmake --build local/llama.cpp/build-cross -j 4 --target llama-completion
echo 'Cross build ready in local/llama.cpp/build-cross; run inside ARM64 via LLAMA_LOCAL_BUILD=build-cross.'
