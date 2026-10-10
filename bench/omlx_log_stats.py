#!/usr/bin/env python3 -I
"""Per-request breakdown from an oMLX log: remote prefill, transfer and MTP drafting.

usage: omlx_log_stats.py LOG [--since 'YYYY-MM-DD HH:MM:SS']
Prints one JSON line per finished chat completion: its time, prompt and answer tokens, and when
the request was prefilled on the producer, the tokens it covered, the producer's prefill seconds,
the transfer seconds and size; with Lightning MTP, tokens per draft step and draft acceptance.
Join it with suite.py's output on prompt_tokens and order.
"""
import argparse, json, re

STAMP = r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)'
REMOTE = re.compile(STAMP + r'.*Remote prefill of (\d+) tokens, prefill ([\d.]+) s, transfer ([\d.]+) s '
                    r'\(([\d.]+) Gbit/s, (\d+) MB\)')
MTP = re.compile(STAMP + r'.*MTP\[\d+\] finish=\S+ tokens=(\d+) cycles=(\d+) tok/cycle=([\d.]+) '
                 r'accept=(\d+)/(\d+)')
DONE = re.compile(STAMP + r'.*Chat completion: .*?(\d+) tokens in [\d.]+s .*?prompt: (\d+)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('log')
    parser.add_argument('--since', default='')
    args = parser.parse_args()
    remote = mtp = None
    for line in open(args.log, errors='replace'):
        if line[:19] < args.since:
            continue
        if (m := REMOTE.match(line)):
            remote = {'remote_tokens': int(m[2]), 'spark_prefill_s': float(m[3]), 'transfer_s': float(m[4]),
                      'gbit_s': float(m[5]), 'mb': int(m[6])}
        elif (m := MTP.match(line)):
            accepted, drafted = int(m[5]), int(m[6])
            mtp = {'tok_per_step': float(m[4]), 'accept': round(accepted / drafted, 3) if drafted else None}
        elif (m := DONE.match(line)):
            row = {'time': m[1], 'prompt_tokens': int(m[3]), 'answer_tokens': int(m[2])}
            row.update(remote or {})
            row.update(mtp or {})
            print(json.dumps(row))
            remote = mtp = None


if __name__ == '__main__':
    main()
