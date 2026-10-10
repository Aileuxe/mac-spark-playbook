#!/bin/bash
# Installs the LaunchDaemon that restores the Mac's end of the link at boot and every 60 s.
# Run with sudo from this directory after filling in ~/.config/mac-spark-playbook/config.env.
# Copies MCDMA's restore helper and checker from MCDMA_DIR; rerun after rebuilding the driver.
set -eu
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
# config.env expands $HOME, which must be the invoking user's, not root's.
export HOME=$(eval echo ~"${SUDO_USER:?run with sudo from your own account}")
# shellcheck source=/dev/null
. "${CONFIG:-$HOME/.config/mac-spark-playbook/config.env}"
DIR=/usr/local/libexec/mcdma
LABEL=local.mcdma.link
install -d -m 755 "$DIR"
install -m 755 mcdma-link-restore.sh "$MCDMA_DIR/build/cx5-native-check" "$DIR/"
install -m 644 "$MCDMA_DIR/tools/restore-rdma.py" "$DIR/restore-rdma.py"
cat > "$DIR/link.env" <<EOF
MAC_CX5_HWADDR=$MAC_CX5_HWADDR
SPARK_CX_GID=$SPARK_CX_GID
SPARK_CX_HWADDR=$SPARK_CX_HWADDR
EOF
cat > /Library/LaunchDaemons/$LABEL.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$DIR/mcdma-link-restore.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>60</integer>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>/var/log/mcdma-link.log</string>
  <key>StandardErrorPath</key><string>/var/log/mcdma-link.log</string>
</dict>
</plist>
EOF
chown root:wheel /Library/LaunchDaemons/$LABEL.plist
launchctl bootout system/$LABEL 2>/dev/null || true
launchctl bootstrap system /Library/LaunchDaemons/$LABEL.plist
echo "installed $LABEL; log /var/log/mcdma-link.log"
