#!/bin/bash
# Keeps the Mac's end of the MCDMA link usable. Run as root every 60 s by the LaunchDaemon that
# install-link-daemon.sh writes. A healthy link exits at once without touching anything.
#
# The mcrdmaN address and the Spark's static neighbour are lost on every restart, and the driver
# names its interfaces in load order, so this finds the CX5 port by its MAC, gives it the
# MAC-derived link-local GID and the Spark's static neighbour, and runs MCDMA's checker.
set -u
DIR=/usr/local/libexec/mcdma
# shellcheck source=/dev/null
. "$DIR/link.env"
PY=/usr/bin/python3
[ -x /opt/homebrew/bin/python3 ] && PY=/opt/homebrew/bin/python3

iface=
for n in $(/sbin/ifconfig -l); do
  case $n in mcrdma*) /sbin/ifconfig "$n" | grep -qi "ether $MAC_CX5_HWADDR" && iface=$n ;; esac
done
if [ -z "$iface" ]; then
  echo "$(date '+%F %T') no mcrdma interface with $MAC_CX5_HWADDR yet (driver not loaded or enclosure missing)"
  exit 1
fi

# Healthy: the driver instance behind $iface reports its port active and its GID live, and the
# Spark's static neighbour is in place.
healthy() {
  /usr/sbin/ioreg -r -c MCDMACX5Native -l | /usr/bin/awk -v want="\"$iface\"" '
    function close_block() { if (name == want) { found = 1; ok = (gid == "Yes" && port == "Yes") } }
    /\+-o MCDMACX5Native/ { close_block(); name = gid = port = "" }
    /"MCDMAAddressInterface"/ { name = $NF }
    /"MCDMAGidLive"/ { gid = $NF }
    /"MCDMAPortActive"/ { port = $NF }
    END { close_block(); exit (found && ok) ? 0 : 1 }' &&
  /usr/sbin/ndp -an | /usr/bin/grep -q "^$SPARK_CX_GID%$iface .*permanent"
}
healthy && exit 0
echo "$(date '+%F %T') restoring $iface"
# A retry after a partial run must not trip over the neighbour entry it already made.
/usr/sbin/ndp -d "$SPARK_CX_GID%$iface" >/dev/null 2>&1
exec "$PY" -I "$DIR/restore-rdma.py" --interface "$iface" --expected-mac "$MAC_CX5_HWADDR" \
  --peer-gid "$SPARK_CX_GID" --peer-mac "$SPARK_CX_HWADDR" --checker "$DIR/cx5-native-check"
