#!/usr/bin/env python3 -I
"""End-to-end chat benchmark: long prompt, long answer. Measures what a user waits for.

usage: bench.py LABEL BASE_URL MODEL TARGET_WORDS SEED [SEED ...]
env: API_KEY (optional bearer token), MAX_TOKENS (default 512)
Prints one JSON line per request: prompt tokens, time to first token, decode tok/s over the
answer after the first token, total seconds, answer tokens and whether the needle was found.
"""
import json, os, random, sys, time, urllib.request

label, base, model, words = sys.argv[1], sys.argv[2].rstrip('/'), sys.argv[3], int(sys.argv[4])
seeds = [int(s) for s in sys.argv[5:]]
max_tokens = int(os.environ.get('MAX_TOKENS', '512'))
FILLER = ("The archive room held ledgers from the old harbour office, each page listing cargo, weather and the "
          "names of the clerks on duty. ").split()
headers = {'Content-Type': 'application/json'}
if os.environ.get('API_KEY'):
    headers['Authorization'] = 'Bearer ' + os.environ['API_KEY']

for seed in seeds:
    rng = random.Random(seed)
    phrase = '-'.join(rng.choice(['amber', 'cobalt', 'falcon', 'granite', 'harbor', 'juniper', 'lumen', 'meridian',
                                  'nimbus', 'onyx', 'quartz', 'sable', 'tundra', 'vesper']) for _ in range(3))
    phrase += f'-{rng.randrange(1000, 9999)}'
    body = [FILLER[i % len(FILLER)] for i in range(words)]
    body.insert(rng.randrange(words // 4, 3 * words // 4), f' The secret passphrase is {phrase}. ')
    prompt = (f'Document {seed}:\n' + ' '.join(body) +
              '\n\nFirst give the secret passphrase from the document on its own line. Then write a detailed, '
              'flowing essay of at least 800 words about how harbour offices kept their ledgers, without lists.')
    payload = {'model': model, 'stream': True, 'max_tokens': max_tokens, 'temperature': 0,
               'chat_template_kwargs': {'enable_thinking': False}, 'stream_options': {'include_usage': True},
               'messages': [{'role': 'user', 'content': prompt}]}
    req = urllib.request.Request(f'{base}/v1/chat/completions', method='POST', headers=headers,
                                 data=json.dumps(payload).encode())
    start, first, text, usage = time.time(), None, '', {}
    with urllib.request.urlopen(req, timeout=1800) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith('data:') or line == 'data: [DONE]':
                continue
            chunk = json.loads(line[5:])
            usage = chunk.get('usage') or usage
            for c in chunk.get('choices', []):
                delta = (c.get('delta') or {}).get('content') or ''
                if delta and first is None:
                    first = time.time() - start
                text += delta
    total = time.time() - start
    n = usage.get('completion_tokens', 0)
    print(json.dumps({'setup': label, 'seed': seed, 'prompt_tokens': usage.get('prompt_tokens'),
                      'ttft_s': round(first or 0, 2), 'decode_tok_s': round((n - 1) / (total - first), 1)
                      if first and n > 1 and total > first else None, 'total_s': round(total, 2),
                      'answer_tokens': n, 'needle': phrase in text}), flush=True)
