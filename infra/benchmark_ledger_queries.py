"""Time actual hot ledger SELECTs on disposable local-XFS snapshots only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import statistics
import subprocess
import time

INDEXES = [
    "CREATE INDEX IF NOT EXISTS attempts_request_origin ON attempts(json_extract(metadata,'$.content_cache_key'),status,created_utc DESC)",
    "CREATE INDEX IF NOT EXISTS events_attempt_kind_sequence ON events(attempt_id,kind,sequence DESC)",
    "CREATE INDEX IF NOT EXISTS attempts_global_committed ON attempts(status,actual,reserved)",
    "CREATE INDEX IF NOT EXISTS attempts_run_committed ON attempts(run_id,status,actual,reserved)",
    "CREATE INDEX IF NOT EXISTS attempts_run_recovery ON attempts(run_id,created_utc DESC,status,reserved)",
]
SUM_SQL = "SELECT COALESCE(SUM(CASE WHEN status='settled' THEN actual WHEN status IN ('reserved','unknown') THEN reserved ELSE 0 END),0) FROM attempts"


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def plan(db, sql, params):
    return [row[3] for row in db.execute('EXPLAIN QUERY PLAN '+sql,params)]


def timings(db, sql, params, repeats=3):
    durations=[]; signatures=[]
    for _ in range(repeats):
        start=time.perf_counter();rows=db.execute(sql,params).fetchall();durations.append(time.perf_counter()-start)
        signatures.append(hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
    if len(set(signatures))!=1:raise RuntimeError('Disposable snapshot SELECT changed')
    return {'seconds':durations,'median_seconds':statistics.median(durations),'result_sha256':signatures[0],'row_count':len(rows)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--local',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--backup-seconds',type=float,default=45);parser.add_argument('--snapshot-input',type=Path);args=parser.parse_args()
    if args.local.exists():raise RuntimeError('Refuse existing disposable snapshot directory')
    if subprocess.check_output(['stat','-f','-c','%T',str(args.local.parent)],text=True).strip()!='xfs':raise RuntimeError('Require verified node-local XFS')
    args.local.mkdir(); pristine=args.local/'snapshot.sqlite3';work=args.local/'indexed.sqlite3'
    src=sqlite3.connect(args.source.as_uri()+'?mode=ro',uri=True,timeout=2);src.execute('PRAGMA query_only=ON')
    st=args.source.stat(); start=time.monotonic()
    def progress(status,remaining,total):
        if time.monotonic()-start>args.backup_seconds:raise TimeoutError('SQLite backup exceeded bounded wait; consistency not claimed')
    if args.snapshot_input:
        shutil.copyfile(args.snapshot_input,pristine)
        backup_seconds=None
    else:
        try:
            with sqlite3.connect(pristine) as dst:src.backup(dst,pages=512,progress=progress,sleep=.05)
        except BaseException:
            pristine.unlink(missing_ok=True);src.close();raise
        backup_seconds=time.monotonic()-start
    shutil.copyfile(pristine,work)
    db=sqlite3.connect(work);db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL')
    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Copied ledger integrity failed')
    representative=db.execute("SELECT attempt_id,run_id,json_extract(metadata,'$.content_cache_key'),json_extract(metadata,'$.transport_recovery_guard.since_utc') FROM attempts WHERE status='settled' AND json_extract(metadata,'$.content_cache_key') IS NOT NULL ORDER BY created_utc DESC LIMIT 1").fetchone()
    if representative is None:raise RuntimeError('No settled request-content example in snapshot')
    attempt_id,run_id,request_key,epoch=representative
    if epoch is None:raise RuntimeError('Most recent settled request lacks an actual recovery epoch')
    queries={
      'latest_settled_request_origin':("SELECT attempt_id,metadata FROM attempts WHERE status='settled' AND json_extract(metadata,'$.content_cache_key')=? ORDER BY created_utc DESC LIMIT 1",(request_key,)),
      'latest_physical_response':("SELECT details FROM events WHERE attempt_id=? AND kind='physical_response' ORDER BY sequence DESC LIMIT 1",(attempt_id,)),
      'global_committed':(SUM_SQL,()),
      'run_committed':(SUM_SQL+' WHERE run_id=?',(run_id,)),
      'recovery_latest100':('SELECT status FROM attempts WHERE run_id=? AND created_utc>=? ORDER BY created_utc DESC LIMIT 100',(run_id,epoch)),
      'recovery_unknown_reserved':("SELECT COALESCE(SUM(reserved),0) FROM attempts WHERE run_id=? AND created_utc>=? AND status='unknown'",(run_id,epoch)),
    }
    report={'schema_version':1,'checked_utc':datetime.now(timezone.utc).isoformat(),'source':str(args.source),'local_snapshot':str(pristine),'local_work_copy':str(work),'snapshot_consistent':True,'backup_seconds':backup_seconds,'snapshot_sha256':digest(pristine),'source_bytes_before':st.st_size,'source_bytes_after':args.source.stat().st_size,'snapshot_bytes':pristine.stat().st_size,'snapshot_bounds':{'attempts':db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],'events':db.execute('SELECT COUNT(*),MIN(sequence),MAX(sequence) FROM events').fetchone(),'attempt_status_counts':dict(db.execute('SELECT status,COUNT(*) FROM attempts GROUP BY status'))},'indexes':INDEXES,'representative_run_id':run_id,'recovery_epoch_used':epoch,'queries':{},'limits':['No production writes, indexes, migration or API calls.','Local-copy timings do not measure NFS lock/fsync latency.','Backup deadline is checked at progress callbacks; kernel I/O cannot be forcibly bounded by this callback.','Only sanitized plans/counts/timings and result digests are exported; no request keys, metadata, prompts or responses.']}
    for name,(sql,params) in queries.items():report['queries'][name]={'sql':sql,'production_plan':plan(src,sql,params),'before_plan':plan(db,sql,params),'before':timings(db,sql,params)}
    src.close();start=time.monotonic()
    for sql in INDEXES:db.execute(sql)
    db.commit();report['index_build_seconds']=time.monotonic()-start
    for name,(sql,params) in queries.items():
        row=report['queries'][name];row['after_plan']=plan(db,sql,params);row['after']=timings(db,sql,params)
        if row['before']['result_sha256']!=row['after']['result_sha256']:raise RuntimeError('Index changed query result: '+name)
    db.close();report['indexed_bytes']=work.stat().st_size
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'backup_seconds':backup_seconds,'indexes_seconds':report['index_build_seconds'],'queries':{n:{'before_s':r['before']['median_seconds'],'after_s':r['after']['median_seconds'],'equal':True} for n,r in report['queries'].items()}}))


if __name__=='__main__':main()
