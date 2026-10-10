#!/bin/sh
# Qwen3.8 Flash Next NVFP4 on the vLLM b12x build as the KV-handoff producer.
# Why each choice is in docs/setup.md ("Producer"). Usage: run-producer.sh [producer|plain]
# "plain" serves the same model without the connector and without MTP, for comparison runs.
set -eu
# shellcheck source=/dev/null
. "$HOME/.config/mac-spark-playbook/config.env"
MODE=${1:-producer}
: "${NVFP4_SNAPSHOT:?set NVFP4_SNAPSHOT in config.env}"
MODEL=/root/.cache/huggingface/hub/models--local-inference-lab--Qwen3.8-Flash-Next-NVFP4/snapshots/$NVFP4_SNAPSHOT
EXTRA=""
if [ "$MODE" = producer ]; then
  # MTP runs only so the handoff carries the MTP head's cache; the producer returns one token.
  EXTRA="--speculative-config {\"method\":\"mtp\",\"num_speculative_tokens\":1} --kv-transfer-config {\"kv_connector\":\"MCDMAKVConnector\",\"kv_connector_module_path\":\"mcdma_kv.connector\",\"kv_role\":\"kv_producer\",\"kv_connector_extra_config\":{\"links\":[\"$LINK\"]}}"
fi
mkdir -p "$CACHE_DIR/b12x" "$CACHE_DIR/vllm"
docker rm -f "$PRODUCER_CONTAINER" >/dev/null 2>&1 || true
# shellcheck disable=SC2086
exec docker run -d --init --name "$PRODUCER_CONTAINER" --gpus all --ipc=host --network host \
  --security-opt seccomp=unconfined --ulimit nofile=1048576:1048576 --ulimit memlock=-1 \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface:ro" -v "$SPARK_MCDMA_DIR:/mcdma:ro" \
  -v "/tmp/mcdma-rpcd.$LINK.sock:/tmp/mcdma-rpcd.$LINK.sock" \
  -v "$CACHE_DIR/b12x:/root/.cache/b12x" -v "$CACHE_DIR/vllm:/root/.cache/vllm" -e B12X_COMPILE_WORKERS=2 \
  -e HF_HUB_OFFLINE=1 -e VLLM_PLE_TABLE_MEMORY=disk -e CUTE_DSL_ARCH=sm_121a -e SAFETENSORS_FAST_GPU=1 \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_SSM_CONV_STATE_LAYOUT=DS -e VLLM_USE_AOT_COMPILE=1 \
  -e VLLM_USE_MEGA_AOT_ARTIFACT=1 -e VLLM_USE_V2_MODEL_RUNNER=1 -e B12X_POLICY_MODE=auto -e VLLM_MXFP8_LM_HEAD=1 \
  -e VLLM_B12X_MOE_FP4_LAYER_MAX_INPUT_SCALE=w13 -e PYTHONPATH=/mcdma/integrations/vllm \
  -e MCDMA_RPC_LIBRARY=/mcdma/build/rpc/libmcdma-rpc.so -e VLLM_LOGGING_LEVEL=INFO \
  "$VLLM_IMAGE" \
  vllm serve "$MODEL" --served-model-name "$SPARK_MODEL" --host 0.0.0.0 --port "$SPARK_PORT" \
    --dtype bfloat16 --kv-cache-dtype auto --quantization modelopt_mixed --load-format b12x --block-size 16 \
    --max-model-len 65536 --max-num-seqs 1 --max-num-batched-tokens 8192 --enable-chunked-prefill \
    --no-enable-prefix-caching --recurrent-checkpoint-policy aligned \
    --gdn-decode-kernel b12x --linear-backend b12x --moe-backend b12x --no-enable-flashinfer-autotune \
    --limit-mm-per-prompt '{"image":0,"video":0}' --compilation-config '{"pass_config":{"fuse_act_quant":true}}' \
    --gpu-memory-utilization 0.70 $EXTRA
