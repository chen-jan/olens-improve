"""Compact rendering of coordinator-reviewed, sanitized development case cards."""
from __future__ import annotations

import html
import json
import re

PANEL_SHA = '36aa5977c631a84b1fceca0cfd22d60de7de58e124930ab7503ed617acefc5cf'
PANEL_IDS = (
    'hallucination|chat-lmsys-0052|L20|p00253',
    'hallucination|chat-lmsys-0023|L60|p00464',
    'multihop_mt|mhh-1967-norwegian-classes-objects-codesigner|L44|p00028',
    'multihop_mt|mhh-mesopotamian-wildman-cedar|L60|p00046',
    'chain_intermediates|chain-w2-d2p-0013|L60|p00062',
    'chain_intermediates|chain-d2p-0385|L20|p00066',
    'role_bound_association|oa-waiter-customer-apologize-ab|L20|p00092',
    'role_bound_association|oa-comedian-heckler-humiliate-ab|L60|p00178',
)
PRIVATE = re.compile(r'/orcd/|/home/|/tmp/|(?:SLURM_JOB_ID|chatcmpl-|sk-[A-Za-z0-9]{12})')
DEFAULT_VARIANTS = {
    'sample_selection':'best_n_exact-n32',
    'consensus':'consensus_exact_support0.125-n16',
    'pruning':'prune_loo_a32_0.005-n32',
    'pooling':'pooled_greedy_swap-n32',
    'contrastive_checks':'best_n_specificity_mean-n32',
    'editing':'editing_round2-n32',
    'combinations':'best_n_specificity_mean_then_prune_0.005-n32',
}


def esc(value):
    return html.escape(str(value), quote=True)


def validated(section):
    if (section.get('status') != 'root_reviewed'
            or section.get('stage') != 'development_pilot'
            or section.get('panel_sha256') != PANEL_SHA):
        raise ValueError('Qualitative cards require the reviewed fixed development panel')
    anchors = section.get('anchors', [])
    ids = [a['cell_id'] for a in anchors]
    if tuple(ids) != PANEL_IDS:
        raise ValueError('Keep every fixed anchor, including missing examples')
    for method in section.get('methods', {}).values():
        if len(method.get('supplements', [])) > 2:
            raise ValueError('At most two separate supplements per method')
        variants = method.get('variants', [])
        if len({v['id'] for v in variants}) != len(variants):
            raise ValueError('Ambiguous qualitative variant')
        for variant in variants:
            if [c['cell_id'] for c in variant['cases']] != ids:
                raise ValueError('Variant must retain the exact ordered panel')
    if PRIVATE.search(json.dumps(section, ensure_ascii=False)):
        raise ValueError('Public qualitative evidence still contains private infrastructure')
    return section


def block(title, value):
    if value is None:
        value = 'Evidence unavailable; no inference from missing data.'
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return f'<details class="case-detail"><summary>{esc(title)}</summary><pre>{esc(text)}</pre></details>'


def card(case):
    if case.get('status') == 'unavailable':
        return '<p class="missing">' + esc(case.get('reason', 'No retained diagnostic at this anchor.')) + '</p>'
    out = '<div class="trace-pair">'
    for key, label in [('baseline', 'Before'), ('proposed', 'After')]:
        row = case.get(key)
        if row is None:
            # G is a token diagnostic, never fabricate a chosen prose output.
            continue
        out += f'<div><h5>{label} · {esc(row.get("label", ""))}</h5><pre>{esc(row["text"])}</pre>'
        if row['text'] == '':
            out += '<p class="small">Empty output: abstention, not missing evidence.</p>'
        if row.get('verdict') is not None:
            out += '<p class="small">Official result: ' + esc(row['verdict']) + '</p>'
        out += '</div>'
    out += '</div>'
    if case.get('assessment_scope')=='method_variants':
        out += '<p class="small">Review across this method’s variants; not a separate verdict for every selected setting.</p>'
    out += '<p>' + esc(case.get('assessment', '')) + '</p>'
    if case.get('unchanged'):
        out += '<p class="small">Exact text unchanged from its parent.</p>'
    if case.get('diagnostic') is not None:
        out += block('Token or controlled-phrase diagnostic · no prose-quality verdict', case['diagnostic'])
    out += block('Original context and answer rule · review only', case.get('context'))
    if case.get('original_readouts'):
        out += block('Original single sample · raw and shortened', case['original_readouts'])
    out += block('Retained judge evidence · not reviewer endorsement', case.get('judge_evidence'))
    out += block('Source identifiers, lengths and scoring limits', case.get('provenance'))
    return out


def method_cards(section, key):
    if not section:
        return ''
    validated(section)
    method = section['methods'].get(key)
    if not method:
        return ''
    variants = method.get('variants', [])
    out = '<details class="shared-cases"><summary>Eight shared examples: exact before and after</summary>'
    out += '<p class="small">Fixed development pilot, two different items and related groups per task. Illustrations explain changes; they are not improvement rates. Missing and unchanged cases remain visible.</p>'
    out += '<p>' + esc(method.get('takeaway', '')) + '</p>'
    if variants:
        out += f'<div class="case-controls"><label>Example<select data-case-anchor="{esc(key)}">'
        for i, a in enumerate(section['anchors']):
            out += f'<option value="{i}">{esc(a["label"])}</option>'
        out += '</select></label>'
        out += f'<label>Variant<select data-case-variant="{esc(key)}">'
        default=next((i for i,v in enumerate(variants) if v['id']==DEFAULT_VARIANTS.get(key)),0)
        for i, v in enumerate(variants):
            out += f'<option value="{i}"'+(' selected' if i==default else '')+f'>{esc(v["label"])}</option>'
        out += '</select></label></div>'
        case = variants[default]['cases'][0]
        context = section.get('contexts', {}).get(case.get('context_ref'))
        if context is not None:
            case = case | {'context':context}
        case = case | {'original_readouts':section.get('original_readouts',{}).get(case['cell_id'])}
        out += f'<div data-case-current="{esc(key)}"><p class="small">' + esc(case['cell_id']) + '</p>' + card(case) + '</div>'
        out += '<noscript><p class="small">The first fixed example remains readable here. Download the evidence file to inspect other examples without JavaScript.</p></noscript>'
    supplements = method.get('supplements', [])
    if supplements:
        out += '<details><summary>Separate rare-change examples · selected after outcomes</summary><p class="small">These do not replace the fixed examples and do not establish a population rate.</p>'
        for s in supplements:
            s=s|{'context':section.get('contexts',{}).get(s.get('context_ref'),s.get('context')),
                 'original_readouts':section.get('original_readouts',{}).get(s['cell_id'])}
            out += '<details class="trace"><summary>' + esc(s['label']) + '</summary>' + card(s) + '</details>'
        out += '</details>'
    out += '<p class="small"><a href="qualitative-evidence.json" download>Download the complete reviewed, sanitized case evidence</a></p></details>'
    return out


CSS = '''.case-controls{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:20px 0}.case-controls label{font-size:12px;color:var(--muted)}.case-controls select{display:block;margin-top:6px;width:100%;font:inherit;padding:9px;background:white;border:1px solid var(--line);border-radius:4px}.shared-cases pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 'Segoe UI',Arial,sans-serif;padding:14px;background:#F2F6FA;max-height:420px;overflow:auto}.case-detail{padding:9px 0}.case-detail summary{font-size:12px}.shared-cases>summary{font-size:15px}@media(max-width:760px){.case-controls{grid-template-columns:1fr}.case-controls select{font-size:13px}}'''
JS = r'''(()=>{
let evidencePromise;
const value=x=>typeof x==='string'?x:JSON.stringify(x,null,2);
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function detail(label,body){const n=node('details',undefined,'case-detail');n.append(node('summary',label),node('pre',body==null?'Evidence unavailable; no inference from missing data.':value(body)));return n;}
function show(target,c,contexts,originals){target.replaceChildren(node('p',c.cell_id,'small'));
if(c.status==='unavailable'){target.append(node('p',c.reason||'No retained diagnostic at this anchor.','missing'));return;}
const pair=node('div',undefined,'trace-pair');for(const [key,label] of [['baseline','Before'],['proposed','After']]){const r=c[key];if(!r)continue;const col=node('div');col.append(node('h5',label+' · '+(r.label||'')),node('pre',r.text));if(r.text==='')col.append(node('p','Empty output: abstention, not missing evidence.','small'));if(r.verdict!=null)col.append(node('p','Official result: '+value(r.verdict),'small'));pair.append(col);}target.append(pair);if(c.assessment_scope==='method_variants')target.append(node('p','Review across this method’s variants; not a separate verdict for every selected setting.','small'));target.append(node('p',c.assessment||''));
if(c.unchanged)target.append(node('p','Exact text unchanged from its parent.','small'));
if(c.diagnostic!=null)target.append(detail('Token or controlled-phrase diagnostic · no prose-quality verdict',c.diagnostic));
target.append(detail('Original context and answer rule · review only',contexts[c.context_ref]||c.context));if(originals[c.cell_id])target.append(detail('Original single sample · raw and shortened',originals[c.cell_id]));target.append(detail('Retained judge evidence · not reviewer endorsement',c.judge_evidence),detail('Source identifiers, lengths and scoring limits',c.provenance));}
function evidence(){if(!evidencePromise)evidencePromise=fetch('qualitative-evidence.json',{cache:'force-cache'}).then(r=>{if(!r.ok)throw Error('Evidence fetch failed');return r.json();}).then(r=>{if(r.status!=='root_reviewed'||r.stage!=='development_pilot'||r.panel_sha256!=='36aa5977c631a84b1fceca0cfd22d60de7de58e124930ab7503ed617acefc5cf')throw Error('Unreviewed evidence');return r;});return evidencePromise;}
document.querySelectorAll('[data-case-anchor]').forEach(anchor=>{const key=anchor.dataset.caseAnchor;const variant=document.querySelector('[data-case-variant="'+key+'"]'),target=document.querySelector('[data-case-current="'+key+'"]');let version=0;async function update(){const current=++version;target.setAttribute('aria-busy','true');try{const data=await evidence();if(current!==version)return;const c=data.methods[key].variants[Number(variant.value)].cases[Number(anchor.value)];show(target,c,data.contexts||{},data.original_readouts||{});}catch(e){if(current===version)target.replaceChildren(node('p','The selected evidence could not be loaded. Use the complete evidence download; missing data are not zero.','missing'));}finally{if(current===version)target.removeAttribute('aria-busy');}}anchor.addEventListener('change',update);variant.addEventListener('change',update);});
})();'''
