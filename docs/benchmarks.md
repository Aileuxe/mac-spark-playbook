# Benchmarks

Measured on 10 October 2026, between 18:46 and 19:24, with `bench/suite.py`. Every row averages two runs that used the
same prompts in each setup. Every run is greedy with thinking off and stops at 512 answer tokens or at the end of the
answer.

## Setups

| Setup | Prefill | Decode |
|---|---|---|
| **Split** | vLLM on the Spark (NVFP4, bf16 KV, MTP drafter on for the head's history) for prompts of 4,096+ tokens; shorter prompts prefill on the Mac | oMLX on the Mac (oQ4e), Lightning MTP primed with the whole prompt |
| **Mac only** | oMLX on the Mac | the same oMLX, Lightning MTP |
| **Spark only (TensorFold)** | TensorFold on the Spark (INT4 AutoRound, fp8 KV) | the same TensorFold, its own drafts on |

TensorFold is the fastest single-Spark server we had for this model. Its checkpoint and drafter differ from the split's,
so compare whole setups, not quantizations.

## Tasks

- **Prose:** a long document with a passphrase planted in it. The answer quotes the passphrase, then writes an essay.
  The check is that the passphrase appears in the answer. The document repeats one filler sentence, which makes
  prefill unrealistically cheap for the model's n-gram layer; see the findings.
- **Code:** Python files from a real project, up to the target length. The answer repeats one file from the middle
  of the context. The check is the similarity of the answer to that file. Copying from the prompt is where drafting
  pays most.

## Columns

| Column | Meaning |
|---|---|
| First token | time to the first answer token, as a client sees it |
| Prefill tok/s | prompt tokens ÷ first-token time, end to end |
| Decode tok/s | answer tokens after the first ÷ the time they took |
| Draft tokens/step | tokens each MTP draft-and-verify step produced, from oMLX's log |
| Check | runs that passed. Speeds average only the runs that passed; see the anomalies |

### Prose

| Prompt | Setup | First token s | Prefill tok/s | Decode tok/s | Total s | Draft tokens/step | Check |
|---:|---|---:|---:|---:|---:|---:|---|
| 508 | Split | 0.7 | 728 | 75.1 | 7.5 | 2.02 | 2/2 ok |
| 509 | Mac only | 0.7 | 692 | 74.0 | 7.6 | 2.12 | 2/2 ok |
| 509 | Spark only (TensorFold) | 0.4 | 1,294 | 44.6 | 11.9 |  | 2/2 ok |
| 2,006 | Split | 1.8 | 1,115 | 68.1 | 9.3 | 1.91 | 2/2 ok |
| 2,007 | Mac only | 1.8 | 1,092 | 64.2 | 9.8 | 2.08 | 2/2 ok |
| 2,007 | Spark only (TensorFold) | 0.8 | 2,562 | 46.5 | 11.8 |  | 2/2 ok |
| 7,992 | Split | 5.2 | 1,532 | 63.2 | 13.3 | 1.92 | 2/2 ok |
| 7,994 | Mac only | 9.4 | 854 | 63.7 | 17.4 | 1.86 | 1/2 ok |
| 7,994 | Spark only (TensorFold) | 3.1 | 2,610 | 47.1 | 13.9 |  | 2/2 ok |
| 15,974 | Split | 8.8 | 1,809 | 62.4 | 17.0 | 2.09 | 2/2 ok |
| 15,976 | Mac only | 19.2 | 832 | 60.3 | 27.7 | 1.83 | 2/2 ok |
| 15,976 | Spark only (TensorFold) | 6.1 | 2,622 | 48.2 | 16.7 |  | 2/2 ok |
| 31,942 | Split | 16.1 | 1,978 | 57.8 | 25.0 | 2.09 | 2/2 ok |
| 31,942 | Mac only | 41.4 | 772 | 45.0 | 54.2 | 2.23 | 2/2 ok |
| 31,942 | Spark only (TensorFold) | 12.4 | 2,578 | 43.1 | 24.2 |  | 2/2 ok |
| 55,892 | Split | 27.9 | 2,006 | 59.4 | 36.5 | 2.18 | 2/2 ok |
| 55,892 | Mac only | 72.7 | 768 | 56.9 | 81.7 | 2.20 | 2/2 ok |
| 55,892 | Spark only (TensorFold) | 23.0 | 2,430 | 42.1 | 35.1 |  | 2/2 ok |

### Code

| Prompt | Setup | First token s | Prefill tok/s | Decode tok/s | Total s | Draft tokens/step | Check |
|---:|---|---:|---:|---:|---:|---:|---|
| 690 | Split | 0.9 | 803 | 105.2 | 1.4 | 3.32 | 2/2 ok (1.00–1.00) |
| 691 | Mac only | 0.9 | 793 | 104.9 | 1.4 | 3.32 | 2/2 ok (1.00–1.00) |
| 691 | Spark only (TensorFold) | 1.0 | 682 | 149.4 | 1.4 |  | 2/2 ok (1.00–1.00) |
| 2,432 | Split | 2.5 | 978 | 115.9 | 6.4 | 3.88 | 2/2 ok (0.99–1.00) |
| 2,432 | Mac only | 2.5 | 958 | 113.8 | 6.6 | 3.73 | 2/2 ok (0.99–0.99) |
| 2,432 | Spark only (TensorFold) | 2.2 | 1,116 | 262.1 | 4.0 |  | 2/2 ok (0.99–0.99) |
| 10,313 | Split | 6.8 | 1,516 | 110.0 | 11.4 | 3.87 | 2/2 ok (0.97–1.00) |
| 11,334 | Mac only | 13.8 | 820 | 104.2 | 18.7 | 3.88 | 1/2 ok (1.00–1.00) |
| 10,314 | Spark only (TensorFold) | 6.3 | 1,628 | 258.4 | 8.3 |  | 2/2 ok (0.98–1.00) |
| 18,386 | Split | 10.9 | 1,690 | 102.3 | 15.9 | 3.88 | 2/2 ok (0.98–0.98) |
| 18,387 | Mac only | 23.4 | 786 | 98.9 | 28.6 | 3.82 | 2/2 ok (0.98–0.98) |
| 18,387 | Spark only (TensorFold) | 14.5 | 1,273 | 254.2 | 16.5 |  | 2/2 ok (0.98–0.98) |
| 36,212 | Split | 19.8 | 1,825 | 92.4 | 25.4 | 3.79 | 2/2 ok (0.98–1.00) |
| 36,213 | Mac only | 52.7 | 696 | 89.8 | 58.4 | 3.73 | 2/2 ok (0.98–1.00) |
| 36,213 | Spark only (TensorFold) | 28.4 | 1,278 | 171.4 | 31.3 |  | 2/2 ok (0.98–1.00) |
| 63,504 | Split | 34.5 | 1,838 | 84.8 | 40.6 | 3.70 | 2/2 ok (0.98–1.00) |
| 63,505 | Mac only | 84.4 | 752 | 76.9 | 91.1 | 3.85 | 2/2 ok (1.00–1.00) |
| 63,505 | Spark only (TensorFold) | 57.5 | 1,112 | 154.5 | 60.8 |  | 2/2 ok (1.00–1.00) |

### Where the first token goes: Split

| Task | Prompt | Producer prefill s | Producer tok/s | Transfer s | MB | Gbit/s | Mac rest s |
|---|---:|---:|---:|---:|---:|---:|---:|
| prose | 7,992 | 3.23 | 2,476 | 0.35 | 355 | 8.2 | 1.64 |
| prose | 15,974 | 6.55 | 2,438 | 0.57 | 594 | 8.3 | 1.71 |
| prose | 31,942 | 13.37 | 2,389 | 1.06 | 1,072 | 8.1 | 1.72 |
| prose | 55,892 | 24.35 | 2,295 | 1.64 | 1,790 | 8.8 | 1.88 |
| code | 10,313 | 4.74 | 2,172 | 0.41 | 424 | 8.3 | 1.64 |
| code | 18,386 | 8.52 | 2,157 | 0.63 | 666 | 8.5 | 1.74 |
| code | 36,212 | 16.94 | 2,137 | 1.13 | 1,200 | 8.6 | 1.77 |
| code | 63,504 | 30.77 | 2,064 | 1.87 | 2,018 | 8.7 | 1.91 |

The prompts below 4,096 tokens are below the split's threshold, so the split and Mac-only rows are the same work
there. The breakdown starts at 8k for the same reason. In it, "Mac rest" is everything else before the first token:
request setup, building the caches from the handoff, the generation prompt's few tokens, and the first decode step.

## Findings

**Prose.**
- The split and TensorFold finish level at every length from 8k up: 13.3 against 13.9 s at 8k, 25.0 against 24.2 s
  at 32k, 36.5 against 35.1 s at 56k.
- TensorFold gives the first token 2–5 s sooner. The split decodes faster, 58–63 against 42–48 tok/s.
- On prose, drafting gets about 2 tokens per step whether or not the head saw the prompt.

**Code.**
- **Up to 16k tokens, TensorFold wins**, through its decode: its drafts copy at 254–262 tok/s, against 102–116 for
  oMLX's MTP head.
- **From 32k on, the split wins**, through its prefill: 25.4 against 31.3 s at 36k, 40.6 against 60.8 s at 64k.
  vLLM prefills code at 2,060–2,170 tok/s on the same Spark, and TensorFold at 1,110–1,630.
- Code prefills slower than prose on both Spark servers. TensorFold drops to about half its prose rate, vLLM by about
  12 %. The model's PLE layer looks up n-grams in a 51 GB table, and varied text touches more of it than the filler.
  Treat the code rows as the realistic prefill numbers.

**Mac only.**
- It decodes like the split (it is the same decoder) but prefills at 700–850 tok/s.
- From 8k up it is the slowest setup, and at 56–64k it takes over twice as long as the split.

**The handoff.**
- The Spark's prefill is 62–87 % of the split's first token, more the longer the prompt.
- The transfer ran at 8.1–8.8 Gbit/s, 0.35–1.9 s.
- The Mac's own part stayed at 1.6–1.9 s whatever the length.

## Anomalies

- **Two Mac-only runs looped.** Both were first runs at the 8k size (one prose, one code). Each answered with a
  repetition loop: 3.91 tokens per step, 379 of 380 drafts accepted, passphrase or file missing. The same two prompt
  sizes passed 14 times in reruns, alone and in sequence, and no split or TensorFold run looped. The cause is not
  known, and we have no saved answer from a looping run. The two runs are left out of the averages and counted in
  Check.
- **The Mac's decode rate depends on what else uses its GPU.** Short prose decoded at 55–82 tok/s at different hours
  of the same day; the sweeps here ran within 45 minutes of each other.
- **Each one-machine sweep overlapped other work on the other machine.** While the Mac-only sweep ran, the Spark
  served a first TensorFold sweep. That sweep was discarded, because it could not tell reasoning from answer tokens;
  it had none. While the TensorFold sweep shown ran, the Mac served the reruns above. Each sweep used only its own
  machine, and the benchmark client on the Mac is light.

## Reproduce

```bash
export API_KEY=$(cat "$OMLX_BASE/.api-key")
python3 bench/suite.py split http://127.0.0.1:8100 Qwen3.8-Flash-Next-oQ4e-mtp --code-dir <a Python tree> \
  --seed 200000 --out split.jsonl --save-dir answers/
python3 bench/omlx_log_stats.py "$OMLX_BASE/logs/omlx.log" --since "<first run's time>" > split-log.jsonl
python3 bench/report.py "Split=split.jsonl:split-log.jsonl" "Mac only=mac.jsonl:mac-log.jsonl" "TensorFold=tf.jsonl"
```

For Mac only, restart the decoder with `OMLX_REMOTE_PREFILL_MIN_TOKENS` set very high. For TensorFold, stop the
producer and point the suite at TensorFold's endpoint. The code task used oMLX's own `omlx/` source tree, and the raw
results are in `bench/results/`. `--seed 200000` reproduces our prompts when `--code-dir` is oMLX at the same commit
(`714fc57a`).
