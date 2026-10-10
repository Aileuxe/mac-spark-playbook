# Pitfalls

What cost us time, roughly in the order we hit it.

**The enclosure on the wrong Mac.** With two Mac Studios on the desk, the Helios was first plugged into the other one.
Check `system_profiler SPThunderboltDataType` on the Mac you are working on.

**A macOS beta the driver does not know.** MCDMA allowlists exact macOS build IDs and refuses anything else. That is
deliberate: the kext uses private kernel interfaces. To allow 27.2 beta `26B5101f`, we compared its kernelcache with
the supported `26A428` first: fileset entries, IORDMAFamily ABI, PAC discriminators. That comparison is
`tools/compare-apple-build.py` and PR #17. Every macOS update repeats this step.

**Copies of the restore helper go stale.** The LaunchDaemon runs a copy of MCDMA's `restore-rdma.py`. An upstream
copy refused the beta build, and each failed retry deleted the Spark's neighbour entry. Install the copy from the
branch the driver was built from, and rerun `install-link-daemon.sh` after every rebuild.

**One link flap wedged the Mac's port until a reboot.** When the Spark's port bounced, Apple's GID cache dropped the
Mac's default GID. The driver reports the port active only once that GID is live, and it installed the GID only at
start. The fix (PR #19) re-installs it from the poll.

**The cable label.** The Thunderbolt cable says TB4 and negotiates 80 Gb/s TB5 with the Helios anyway. The QSFP link
runs at 40G. Neither limits anything here: a handoff moves at 7.6–9.4 Gbit/s, because of software.

**`pkill -f` from an ssh command line.** It also matches the ssh command itself, so it kills your own session. Use
`pkill -x NAME`.

**Prebuilt vLLM images.** NVIDIA's vLLM image was too old for `qwen4_exp`. vLLM 0.31.0 refused the PLE table of the
GPTQ checkpoint, or ran out of memory holding it resident. The b12x build loads the 51 GB n-gram table from disk
with io_uring (`seccomp=unconfined`), but its linear path does not take GPTQ weights. The NVFP4 checkpoint works.

**QSA guard.** b12x builds refuse KV connectors for QSA models unless the connector declares it can handle aligned
hybrid transfers. An export-only producer can (`supports_aligned_hybrid_transfer`), with
`--recurrent-checkpoint-policy aligned`.

**Index keys by layer name.** The first hook found QSA layers by their cache tensor's `data_ptr`, and missed layer 3.
It now uses the module's `layer_name`.

**MTP changes the producer in three places.**
- **Timing.** V1's model runner calls `wait_for_save` before the drafter writes its cache, so with MTP on the export
  waits for `get_finished`.
- **Conv windows.** Speculative decoding widens every Gated DeltaNet and PLE conv window by one slot per speculative
  token. Prefill fills the first slots, and that is what the export takes.
- **The head's last row.** It pairs the last prompt token with vLLM's own sampled token, so it is not prompt history
  and is left out.

**b12x tuning and the GB10's unified memory.** b12x tunes kernels after vLLM has taken its share of memory. Our
watchdog killed the producer three times, at 4–5 GiB available. Two compile workers, `--gpu-memory-utilization 0.70`
and a persisted tuning cache fixed it, and the KV cache still holds one 65k-token request. Without a watchdog the box
can hang.

**launchd and decode speed.** oMLX in a LaunchAgent decoded at 37 tok/s; the same command in a terminal ran at 50.
Neither `ProcessType Interactive` nor `taskpolicy -t 0 -l 0` helped. `taskpolicy -a`, the policies of an
application, did: 52–55 tok/s.

**The Mac's decode rate moves.** The same prompt decoded anywhere from 55 to 82 tok/s across one afternoon,
depending on what else used the GPU (the screen was in use). Compare runs taken minutes apart, not hours.

**oMLX needs an API key on 0.0.0.0.** Keep it in a 0600 file. If a gateway such as LiteLLM fronts the Mac, give it
the key from its own host-only environment file, never from a repository.
