#!/bin/bash
# Installs two LaunchAgents for the current user, started at login and restarted on exit:
#   local.mcdma.rpcd   the connect end of the MCDMA link (mailbox and socket are owner-only,
#                      so it runs as the user that runs oMLX)
#   local.omlx.split   the oMLX decoder (omlx-split.sh)
# Logs go to $OMLX_BASE/logs/. Rerun after editing config.env.
set -eu
# shellcheck source=/dev/null
. "$HOME/.config/mac-spark-playbook/config.env"
HERE=$(cd "$(dirname "$0")" && pwd)
LOGS=$OMLX_BASE/logs
AGENTS=$HOME/Library/LaunchAgents
mkdir -p "$LOGS" "$AGENTS"
set -- $MAILBOX_MIB
REQ_MIB=$1 REP_MIB=$2

agent() { # label log program args...
  local label=$1 log=$2; shift 2
  {
    echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    echo '<plist version="1.0"><dict>'
    echo "  <key>Label</key><string>$label</string>"
    echo '  <key>ProgramArguments</key><array>'
    for arg in "$@"; do echo "    <string>$arg</string>"; done
    echo '  </array>'
    echo '  <key>ProcessType</key><string>Interactive</string>'
    echo '  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>'
    echo '  <key>ThrottleInterval</key><integer>20</integer>'
    echo "  <key>StandardOutPath</key><string>$LOGS/$log</string>"
    echo "  <key>StandardErrorPath</key><string>$LOGS/$log</string>"
    echo '</dict></plist>'
  } > "$AGENTS/$label.plist"
  plutil -lint -s "$AGENTS/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$AGENTS/$label.plist"
  echo "installed $label; log $LOGS/$log"
}

agent local.mcdma.rpcd rpcd-connect.log "$MCDMA_DIR/build/mcdma-rpcd" connect \
  "$LINK,$MAC_LAN_IF/$SPARK_LAN_LL,$LINK_PORT,rdma_mcrdma0,0,$PATH_MTU,$REQ_MIB,$REP_MIB"
agent local.omlx.split omlx.log /bin/bash "$HERE/omlx-split.sh"
