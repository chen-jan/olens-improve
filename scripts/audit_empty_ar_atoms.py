"""Read-only null AR-key provenance scan and immutable generated-span join."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re

PATTERN=r'</?explanation>|<\|im_start\|>(system|user|assistant)?|<\|im_end\|>|<think>|</think>'


def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--samples',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Scan full usage rows inside a CPU allocation')
    output=Path(a.output)
    if output.exists():raise FileExistsError('Preserve the original audit')
    sources={};nulls={};total=0;duplicates=0
    for path in sorted(Path(a.cache).glob('usage_*.jsonl')):
        digest=sha256()
        with path.open('rb') as stream:
            for line in stream:
                digest.update(line);row=json.loads(line);total+=1
                if row['cache_key'] is not None:continue
                identity=(row['cell_id'],row['sample_index'],row['source_phrase_id'])
                if identity in nulls:
                    if nulls[identity]['row']!=row:raise ValueError('Conflicting null-atom provenance')
                    duplicates+=1;continue
                if row['scored_token_ids'] or row['scored_token_count'] or row['original_token_count'] or row['status']!='empty_after_cleanup':raise ValueError('Null key does not describe an empty AR input')
                raw=row['text'];cleaned=re.sub(PATTERN,'',raw).strip()
                category='whitespace' if not raw.strip() else 'special_only' if not cleaned else 'other'
                nulls[identity]={'row':row,'category':category,'raw_text_sha256':sha256(raw.encode()).hexdigest(),'raw_characters':len(raw),'short_raw_representation':repr(raw) if len(raw)<=64 else None,'cleanup_remaining_characters':len(cleaned)}
        sources[str(path)]={'sha256':digest.hexdigest(),'bytes':path.stat().st_size}
    samples_path=Path(a.samples);sample_ids={(identity[0],identity[1]) for identity in nulls};matched={};digest=sha256()
    with samples_path.open('rb') as stream:
        for line in stream:
            digest.update(line);sample=json.loads(line);identity=(sample['cell_id'],sample['sample_index'])
            if identity not in sample_ids:continue
            if identity in matched:raise ValueError('Duplicate generated sample')
            matched[identity]=sample
    if set(matched)!=sample_ids:raise ValueError('Null usage refers outside the frozen DEV sample snapshot')
    sources[str(samples_path)]={'sha256':digest.hexdigest(),'bytes':samples_path.stat().st_size}
    details=[]
    for identity,entry in sorted(nulls.items()):
        row=entry['row'];sample=matched[(identity[0],identity[1])]
        if row['activation_sha256']!=sample['activation_sha256'] or sample['text'][row['span_start']:row['span_end']]!=row['text']:
            raise ValueError('Empty atom span or activation differs from generated provenance')
        details.append({key:value for key,value in row.items() if key not in ('text','scored_text')}|{key:value for key,value in entry.items() if key!='row'}|{'generated_sample_sha256':sha256(sample['text'].encode()).hexdigest(),'generated_sample_characters':len(sample['text'])})
    n1=[row for row in details if row['sample_index']==0]
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sources,'usage_rows_scanned':total,'unique_null_bullets':len(details),'duplicate_identical_null_usage_rows':duplicates,'affected_samples':len(sample_ids),'affected_cells':len({identity[0] for identity in sample_ids}),'types':dict(Counter(row['category'] for row in details)),'n1_bullets':len(n1),'n1_cells':len({row['cell_id'] for row in n1}),'nulls_by_family':dict(Counter(row['cell_id'].split('|',1)[0] for row in details)),'short_raw_types':dict(Counter(row['short_raw_representation'] for row in details)),'details':details,'generated_span_matches':len(details),'boundary':'Read-only classification and exact span checks; no sample, parser, vector, selector, or judgment changes. Special-only means the released cleanup regex leaves no content.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('checked_utc','usage_rows_scanned','unique_null_bullets','duplicate_identical_null_usage_rows','affected_samples','affected_cells','types','n1_bullets','n1_cells','nulls_by_family','short_raw_types','generated_span_matches')},indent=2))


if __name__=='__main__':main()
