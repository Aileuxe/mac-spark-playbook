#!/usr/bin/env python3 -I
"""Markdown tables from suite.py results, optionally joined with omlx_log_stats.py output.

usage: report.py SETUP=RESULTS.jsonl[:LOGSTATS.jsonl] ...
Each setup's runs are averaged per task and target length (two runs each in our sweeps). Runs
whose answer failed its check (passphrase missing, or code copied below 0.9 similarity) are left
out of the averages, since a degenerate answer decodes unrealistically fast; the Check column
counts them.
A log-stats file adds the producer's prefill rate, the transfer and MTP drafting per request,
matched to the results by prompt tokens in order.
"""
import json, sys
from statistics import mean


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def joined(results, stats):
    rows, i = [], 0
    for run in results:
        extra = {}
        for j in range(i, len(stats)):
            if stats[j]['prompt_tokens'] == run['prompt_tokens']:
                extra, i = stats[j], j + 1
                break
        rows.append({**run, **{k: v for k, v in extra.items() if k not in run}})
    return rows


def fmt(value, digits=1):
    if value is None:
        return ''
    return f'{value:,.{digits}f}' if isinstance(value, float) else f'{value:,}'


def ok(run):
    return run['check'] is True if run['task'] == 'prose' else run['check'] >= 0.9


def avg(rows, key):
    values = [r[key] for r in rows if r.get(key) is not None]
    return mean(values) if values else None


def main():
    setups = []
    for arg in sys.argv[1:]:
        name, files = arg.split('=', 1)
        results, _, stats = files.partition(':')
        setups.append((name, joined(load(results), load(stats) if stats else [])))
    for task in ('prose', 'code'):
        print(f'\n### {task.capitalize()}\n')
        print('| Prompt | Setup | First token s | Prefill tok/s | Decode tok/s | Total s | Draft tokens/step | '
              'Check |')
        print('|---:|---|---:|---:|---:|---:|---:|---|')
        targets = sorted({r['target'] for _, rows in setups for r in rows if r['task'] == task})
        for target in targets:
            for name, rows in setups:
                group = [r for r in rows if r['task'] == task and r['target'] == target]
                if not group:
                    continue
                passed = [r for r in group if ok(r)]
                check = f'{len(passed)}/{len(group)} ok'
                if task == 'code' and passed:
                    check += f" ({min(r['check'] for r in passed):.2f}–{max(r['check'] for r in passed):.2f})"
                group = passed or group
                print(f"| {fmt(round(avg(group, 'prompt_tokens')))} | {name} | {fmt(avg(group, 'ttft_s'))} | "
                      f"{fmt(round(avg(group, 'prefill_tok_s')))} | {fmt(avg(group, 'decode_tok_s'))} | "
                      f"{fmt(avg(group, 'total_s'))} | {fmt(avg(group, 'tok_per_step'), 2)} | {check} |")
    split = [(name, rows) for name, rows in setups if any('spark_prefill_s' in r for r in rows)]
    for name, rows in split:
        print(f'\n### Where the first token goes: {name}\n')
        print('| Task | Prompt | Producer prefill s | Producer tok/s | Transfer s | MB | Gbit/s | Mac rest s |')
        print('|---|---:|---:|---:|---:|---:|---:|---:|')
        for task in ('prose', 'code'):
            for target in sorted({r['target'] for r in rows if r['task'] == task}):
                group = [r for r in rows if r['task'] == task and r['target'] == target and 'spark_prefill_s' in r
                         and ok(r)]
                if not group:
                    continue
                prefill, transfer = avg(group, 'spark_prefill_s'), avg(group, 'transfer_s')
                rate = mean(r['remote_tokens'] / r['spark_prefill_s'] for r in group)
                rest = avg(group, 'ttft_s') - prefill - transfer
                print(f"| {task} | {fmt(round(avg(group, 'prompt_tokens')))} | {fmt(prefill, 2)} | {fmt(round(rate))} | "
                      f"{fmt(transfer, 2)} | {fmt(round(avg(group, 'mb')))} | {fmt(avg(group, 'gbit_s'))} | "
                      f"{fmt(rest, 2)} |")


if __name__ == '__main__':
    main()
