"""Prepare disjoint AR inputs, encode isolated workers, or merge validated catalogs."""
import argparse
from collections import OrderedDict
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace
import torch
from transformers import AutoTokenizer
from olens_improve.ar_cache import digest, input_records, vector_key
from olens_improve.ar_partition import partition_for, read_cache, merge_catalog,validate_stage
from olens_improve.reconstruction import ar_token_ids
from olens_improve.selection import parse_bullets, PARSER_POLICY


def check_checkpoint(checkpoint,contract):
    for relative,field in [('heads.pt','head_sha256'),('meta.json','meta_sha256'),
                           ('lora/adapter_config.json','adapter_config_sha256'),
                           ('lora/adapter_model.safetensors','adapter_sha256')]:
        if sha256((Path(checkpoint)/relative).read_bytes()).hexdigest()!=contract[field]:
            raise ValueError('Checkpoint differs from prepared/inherited contract: '+field)


def prepare(a):
    manifest_body=a.manifest.read_bytes();fresh_body=a.fresh_manifest.read_bytes();gate_body=a.gate.read_bytes()
    manifest_sha=sha256(manifest_body).hexdigest();fresh_sha=sha256(fresh_body).hexdigest()
    stage,cells,captures=validate_stage(json.loads(manifest_body),manifest_sha,json.loads(fresh_body),fresh_sha,json.loads(gate_body))
    contract,known,sources=read_cache(a.inherited)
    check_checkpoint(a.checkpoint,contract)
    if contract['span_limit']!=32 or contract['tokenizer_cleanup']!='source_scaffolding_and_special_ids_v1':
        raise ValueError('Unsupported scorer input contract')
    state=torch.load(a.checkpoint/'heads.pt',map_location='cpu',weights_only=True)
    tags={int(l):state['tag_ids'][i].tolist() for i,l in enumerate(state['layers'])}
    runtime=json.loads(a.runtime.read_text())
    tokenizer=AutoTokenizer.from_pretrained(runtime['paths']['base_snapshot'],local_files_only=True)
    count=lambda s:len(tokenizer(s,add_special_tokens=False)['input_ids'])
    pending=OrderedDict();usages=[];inputs=[];seen=set();by_cell={}
    for path in a.input:
        body=path.read_bytes();source_sha=sha256(body).hexdigest()
        status_path=path.with_suffix('.status.json');flat_meta=path.with_suffix('.manifest.json')
        if status_path.exists():
            status=json.loads(status_path.read_text())
            if status['status']!='complete' or status['journal_sha256']!=source_sha:
                raise ValueError('Input journal lacks matching terminal status')
        elif flat_meta.exists():
            status=json.loads(flat_meta.read_text())
            if status.get('flat_sha256')!=source_sha or status.get('cohort_manifest_sha256')!=manifest_sha:
                raise ValueError('Flat snapshot does not bind this exact stage cohort')
            for parent,expected in status['parent_journal_sha256'].items():
                parent_path=Path(parent);actual=sha256(parent_path.read_bytes()).hexdigest()
                terminal=json.loads(parent_path.with_suffix('.status.json').read_text())
                if actual!=expected or terminal['status']!='complete' or terminal['journal_sha256']!=expected:
                    raise ValueError('Flat snapshot parent journal is not immutable/terminal')
        else:raise ValueError('Require terminal journal or source-bound immutable flat snapshot')
        inputs.append({'path':str(path.resolve()),'sha256':source_sha})
        for row in input_records(body):
            cid,index,layer=row['cell_id'],row['sample_index'],int(row['layer'])
            if cid not in cells:raise ValueError('Off-cohort source cell')
            if row.get('split',stage)!=stage:raise ValueError('Input contains another split')
            if any(row[k]!=cells[cid][k] for k in ('family','item_id','layer','position')):
                raise ValueError('Input cell identity differs from frozen cohort')
            if row['activation_sha256']!=captures[cid]['activation_sha256']:
                raise ValueError('Input activation does not match verified fresh capture')
            if (cid,index) in seen:raise ValueError('Duplicate source cell/sample')
            seen.add((cid,index))
            if not isinstance(index,int) or isinstance(index,bool) or not 0<=index<32:
                raise ValueError('Invalid source sample index')
            by_cell.setdefault(cid,set()).add(index)
            if layer not in tags or layer not in range(20,61,4):raise ValueError('Off-contract layer')
            pool=row.get('global_pool_id',row.get('pool_id'))
            if pool is None:raise ValueError('Missing pool provenance')
            sample=parse_bullets(row['text'],f'{pool}:{cid}:{index}',index,token_count=count,max_output_tokens=256)
            for bullet in sample.bullets:
                cleaned,ids=ar_token_ids(tokenizer,bullet.text);scored=ids[:32]
                key=vector_key(contract['sha256'],tags[layer],scored) if scored else None
                usages.append({'cell_id':cid,'pool_id':pool,'activation_sha256':row['activation_sha256'],
                    'sample_index':index,'source_phrase_id':bullet.phrase_id,'layer':layer,'text':bullet.text,
                    'scored_text':cleaned,'span_start':bullet.start,'span_end':bullet.end,
                    'parser_flags':list(sample.flags),'parser_policy':PARSER_POLICY,
                    'original_token_count':len(ids),'scored_token_count':len(scored),'scored_token_ids':scored,
                    'unscored_suffix_ids':ids[32:],'truncated':len(ids)>32,'cache_key':key,
                    'status':'encoded_or_cache_hit' if scored else 'empty_after_cleanup'})
                if key is not None and key not in known and key not in pending:
                    pending[key]={'phrase_id':key,'cache_key':key,'text':bullet.text,'layer':layer,
                                  'scored_token_ids':scored,'tag_ids':tags[layer],
                                  'split':stage,'frozen_test_authorized':stage=='test'}
    if by_cell.keys()!=cells.keys() or any(indices!=set(range(32)) for indices in by_cell.values()):
        raise ValueError('Require complete frozen N32 input cells')
    if a.output.exists():raise ValueError('Prepared directory already exists')
    a.output.mkdir(parents=True)
    usage_body=''.join(json.dumps(r)+'\n' for r in usages).encode()
    usage=a.output/'usage.jsonl';usage.write_bytes(usage_body)
    partitions=[]
    for number in range(a.count):
        body=''.join(json.dumps(r)+'\n' for k,r in pending.items() if partition_for(k,a.count)==number).encode()
        path=a.output/f'partition_{number:03d}.jsonl';path.write_bytes(body)
        partitions.append({'path':str(path.resolve()),'sha256':sha256(body).hexdigest(),
                           'keys':sum(partition_for(k,a.count)==number for k in pending)})
    plan={'contract':contract,'inherited_directory':str(a.inherited.resolve()),
          'stage':stage,'manifest_sha256':manifest_sha,'fresh_manifest_sha256':fresh_sha,
          'coordinator_gate_sha256':sha256(gate_body).hexdigest(),
          'inherited_keys_sha256':digest(sorted(known)),'inherited_sources':sources,
          'inputs':inputs,'partition_count':a.count,'partitions':partitions,'new_keys':len(pending),
          'batch_size':128,'usage':{'path':str(usage.resolve()),'sha256':sha256(usage_body).hexdigest()},
          'preparation_code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
          'execution_code_sha256':{str(p):sha256(p.read_bytes()).hexdigest() for p in
              [Path('scripts/encode_candidates.py'),Path('src/olens_improve/reconstruction.py'),
               Path('src/olens_improve/selection.py')]},
          'policy':'SHA256 effective-input key modulo partition count; no duplicated writers'}
    (a.output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for path in a.output.iterdir():path.chmod(0o444)
    return {'new_keys':len(pending),'partition_keys':[p['keys'] for p in partitions],'usage_rows':len(usages)}


def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='command',required=True)
    q=subs.add_parser('prepare')
    q.add_argument('--input',action='append',type=Path,required=True)
    q.add_argument('--inherited',type=Path,required=True);q.add_argument('--count',type=int,choices=(2,3,4),required=True)
    q.add_argument('--checkpoint',type=Path,required=True);q.add_argument('--runtime',type=Path,default=Path('configs/runtime.json'))
    q.add_argument('--output',type=Path,required=True)
    q.add_argument('--manifest',type=Path,required=True);q.add_argument('--fresh-manifest',type=Path,required=True)
    q.add_argument('--gate',type=Path,required=True)
    q=subs.add_parser('encode')
    q.add_argument('--plan',type=Path,required=True);q.add_argument('--index',type=int,required=True)
    q.add_argument('--checkpoint',type=Path,required=True);q.add_argument('--runtime',default='configs/runtime.json')
    q.add_argument('--output',type=Path,required=True)
    q=subs.add_parser('merge')
    q.add_argument('--plan',type=Path,required=True);q.add_argument('--worker-cache',action='append',type=Path,required=True)
    q.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use allocated resources')
    if a.command=='prepare':result=prepare(a)
    else:
        plan=json.loads(a.plan.read_text())
        if a.command=='merge':result=merge_catalog(plan,plan['inherited_directory'],a.worker_cache,a.output)
        else:
            if not 0<=a.index<plan['partition_count']:raise ValueError('Invalid partition index')
            part=plan['partitions'][a.index];body=Path(part['path']).read_bytes()
            if sha256(body).hexdigest()!=part['sha256']:raise ValueError('Partition changed')
            check_checkpoint(a.checkpoint,plan['contract'])
            if any(sha256(Path(p).read_bytes()).hexdigest()!=s for p,s in plan['execution_code_sha256'].items()):
                raise ValueError('Prepared encoder/scorer source changed')
            # The unchanged encoder operates only on prepared new keys in an isolated output root.
            from encode_candidates import encode_snapshot
            args=SimpleNamespace(runtime=a.runtime,input=[part['path']],input_kind='phrases',checkpoint=str(a.checkpoint),
                output=str(a.output),batch_size=128,shard_size=4096,max_output_tokens=256)
            encode_snapshot(args)
            result={'partition':a.index,'status':'encoded','output_root':str(a.output)}
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
