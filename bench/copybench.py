#!/usr/bin/env python3 -I
"""Copy-heavy chat benchmark: a source file in the prompt, an answer that mostly repeats it.

usage: copybench.py LABEL BASE_URL MODEL FILE FIRST_LINE LAST_LINE
env: API_KEY (optional bearer token), MAX_TOKENS (default 512)
Prints one JSON line: prompt tokens, time to first token, decode tok/s after the first token, total seconds.
Speculative decoding gains most here, and its draft head needs the prompt to predict the copy.
"""
import json, os, sys, time, urllib.request

label, base, model, path = sys.argv[1], sys.argv[2].rstrip('/'), sys.argv[3], sys.argv[4]
first, last = int(sys.argv[5]), int(sys.argv[6])
code = ''.join(open(path).readlines()[first - 1:last])
prompt = (f'```python\n{code}```\n\nRewrite the code above unchanged except that every local variable named `ctx` '
          'becomes `context`. Output only the code, starting from its first line.')
headers = {'Content-Type': 'application/json'}
if os.environ.get('API_KEY'):
    headers['Authorization'] = 'Bearer ' + os.environ['API_KEY']
payload = {'model': model, 'stream': True, 'max_tokens': int(os.environ.get('MAX_TOKENS', '512')), 'temperature': 0,
           'chat_template_kwargs': {'enable_thinking': False}, 'stream_options': {'include_usage': True},
           'messages': [{'role': 'user', 'content': prompt}]}
req = urllib.request.Request(f'{base}/v1/chat/completions', method='POST', headers=headers,
                             data=json.dumps(payload).encode())
start, ttft, usage = time.time(), None, {}
with urllib.request.urlopen(req, timeout=1800) as r:
    for line in r:
        line = line.decode().strip()
        if not line.startswith('data:') or line == 'data: [DONE]':
            continue
        chunk = json.loads(line[5:])
        usage = chunk.get('usage') or usage
        for c in chunk.get('choices', []):
            if ttft is None and (c.get('delta') or {}).get('content'):
                ttft = time.time() - start
total = time.time() - start
n = usage.get('completion_tokens', 0)
print(json.dumps({'setup': label, 'prompt_tokens': usage.get('prompt_tokens'), 'ttft_s': round(ttft or 0, 2),
                  'decode_tok_s': round((n - 1) / (total - ttft), 1) if ttft and n > 1 and total > ttft else None,
                  'total_s': round(total, 2), 'answer_tokens': n}), flush=True)
