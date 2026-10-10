# Setup

The steps run in order, and each ends with a check. Fill in `config.env` first: copy `config.env.example` to
`~/.config/mac-spark-playbook/config.env` on both machines. The names of devices and interfaces come from your own
machines (`ifconfig`, `ibv_devices`, `ip link`), not from the examples.

## 1. Driver on the Mac

Clone [Aileuxe/MCDMA](https://github.com/Aileuxe/MCDMA) on both machines and check out branch `playbook`. It
combines MCDMA 0.1.18 with four open PRs; see the README.

MCDMA's [install guide](https://github.com/Aileuxe/MCDMA/blob/playbook/docs/install.md) has the rest:
- Recovery settings: Reduced Security with user-managed kernel extensions, and SIP off for the ad-hoc-signed build;
- building with `tools/build.py`;
- installing and approving the kext;
- restarting.

On a macOS build MCDMA does not list yet, the driver refuses to start. Compare the build first with
`tools/compare-apple-build.py`; [`docs/build-26B5101f.md`](https://github.com/Aileuxe/MCDMA/blob/playbook/docs/build-26B5101f.md)
shows how 27.2 beta `26B5101f` was checked against `26A428`. Only then add it to the allowlist.

**Check:** `kmutil showloaded --list-only | grep org.mcdma.cx5.native` lists the kext, and `ifconfig` shows an
`mcrdmaN` interface with the CX5's MAC.

## 2. The Spark's port

Section 4 of the install guide covers the Linux peer. To keep the port's settings across reboots, use a
NetworkManager profile instead of `ip` commands. It gives the port MTU 9000, no IPv4, and a MAC-derived link-local
address:

```bash
sudo nmcli con add type ethernet ifname "$SPARK_CX_IF" con-name mcdma-mac ipv4.method disabled \
  ipv6.method link-local ipv6.addr-gen-mode eui64 802-3-ethernet.mtu 9000
sudo nmcli con up mcdma-mac
```

The Mac's `mcrdmaN` carries no IP and never answers neighbour discovery, so the Spark needs a static neighbour for it.
The dispatcher in `spark/` restores that neighbour whenever the port comes up:

```bash
printf 'SPARK_CX_IF=%s\nMAC_CX5_GID=%s\nMAC_CX5_HWADDR=%s\n' "$SPARK_CX_IF" "$MAC_CX5_GID" "$MAC_CX5_HWADDR" \
  | sudo tee /etc/default/mcdma-neigh
sudo install -m 755 -o root -g root spark/90-mcdma-neigh /etc/NetworkManager/dispatcher.d/
sudo nmcli con up mcdma-mac
```

**Check:** `ip -6 neigh show dev "$SPARK_CX_IF"` shows the Mac's GID as `PERMANENT`. `show_gids` lists the Spark's own
MAC-derived GID as RoCE v2; set its index as `SPARK_GID_INDEX`.

## 3. The Mac's end of the link, kept alive

The Mac loses its `mcrdmaN` address and its neighbour entry on every restart. The driver also names interfaces in
load order. `mac/install-link-daemon.sh` installs a LaunchDaemon that runs every 60 s. It exits at once when the link
is healthy. Otherwise it finds the port by MAC and restores it with MCDMA's `restore-rdma.py`, then runs the checker.

```bash
cd mac && sudo ./install-link-daemon.sh
```

**Check:** `ndp -an | grep mcrdma` shows the Spark's GID as `permanent`, and `/var/log/mcdma-link.log` stays quiet.
Before going on, run MCDMA's RDMA READ and WRITE verification (install guide, section 5).

## 4. Link daemons

Each end runs `mcdma-rpcd`. A Spark has no Thunderbolt networking, so the two daemons do their short setup exchange
over the LAN. Each end pins the other's link-local address there (PR #18). The payload moves only over the QSFP
cable.

```bash
spark/start-link.sh        # on the Spark: the listen end
mac/install-agents.sh      # on the Mac: LaunchAgents for the connect end and for oMLX (step 6)
```

Build the Spark side with `make -C rpc`. On Ubuntu 24.04's GCC 13 add `-Wno-error=format-truncation` (see PR #18).
The Spark's listen daemon needs a locked-memory limit that covers both mailbox halves.

**Check:**
- Mac: `printf 'STATUS\n' | nc -U /tmp/mcdma-rpcd.sock` says `up`.
- Spark: `printf 'STATUS\n' | nc -U -q1 /tmp/mcdma-rpcd.$LINK.sock` says `up`.

## 5. Producer on the Spark

Download the NVFP4 checkpoint into `~/.cache/huggingface`, put its snapshot hash in `NVFP4_SNAPSHOT`, then:

```bash
setsid -f spark/memwatch.sh > /dev/null 2>&1 < /dev/null
spark/run-producer.sh
```

The first start compiles and tunes b12x kernels for 10 minutes or more. `CACHE_DIR` keeps the results, and later
starts take about 2 minutes. The producer mounts the link daemon's socket, so restart the producer whenever
`start-link.sh` runs again.

Why the flags are what they are:

| Flag | Why |
|---|---|
| `--kv-cache-dtype auto` (bf16) | handoffs refuse fp8 caches |
| `--max-num-seqs 1` | the connector records QSA raw index keys by position, for the one request being prefilled |
| `--no-enable-prefix-caching` | each request keeps one private recurrent-state block until the Mac closes the handoff |
| `--recurrent-checkpoint-policy aligned` | this build's QSA guard admits export-only connectors under it |
| `--speculative-config` mtp, 1 token | the producer returns one token; MTP runs so the handoff carries the MTP head's cache |
| `seccomp=unconfined` | the disk-backed PLE table uses io_uring |
| `--gpu-memory-utilization 0.70`, `B12X_COMPILE_WORKERS=2` | headroom for b12x tuning; see pitfalls |
| NVFP4 checkpoint | the GPTQ and AutoRound checkpoints did not load on the b12x linear path |

**Check:** `curl http://$SPARK_HOST:$SPARK_PORT/health` answers. `docker logs` shows these connector lines:
- `recording raw QSA index keys`;
- `recording the MTP drafter's target hidden states`;
- `Creating v1 connector with name: MCDMAKVConnector`.

## 6. Decoder on the Mac

```bash
git clone -b feat/remote-prefill-hybrid https://github.com/Aileuxe/omlx "$OMLX_DIR"
cd "$OMLX_DIR" && python3.12 -m venv .venv && .venv/bin/pip install -e .
mkdir -p "$OMLX_BASE" && openssl rand -hex 24 > "$OMLX_BASE/.api-key" && chmod 600 "$OMLX_BASE/.api-key"
```

Turn Lightning MTP on for the model in `$OMLX_BASE/model_settings.json`:

```json
{"version": 1, "models": {"Qwen3.8-Flash-Next-oQ4e-mtp": {"mtp_enabled": true}}}
```

Then run `mac/install-agents.sh` (step 4) if you have not already. It starts `mac/omlx-split.sh` under
`taskpolicy -a`. Without that wrapper, launchd runs oMLX at the default scheduling role, and decode drops by a third.
The same fix for oMLX's own `brew services` job is proposed upstream.

**Check:** `$OMLX_BASE/logs/omlx.log` shows `Remote prefill for Qwen3.8-Flash-Next-oQ4e-mtp … over worker-a`.

## 7. Verify end to end

```bash
export API_KEY=$(cat "$OMLX_BASE/.api-key")
python3 bench/bench.py split http://127.0.0.1:$OMLX_PORT Qwen3.8-Flash-Next-oQ4e-mtp 6500 501 502
python3 bench/copybench.py copy http://127.0.0.1:$OMLX_PORT Qwen3.8-Flash-Next-oQ4e-mtp <some.py> 1 300
```

`bench.py` plants a passphrase in an 8k-token document, so `needle: true` means the handed-over state is right.
`copybench.py` has the model rewrite a source file, which shows what MTP drafting gains.

The oMLX log should show, per long request:
- `Remote prefill of N tokens, prefill … s, transfer … s`;
- then `MTP path activated … primed=N`, with `N` the whole prompt.

A `primed` of a few tokens means the MTP head started without the prompt; the producer's log says why.

Prompts shorter than 4,096 uncached tokens prefill on the Mac (`OMLX_REMOTE_PREFILL_MIN_TOKENS`). Anything that
fails falls back to local prefill, with the reason in the log.
