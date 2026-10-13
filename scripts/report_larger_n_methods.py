"""Produce compact, source-bound tables from the completed sparse pilot."""
import csv
import hashlib
import io
import json
from pathlib import Path
import statistics

ROOT=Path('${OLENS_DATA_ROOT}/larger-n-methods-v1/quality-all')
FAMILIES=['hallucination','multihop_mt','chain_intermediates','role_bound_association']
TITLES=['Hallucination (chat)','Multihop (multi-token)','Chained intermediates','Role-bound association']
METHODS=[('More samples','best_n_exact',32),('Remove weak bullets','prune_loo_best_0.005',32),
 ('Combine bullets','pooled_greedy_swap',32),('Combine + prune','pooled_greedy_swap_then_prune_0.005',32),
 ('Keep repeats','consensus_semantic_v5_support0.125_compaton_vetoon',16),('Edit pooled text','editing_round2',32)]
report=json.loads((ROOT/'report.json').read_text())
arms={r['condition']:r for r in report['conditions']}
assert all(r['measurement_complete'] for r in arms.values()) and len(arms)==14
selections=[json.loads(l) for l in (ROOT/'selections.jsonl').read_text().splitlines()]
rows=[]
for arm in arms.values():
 for f in FAMILIES:
  metrics=arm['families'][f]['metrics'];name='contradiction_rate' if f=='hallucination' else 'cell_recovery';m=metrics[name]
  fits=[];tokens=[];bullets=[]
  for r in selections:
   if r['family']!=f:continue
   s=next(s for s in r['selections'] if f"{s['method']}-n{s['n']}"==arm['condition'])
   value=(s.get('fits') or {}).get('exact',{}).get('fve')
   if value is not None:fits.append(value)
   if 'token_count' in s:tokens.append(s['token_count'])
   if 'bullet_count' in s:bullets.append(s['bullet_count'])
  rows.append({'condition':arm['condition'],'family':f,'endpoint':name,'numerator':m['numerator'],
   'denominator':m['denominator'],'rate':m['value'],'ci95':m['ci95'],'expected_sites':8,
   'empty_outputs':arm['families'][f]['empty_abstentions'],'missing_stage1':arm['families'][f]['missing_stage1'],
   'missing_stage2':arm['families'][f]['missing_stage2'],'mean_fve':statistics.mean(fits) if len(fits)==8 else None,
   'fve_sites':len(fits),'mean_qwen_tokens':statistics.mean(tokens) if len(tokens)==8 else None,
   'mean_bullets':statistics.mean(bullets) if len(bullets)==8 else None,
   'assertion_share':metrics.get('assertion_share',{}).get('value')})
lookup={(r['condition'],r['family']):r for r in rows}
def count(cid,f):
 r=lookup[cid,f]
 return f"{r['numerator']}/{r['denominator']}" if r['denominator'] else 'undefined (0 specific)'
lines=['# N64 methods on the fixed 32-site pilot','',
 'Completed exploratory comparison on eight activation sites per task. These are **site-level results**, not full-grid question success rates. All four tasks use their unchanged evaluators; both hallucination stages are complete.',
 '', 'The original released lens gives 5/8 contradictory specific readouts, 0/8 multihop recoveries, 1/8 chained-intermediate recoveries and 0/8 role-binding recoveries on these sites. Its separate four-bullet reference has the same totals.',
 '', 'Each cell below is the old sample budget → 64. The old budget is 32 except Keep repeats, whose displayed reference used 16. Lower hallucination contradiction counts are better; higher recovery counts are better.',
 '', '| Method | Hallucination (chat): wrong/specific | Multihop (multi-token): recovered/8 | Chained intermediates: recovered/8 | Role-bound association: recovered/8 |',
 '|---|---:|---:|---:|---:|']
for label,method,n in METHODS:
 lines.append('| '+label+(' (16 → 64)' if n==16 else ' (32 → 64)')+' | '+ ' | '.join(count(f'{method}-n{n}',f)+' → '+count(f'{method}-n64',f) for f in FAMILIES)+' |')
lines += ['', 'At N64, Keep repeats emits no text at all eight hallucination sites and all eight multihop sites; it abstains at 24/32 sites overall. An undefined contradiction rate is not evidence of perfect accuracy. Other methods retain specific assertions on all eight hallucination sites.',
 '', 'Best-of-64 reduces observed contradictions by one readout (5/8 → 4/8); its grouped paired 95% interval is −37.5 to 0 percentage points. With only seven or eight independent groups, unchanged counts and zero-variation intervals do not establish equivalence or generalization.',
 '', '## AR reconstruction', '', 'Mean fraction of variance explained, in percent. Reconstruction is a selection metric, not a correctness score.',
 '', '| Method | Hallucination (chat) | Multihop (multi-token) | Chained intermediates | Role-bound association |','|---|---:|---:|---:|---:|']
def fit(cid,f):
 v=lookup[cid,f]['mean_fve'];return f'{100*v:.2f}' if v is not None else 'unavailable'
for label,method,n in METHODS:
 lines.append('| '+label+(' (16 → 64)' if n==16 else ' (32 → 64)')+' | '+' | '.join(fit(f'{method}-n{n}',f)+' → '+fit(f'{method}-n64',f) for f in FAMILIES)+' |')
lines += ['', '## Evidence and limits','',
 '- Eight-site results have very low precision. The sites were previously inspected; all findings are exploratory.',
 '- The fixed settings were carried forward without searching these outcomes. Original raw N1, capped N1 and actual method parents remain distinct.',
 '- A higher reconstruction score does not imply fewer false claims. Removing entire bullets can change interpretation and judge decisions; measured label changes are not proof of newly introduced factual content.',
 '- False-span tallies and true/unverifiable claim tallies have different segmentation and cannot be read as uniform claim precision.',
 '- All candidates came from the saved pool. Editing added only candidate-only helper calls and AR encodings, with unchanged-parent fallback.',
 '', 'The complete report, source hashes, judgments and paired intervals are preserved under `'+str(ROOT)+'`. The companion CSV gives native rates, uncertainty, assertion share, empty outputs and reconstruction for every condition–task pair.']
Path('docs/LARGER_N_METHODS_REPORT.md').write_text('\n'.join(lines)+'\n')
buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
Path('docs/reviews/larger-n-methods-v1.csv').write_text(buf.getvalue())
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'report.json',ROOT/'approval.json',ROOT/'selections.jsonl',ROOT/'original-replay-audit.json']}
receipt={'status':'complete','scope':'32 fixed development activation sites, eight per task; not full-grid question results',
 'conditions':14,'condition_task_records':56,'missing_required_verdicts':0,'rows':rows,
 'paired_comparisons':report['paired_comparisons'],'costs':json.loads((ROOT/'costs.json').read_text()),
 'source_sha256':sources,'gpu_steps':[{'job_step':'25637237.10','seconds':36},{'job_step':'25637237.11','seconds':30}],
 'new_h200_step_hours':66/3600,'new_oracle_lens_samples':0,'new_edit_ar_vectors':191,
 'site_publication':'No site changes in this experiment; the 469-question public plots remain unchanged.'}
Path('docs/reviews/larger-n-methods-v1.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('\n'.join(lines[:20]))
