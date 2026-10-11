import json
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import watch_expansion_api_health as w


class WorkerHealth(unittest.TestCase):
    def test_stale_running_state_cannot_mask_dead_process(self):
        with tempfile.TemporaryDirectory() as d:
            s={'pid':123,'family':'chain_intermediates','inventory_sha256':'seal','running':True,
               'last_successful_check_utc':100,'completed':{}}
            out=w.worker_health(s,1000,Path(d));self.assertEqual(out['status'],'dead_process')
            self.assertTrue(out['recovery_required'])

    def test_busy_live_worker_is_flagged_without_automatic_restart(self):
        with tempfile.TemporaryDirectory() as d:
            proc=Path(d)/'123';proc.mkdir();(proc/'cmdline').write_bytes(b'python\0scripts/expanded_judges.py\0--family\0chain_intermediates\0seal\0')
            (proc/'status').write_text('VmRSS: 1024 kB\n')
            s={'pid':123,'family':'chain_intermediates','inventory_sha256':'seal','running':True,
               'last_successful_check_utc':100,'completed':{}}
            out=w.worker_health(s,1000,Path(d));self.assertEqual(out['status'],'stale_alive')
            self.assertFalse(out['recovery_required']);self.assertEqual(out['resident_bytes'],1048576)
            s['family']='hallucination';out=w.worker_health(s,1000,Path(d));self.assertEqual(out['status'],'pid_identity_mismatch')

    def test_terminal_exit_is_normal(self):
        with tempfile.TemporaryDirectory() as d:
            s={'pid':123,'family':'chain_intermediates','inventory_sha256':'seal','running':False,'completed':dict.fromkeys(range(70))}
            self.assertEqual(w.worker_health(s,1000,Path(d))['status'],'terminal')


if __name__=='__main__':unittest.main()
