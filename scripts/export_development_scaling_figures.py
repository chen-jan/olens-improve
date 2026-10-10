"""Plot the reviewed DEV rates and intervals; no aggregation or curve fitting."""
import argparse
import copy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path

FAMILIES=('hallucination','multihop_mt','chain_intermediates','role_bound_association')
PREFIXES=(1,2,4,8,16,32)
ORDER=['raw_n1-n1','capped_n1-n1']+[f'best_n_exact-n{n}'for n in PREFIXES]
TITLES=('Transcript contradictions','Multi-hop bridge','Numerical intermediates','Role binding')


def source_metrics(report,scope):
    if scope not in ('cell','item'):raise ValueError('Unknown metric scope')
    if report['status']!='complete_four_family_development_scaling':raise ValueError('Require completed DEV report')
    arms=report['measurement']['conditions']
    if [r['condition']for r in arms]!=ORDER or not all(r['measurement_complete']for r in arms):
        raise ValueError('Wrong prefix order or incomplete condition')
    data={}
    for family in FAMILIES:
        endpoint=('contradiction_rate'if family=='hallucination'else'cell_recovery')if scope=='cell'else(
            'original_grid_contradiction_rate'if family=='hallucination'else'original_grid_item_pass_rate')
        field='metrics'if scope=='cell'else'original_grid_metrics';data[family]=[]
        for arm in arms:
            metric=copy.deepcopy(arm['families'][family][field][endpoint])
            value=metric['value'];ci=metric.get('ci95')
            if metric['denominator']<=0 or value is None or not math.isfinite(value)or not 0<=value<=1:
                raise ValueError('Undefined/invalid rate must not be plotted as zero')
            if ci is not None and(len(ci)!=2 or not all(math.isfinite(v)for v in ci)or ci[0]>ci[1]):
                raise ValueError('Invalid supplied interval')
            data[family].append({'condition':arm['condition'],'endpoint':endpoint,'metric':metric})
    return data


def export(report,out,source_path,source_sha,reviewed_by):
    data={scope:source_metrics(report,scope)for scope in ('cell','item')}
    os.environ.setdefault('MPLCONFIGDIR','/tmp/olens-improve-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    out=Path(out)
    if out.exists():raise FileExistsError('Use a new immutable figure directory')
    out.mkdir(parents=True);files=[]
    for scope in ('cell','item'):
        fig,axes=plt.subplots(2,2,figsize=(15,9.5))
        fig.subplots_adjust(top=.87,bottom=.18,left=.07,right=.98,hspace=.42,wspace=.22)
        for ax,family,title in zip(axes.flat,FAMILIES,TITLES):
            rows=data[scope][family]
            for reference,color,style in [(rows[0],'#6f6f6f',':'),(rows[1],'#b36b2b','--')]:
                m=reference['metric'];ax.axhline(100*m['value'],color=color,linestyle=style,linewidth=1.5)
                if m.get('ci95')is not None:ax.axhspan(100*m['ci95'][0],100*m['ci95'][1],color=color,alpha=.045)
            rates=[100*r['metric']['value']for r in rows[2:]]
            ax.plot(PREFIXES,rates,'o-',color='#244e69',linewidth=1.7,markersize=5)
            for n,row in zip(PREFIXES,rows[2:]):
                m=row['metric'];ci=m.get('ci95')
                if ci is not None:
                    ax.vlines(n,100*ci[0],100*ci[1],color='#537990',linewidth=1.3)
                    ax.scatter([n,n],[100*ci[0],100*ci[1]],marker='_',color='#537990',s=40)
                ax.annotate(f"{m['numerator']}/{m['denominator']}",(n,100*m['value']),xytext=(0,8),
                            textcoords='offset points',ha='center',fontsize=8,
                            bbox={'facecolor':'white','edgecolor':'none','alpha':.8,'pad':1})
            bounds=[100*v for r in rows for v in(r['metric'].get('ci95')or[r['metric']['value']])]
            lo=0 if family!='hallucination'else max(0,min(bounds)-5)
            ax.set_ylim(lo,min(100,max(bounds)+8));ax.set_xscale('log',base=2);ax.set_xlim(.75,43)
            ax.set_xticks(PREFIXES,[str(n)for n in PREFIXES]);ax.set_xlabel('Recorded sample prefix N')
            unit=('Contradicted / specific readouts (%)\nLower is better'if family=='hallucination'else
                  'Passing cells (%)\nHigher is better'if scope=='cell'else'Items with any passing site (%)\nHigher is better')
            ax.set_ylabel(unit,fontsize=10);groups=rows[2]['metric']['independent_groups']
            ax.set_title(f'{title} — {groups} related groups',fontsize=12);ax.grid(alpha=.18)
            ax.spines[['top','right']].set_visible(False);raw,cap=[r['metric']for r in rows[:2]]
            ax.text(.02,.02,f"Raw N1: {raw['numerator']}/{raw['denominator']}; capped N1: {cap['numerator']}/{cap['denominator']}",
                    transform=ax.transAxes,fontsize=8,bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
        handles=[Line2D([],[],color='#244e69',marker='o',label='Best complete sample by exact reconstruction'),
                 Line2D([],[],color='#6f6f6f',linestyle=':',label='Released raw N1 reference'),
                 Line2D([],[],color='#b36b2b',linestyle='--',label='Capped N1 reference')]
        fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.09),ncol=3,frameon=False,fontsize=10)
        caption='Complete original DEV grids — '+('cell rates'if scope=='cell'else'original item aggregation')
        fig.suptitle(caption+'\nSupplied per-method 95% intervals; family-specific axis ranges',fontsize=15)
        fig.text(.5,.045,'Dots: source numerator/denominator. Lines only connect recorded prefixes; no fitted scaling law.\n'
                 'Reconstruction N1 differs from capped N1 by eligibility. Hall remains a readout ratio in both views;\n'
                 'recovery/role passes are not whole-output truth. Source SHA256 '+source_sha[:12],ha='center',fontsize=9)
        for extension in ('png','pdf'):
            p=out/f'development-scaling-{scope}.{extension}';fig.savefig(p,dpi=180,bbox_inches='tight',facecolor='white')
            files.append({'path':p.name,'sha256':sha256(p.read_bytes()).hexdigest()})
        plt.close(fig)
    receipt={'status':'exported_supplied_values_no_aggregation','created_utc':datetime.now(timezone.utc).isoformat(),
             'source':{'path':str(source_path),'sha256':source_sha},'reviewed_by':reviewed_by,'condition_order':ORDER,
             'sample_prefixes':list(PREFIXES),'plotted_source_metrics':data,'files':files,'matplotlib_version':matplotlib.__version__,
             'limits':['Supplied absolute per-method intervals, not paired-change or simultaneous bands.',
                       'Related-group intervals and warnings retained unchanged; no new statistics.',
                       'Complete original DEVELOPMENT grids only; no validation or TEST outcomes.',
                       'Raw/capped N1 are distinct from reconstruction N1; quality need not be monotonic.',
                       'Cost, fresh-input latency and GPU dollars are separate from these plots.']}
    (out/'figure-data.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n');return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True);p.add_argument('--reviewed-by',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw=a.report.read_bytes()
    if sha256(raw).hexdigest()!=a.expected_sha256:raise ValueError('Wrong reviewed report bytes')
    result=export(json.loads(raw),a.output,a.report,a.expected_sha256,a.reviewed_by)
    print(json.dumps({'output':str(a.output),'files':result['files']}))
