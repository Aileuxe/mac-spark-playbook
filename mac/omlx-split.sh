#!/bin/bash
# The oMLX decoder of the split, run by the LaunchAgent local.omlx.split (install-agents.sh).
# Long prompts are prefilled by vLLM on the Spark and their state arrives over the MCDMA link.
set -eu
# shellcheck source=/dev/null
. "$HOME/.config/mac-spark-playbook/config.env"
# An external model disk can mount after login; launchd restarts this until it is there.
[ -d "$MODEL_DIR/$LOCAL_MODEL" ] || { echo "$(date '+%F %T') waiting for $MODEL_DIR/$LOCAL_MODEL"; sleep 20; exit 1; }
cd "$OMLX_DIR"
# oMLX refuses to listen on 0.0.0.0 without an API key; keep it in a 0600 file, never in git.
export OMLX_API_KEY=$(cat "$OMLX_BASE/.api-key")
export OMLX_REMOTE_PREFILL_URL=http://$SPARK_HOST:$SPARK_PORT
export OMLX_REMOTE_PREFILL_MODEL=$SPARK_MODEL
export OMLX_REMOTE_PREFILL_FOR=$LOCAL_MODEL
export OMLX_REMOTE_PREFILL_LINKS=$LINK
export OMLX_REMOTE_PREFILL_CHECKSUM=0
export OMLX_REMOTE_PREFILL_TIMEOUT=300
export OMLX_MCDMA_RPC_LIBRARY=$MCDMA_DIR/build/libmcdma-rpc.dylib
export OMLX_MCDMA_RPCD_SOCKET=/tmp/mcdma-rpcd.sock
# launchd starts agents at the default scheduling role: decode ran at 37 instead of 52-55 tok/s.
# taskpolicy -a gives oMLX the scheduling policies of an application and execs it.
exec /usr/sbin/taskpolicy -a .venv/bin/omlx serve --base-path "$OMLX_BASE" --model-dir "$MODEL_DIR" \
  --host 0.0.0.0 --port "$OMLX_PORT"
