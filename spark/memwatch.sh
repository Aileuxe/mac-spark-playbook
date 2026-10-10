#!/bin/sh
# Kills the producer container before the GB10's unified memory runs dry, which can hang the box.
# b12x tunes kernels while vLLM starts, on top of vLLM's own share; this caught it three times.
# Start it detached before the producer: setsid -f ./memwatch.sh > /dev/null 2>&1 < /dev/null
# shellcheck source=/dev/null
. "$HOME/.config/mac-spark-playbook/config.env"
while :; do
  a=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
  if [ "$a" -lt "$MEMWATCH_MIN_GIB" ] && docker ps -q -f "name=^$PRODUCER_CONTAINER\$" | grep -q .; then
    echo "$(date +%T) available ${a} GiB, killing $PRODUCER_CONTAINER" >> "$HOME/memwatch.log"
    docker kill "$PRODUCER_CONTAINER" >/dev/null 2>&1
  fi
  sleep 1
done
