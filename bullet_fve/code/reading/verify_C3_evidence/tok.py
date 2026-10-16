import pickle
from transformers import AutoTokenizer
P = '${OLENS_SCRATCH}/olens-bullet-fve/reading/verify_C3_evidence/rows.pkl'
D = pickle.load(open(P, 'rb'))
tok = AutoTokenizer.from_pretrained('${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9', local_files_only=True)
texts = [r['text'] for r in D['rows']]
ids = tok(texts, add_special_tokens=False)['input_ids']
for r, i in zip(D['rows'], ids): r['ntok'] = len(i)
pickle.dump(D, open(P, 'wb'))
import numpy as np
print(np.percentile([r['ntok'] for r in D['rows']], [5, 25, 50, 75, 95]))
