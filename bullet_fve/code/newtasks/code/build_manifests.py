"""Phase 0 (CPU, tokenizer only): build the capture and generation manifests from design/sites.jsonl.

- capture.json: every position of each item's capture window x 5 layers (15,980 cells), in the
  format OI/scripts/capture_cells.py consumes unchanged ({cell_id, family, item_id, layer, position,
  token, capture_spec}). capture_spec uses OI pool_worker.render: UM = 'chat' (system + user), CA =
  'chat_summarize' (stimulus + suffix). Rendered ids are checked against WSB's own producer render.
- gen_p0.json / gen_ca.json / gen_umA.json / gen_umB.json: the generation cells per stage.
  umA may drop template roles (only ever drop, per the P0 rule) with --um-drop-role.

Usage: python -B build_manifests.py [--um-drop-role ROLE ...] [--only-gen]
Writes only under newtasks/data/manifests.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

C.setup_paths()
OUT = C.DATA / 'manifests'
SUFFIX = '\n\nSummarize the preceding story in one sentence.'
P0_LAYERS = (36, 52)
P0_PER_SUBFAMILY = 5


def capture_spec(family, item):
    if family == 'user_modeling':
        msgs = item['messages']
        assert [m['role'] for m in msgs] == ['system', 'user'], item['name']
        return {'family': family, 'id': item['name'], 'render': 'chat',
                'system': msgs[0]['content'], 'text': msgs[1]['content']}
    return {'family': family, 'id': item['id'], 'render': 'chat_summarize',
            'text': item['stimulus'], 'suffix': SUFFIX}


def pick_p0_items(bank):
    """5 selfdescribe + 5 synthsys, seeded order, one item per attribute class first."""
    from wsbench.mc import seed_int
    chosen = []
    for sub in ('selfdescribe', 'synthsys'):
        items = sorted((it for it in bank.values() if it['subfamily'] == sub),
                       key=lambda it: seed_int(f'nt-p0:{C.SEED}:{it["name"]}'))
        picked, classes = [], set()
        for it in items:
            if it['attr_class'] not in classes and len(picked) < P0_PER_SUBFAMILY:
                picked.append(it['name']); classes.add(it['attr_class'])
        for it in items:
            if len(picked) >= P0_PER_SUBFAMILY:
                break
            if it['name'] not in picked:
                picked.append(it['name'])
        chosen += picked
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--um-drop-role', action='append', default=[],
                    help='planned UM Tier A role to drop after the P0 rule (drop-only)')
    ap.add_argument('--only-gen', action='store_true', help='rebuild generation manifests only')
    args = ap.parse_args()
    from transformers import AutoTokenizer
    from pool_worker import render as oi_render
    from wsbench.readplan import plan, resolve
    from wsbench.produce.render import render as wsb_render

    tok = AutoTokenizer.from_pretrained(str(C.BASE), local_files_only=True)
    sites = C.load_sites()
    banks = {f: C.load_bank(f) for f in C.FAMILIES.values()}
    wsb_specs = {(f, s.id): s for f in C.FAMILIES.values() for s in plan(f)}
    stats = collections.Counter()
    capture_cells, by_item = [], {}
    for row in sites:
        fam, iid = row['family'], row['id']
        item = banks[fam][iid]
        spec = capture_spec(fam, item)
        ids = oi_render(spec, tok)
        wr = wsb_render(wsb_specs[(fam, iid)], tok)
        if ids != wr.ids:
            raise SystemExit(f'render mismatch vs WSB producer: {iid}')
        stats['render_parity_ok'] += 1
        n = len(ids)
        assert n == row['n_tokens'], (iid, n, row['n_tokens'])
        span = resolve(wsb_specs[(fam, iid)].positions, wr.tokens)
        assert [span[0], span[-1]] == row['wsb_span'], (iid, span[0], span[-1], row['wsb_span'])
        decoded = [tok.decode([i]) for i in ids]
        for s in row['planned_sites']:
            assert decoded[s['pos']] == s['token'], (iid, s)
            assert s['pos'] in row['capture_positions'], (iid, s)
        by_item[(fam, iid)] = {'row': row, 'decoded': decoded, 'span': set(span), 'n': n}
        for pos in row['capture_positions']:
            for layer in C.LAYERS:
                capture_cells.append({'cell_id': C.cell_id(fam, iid, layer, pos), 'family': fam, 'item_id': iid,
                                      'layer': layer, 'position': pos, 'token': decoded[pos],
                                      'rel_from_end': n - 1 - pos, 'in_wsb_span': pos in span,
                                      'capture_spec': spec})
                stats[f'capture_cells[{C.SHORT[fam]}]'] += 1
    OUT.mkdir(parents=True, exist_ok=True)
    cap_path = OUT / 'capture.json'
    capture = {'schema': 'nt-capture-v1', 'split': 'development', 'benchmark_commit': C.WSB_COMMIT,
               'layers': list(C.LAYERS), 'cells': capture_cells,
               'note': 'adapter-free decoder-block output, OI capture_cells.py unchanged'}
    body = json.dumps(capture, indent=1, ensure_ascii=False) + '\n'
    if args.only_gen:
        if C.sha(cap_path.read_bytes()) != C.sha(body.encode()):
            raise SystemExit('capture manifest would change; refuse with --only-gen')
    elif cap_path.exists() and cap_path.read_text() != body:
        if (C.DATA / 'capture/capture_state.json').exists():
            raise SystemExit('capture already started with a different manifest; refuse to overwrite')
        C.atomic_text(cap_path, body)
    else:
        C.atomic_text(cap_path, body)
    cap_ids = {c['cell_id'] for c in capture_cells}

    def gen_cell(fam, iid, layer, site, extra=None):
        d = by_item[(fam, iid)]
        pos = site['pos']
        cid = C.cell_id(fam, iid, layer, pos)
        assert cid in cap_ids, cid
        return {'cell_id': cid, 'family': fam, 'item_id': iid, 'layer': layer, 'position': pos,
                'token': d['decoded'][pos], 'rel_from_end': d['n'] - 1 - pos,
                'tier': site.get('tier'), 'role': site.get('role'), **(extra or {})}

    manifests = {k: [] for k in C.STAGES}
    p0_items = pick_p0_items(banks['user_modeling'])
    um_roles = collections.Counter()
    for row in sites:
        fam, iid = row['family'], row['id']
        for s in row['planned_sites']:
            if fam == 'user_modeling':
                um_roles[(s['tier'], s['role'])] += 1
        for layer in C.LAYERS:
            for s in row['planned_sites']:
                if fam == 'conjunctive_association':
                    manifests['ca'].append(gen_cell(fam, iid, layer, s))
                elif s['tier'] == 'A' and s['role'] not in args.um_drop_role:
                    manifests['umA'].append(gen_cell(fam, iid, layer, s))
                elif s['tier'] == 'B':
                    manifests['umB'].append(gen_cell(fam, iid, layer, s))
        if fam == 'user_modeling' and iid in p0_items:
            d = by_item[(fam, iid)]
            planned = {s['pos']: s for s in row['planned_sites']}
            for layer in P0_LAYERS:
                for pos in row['capture_positions']:
                    s = planned.get(pos, {'pos': pos, 'tier': None, 'role': f'unplanned rel {d["n"] - 1 - pos}'})
                    manifests['p0'].append(gen_cell(fam, iid, layer, s, {'in_wsb_span': pos in d['span']}))
    unknown = set(args.um_drop_role) - {r for (t, r) in um_roles if t == 'A'}
    if unknown:
        raise SystemExit(f'unknown UM Tier A role(s) to drop: {sorted(unknown)}')
    index = {'capture': {'path': str(cap_path), 'sha256': C.file_sha(cap_path), 'cells': len(capture_cells)},
             'um_drop_roles': sorted(args.um_drop_role), 'p0_items': p0_items,
             'um_roles': {f'{t}|{r}': n for (t, r), n in sorted(um_roles.items())}}
    for stage, cells in manifests.items():
        fam, n, shards = C.STAGES[stage]
        path = OUT / f'gen_{stage}.json'
        payload = {'schema': 'nt-gen-v1', 'stage': stage, 'family': fam, 'n': n, 'shard_count': shards,
                   'capture_manifest_sha256': index['capture']['sha256'], 'cells': cells}
        text = json.dumps(payload, indent=1, ensure_ascii=False) + '\n'
        gen_dir = C.stage_dir(stage)
        if path.exists() and path.read_text() != text and any(gen_dir.glob('shard-*.jsonl')):
            raise SystemExit(f'{stage}: generation already started from a different manifest; refuse')
        C.atomic_text(path, text)
        index[stage] = {'path': str(path), 'sha256': C.file_sha(path), 'cells': len(cells),
                        'items': len({c['item_id'] for c in cells}), 'n': n,
                        'readouts': len(cells) * n}
    C.atomic_json(OUT / 'index.json', index)
    print(json.dumps({'stats': dict(stats), **{k: v for k, v in index.items() if k != 'um_roles'}}, indent=1))


if __name__ == '__main__':
    main()
