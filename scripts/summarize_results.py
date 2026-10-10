"""Aggregate local immutable judged artifacts without API calls."""
import argparse
import json
from pathlib import Path
from olens_improve.reporting import summarize, markdown, SELECTION_SHA

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--conditions', required=True)
    p.add_argument('--condition-root', required=True)
    p.add_argument('--selection-sha256', default=SELECTION_SHA)
    p.add_argument('--output', required=True)
    p.add_argument('--table', required=True)
    a=p.parse_args()
    report=summarize(a.manifest,a.conditions,a.condition_root,selection_sha=a.selection_sha256)
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
    Path(a.table).write_text(markdown(report))
    print(json.dumps({'complete':sum(x['measurement_complete'] for x in report['conditions']),'total':len(report['conditions']),'paired_comparisons':len(report['paired_comparisons'])}))
