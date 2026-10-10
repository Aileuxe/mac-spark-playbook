#!/usr/bin/env python3 -I
"""Benchmark sweep: prompt lengths x tasks against one OpenAI-compatible chat endpoint.

usage: suite.py LABEL BASE_URL MODEL --code-dir DIR [--lengths 500,2000,8000] [--reps 2]
                [--tasks prose,code] [--max-tokens 512] [--out results.jsonl]
env:   API_KEY (optional bearer token)

Two tasks, both greedy with thinking off, each run with a unique first line so no prefix cache helps:
  prose  a long document with a passphrase planted in it; the answer quotes the passphrase, then
         writes an essay. check = the passphrase is in the answer (the handed-over state is right).
  code   source files from --code-dir up to the target length; the answer repeats one file from
         the middle of the context verbatim. check = similarity of the answer to that file (0..1).
         Copying from the prompt is where speculative decoding with a primed MTP head pays most.
Per run it prints one JSON line: prompt tokens, time to first token, end-to-end prefill rate
(prompt tokens / time to first token), decode rate after the first token, total time, check.
"""
import argparse, difflib, json, os, pathlib, random, re, sys, time, urllib.request

FILLER = ("The archive room held ledgers from the old harbour office, each page listing cargo, weather and the "
          "names of the clerks on duty. ").split()
WORDS = ['amber', 'cobalt', 'falcon', 'granite', 'harbor', 'juniper', 'lumen', 'meridian', 'nimbus', 'onyx',
         'quartz', 'sable', 'tundra', 'vesper']
TOKENS_PER_WORD = 1.22   # Qwen3.8 tokenizer on FILLER
CHARS_PER_TOKEN = 4.5    # on Python source


def prose(label, length, seed):
    rng = random.Random(seed)
    phrase = '-'.join(rng.choice(WORDS) for _ in range(3)) + f'-{rng.randrange(1000, 9999)}'
    words = max(50, int(length / TOKENS_PER_WORD) - 60)
    body = [FILLER[i % len(FILLER)] for i in range(words)]
    body.insert(rng.randrange(words // 4, 3 * words // 4), f' The secret passphrase is {phrase}. ')
    prompt = (f'Document {label}-{seed}:\n' + ' '.join(body) +
              '\n\nFirst give the secret passphrase from the document on its own line. Then write a detailed, '
              'flowing essay of at least 800 words about how harbour offices kept their ledgers, without lists.')
    return prompt, lambda text: phrase in text


def code(label, length, seed, files):
    rng = random.Random(seed)
    budget = int(length * CHARS_PER_TOKEN)
    # The file to repeat sits in the middle of the context; other files fill the rest, and the
    # last one is cut at a line boundary so the prompt lands close to the target length.
    fits = [f for f in files if 1500 < len(f[1]) < min(12000, budget * 0.6)] or \
        sorted(files, key=lambda f: len(f[1]))[:1]
    target_path, target = rng.choice(fits)
    middle = f'# File: {target_path}\n{target}\n'
    others = [f for f in files if f[0] != target_path]
    rng.shuffle(others)

    def fill(room):
        out, used = [], 0
        for path, text in others:
            if used >= room:
                break
            block = f'# File: {path}\n{text}\n'
            cut = used + len(block) > room
            if cut:
                block = block[: block.rfind('\n', 0, room - used) + 1]
            out.append(block)
            used += len(block)
            if cut:
                break
        del others[: len(out)]
        return ''.join(out)

    side = max(0, budget - len(middle)) // 2
    context = fill(side) + middle + fill(side)
    prompt = (f'# Run {label}-{seed}\n' + context +
              f'\n\nRepeat the file `{target_path}` from the code above exactly as it is, from its first line. '
              'Output only the code in one code block.')

    def check(text):
        found = re.search(r'```[a-zA-Z]*\n(.*?)(```|$)', text, re.S)
        answer = (found.group(1) if found else text).strip('\n')
        if not answer:
            return 0.0
        return round(difflib.SequenceMatcher(None, answer, target[:len(answer)], autojunk=False).ratio(), 3)
    return prompt, check


def run(base, model, prompt, max_tokens):
    headers = {'Content-Type': 'application/json'}
    if os.environ.get('API_KEY'):
        headers['Authorization'] = 'Bearer ' + os.environ['API_KEY']
    payload = {'model': model, 'stream': True, 'max_tokens': max_tokens, 'temperature': 0,
               'chat_template_kwargs': {'enable_thinking': False}, 'stream_options': {'include_usage': True},
               'messages': [{'role': 'user', 'content': prompt}]}
    req = urllib.request.Request(f'{base}/v1/chat/completions', method='POST', headers=headers,
                                 data=json.dumps(payload).encode())
    start, first, first_any, text, reasoning, usage = time.time(), None, None, '', '', {}
    with urllib.request.urlopen(req, timeout=3600) as response:
        for line in response:
            line = line.decode().strip()
            if not line.startswith('data:') or line == 'data: [DONE]':
                continue
            chunk = json.loads(line[5:])
            usage = chunk.get('usage') or usage
            for choice in chunk.get('choices', []):
                delta = choice.get('delta') or {}
                content = delta.get('content') or ''
                # A server that thinks despite enable_thinking=False streams reasoning separately.
                thought = delta.get('reasoning_content') or delta.get('reasoning') or ''
                if (content or thought) and first_any is None:
                    first_any = time.time() - start
                if content and first is None:
                    first = time.time() - start
                text += content
                reasoning += thought
    return text, reasoning, first, first_any, time.time() - start, usage


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('label')
    parser.add_argument('base_url')
    parser.add_argument('model')
    parser.add_argument('--code-dir', required=True, help='a tree of .py files for the code task')
    parser.add_argument('--lengths', default='500,2000,8000,16000,32000,56000')
    parser.add_argument('--reps', type=int, default=2)
    parser.add_argument('--tasks', default='prose,code')
    parser.add_argument('--max-tokens', type=int, default=512)
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--out', help='append the JSON lines to this file too')
    parser.add_argument('--save-dir', help='write each answer (and any reasoning) to a file here')
    parser.add_argument('--only-seeds', help='comma-separated seeds to run, skipping the others')
    args = parser.parse_args()
    root = pathlib.Path(args.code_dir)
    files = sorted((str(p.relative_to(root)), p.read_text(errors='replace'))
                   for p in root.rglob('*.py') if 200 < p.stat().st_size < 60000)
    out = open(args.out, 'a') if args.out else None
    seed = args.seed
    # One short request first: the first after a load or an idle spell pays one-off setup.
    run(args.base_url.rstrip('/'), args.model, f'Warm-up {args.label}: say ok.', 8)
    for length in (int(x) for x in args.lengths.split(',')):
        for task in args.tasks.split(','):
            for _ in range(args.reps):
                seed += 1
                if args.only_seeds and str(seed) not in args.only_seeds.split(','):
                    continue
                prompt, check = prose(args.label, length, seed) if task == 'prose' else \
                    code(args.label, length, seed, files)
                text, reasoning, first, first_any, total, usage = run(args.base_url.rstrip('/'), args.model,
                                                                      prompt, args.max_tokens)
                if args.save_dir:
                    pathlib.Path(args.save_dir).mkdir(parents=True, exist_ok=True)
                    pathlib.Path(args.save_dir, f'{args.label}-{task}-{length}-{seed}.txt').write_text(
                        (f'--- reasoning\n{reasoning}\n--- answer\n' if reasoning else '') + text)
                n, p = usage.get('completion_tokens', 0), usage.get('prompt_tokens')
                row = {'setup': args.label, 'task': task, 'target': length, 'seed': seed, 'prompt_tokens': p,
                       'ttft_s': round(first or 0, 2),
                       'prefill_tok_s': round(p / first) if p and first else None,
                       # Over every generated token, reasoning included, from the first one of any kind.
                       'decode_tok_s': round((n - 1) / (total - first_any), 1)
                       if first_any and n > 1 and total > first_any else None,
                       'total_s': round(total, 2), 'answer_tokens': n, 'check': check(text),
                       'first_output_s': round(first_any or 0, 2), 'reasoning_chars': len(reasoning),
                       'time': time.strftime('%Y-%m-%dT%H:%M:%S')}
                line = json.dumps(row)
                print(line, flush=True)
                if out:
                    out.write(line + '\n')
                    out.flush()


if __name__ == '__main__':
    sys.exit(main())
