#!/bin/sh
# Starts the listen end of the MCDMA link, detached. Run as the user that runs the producer
# (mailbox and socket are owner-only), with a locked-memory limit that covers both mailbox halves.
# The producer bind-mounts the daemon's socket: restart the producer after restarting this.
set -eu
# shellcheck source=/dev/null
. "$HOME/.config/mac-spark-playbook/config.env"
pkill -x mcdma-rpcd 2>/dev/null && sleep 1 || true
cd "$SPARK_MCDMA_DIR"
# shellcheck disable=SC2086
setsid -f ./build/rpc/mcdma-rpcd listen "$LINK" "$SPARK_RDMA_DEV" "$SPARK_GID_INDEX" "$PATH_MTU" \
  "$SPARK_LAN_IF/$MAC_LAN_LL:$LINK_PORT" $MAILBOX_MIB > "$HOME/mcdma-rpcd-$LINK.log" 2>&1 < /dev/null
sleep 2
printf 'STATUS\n' | nc -U -q1 "/tmp/mcdma-rpcd.$LINK.sock" || true
