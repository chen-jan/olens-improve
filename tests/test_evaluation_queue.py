"""An operational pause must preserve the current result and prevent new calls."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from olens_improve.evaluation import ConditionBoundaryStop, _main


class ConditionQueueTests(unittest.TestCase):
    def test_signal_only_sets_a_boundary_request(self):
        stop = ConditionBoundaryStop()
        self.assertFalse(stop.requested())
        stop.request()
        self.assertTrue(stop.requested())

    def test_file_request_after_first_condition_prevents_second_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = root / 'queue.json'
            queue.write_text(json.dumps([{'method':'first','n':1},{'method':'second','n':2}]))
            stop_file = root / 'stop'
            completed = []

            def dispatch(*args, **kwargs):
                completed.append(kwargs['method'])
                stop_file.touch()
                return {'condition':{'method':kwargs['method']},'budget':{}}

            argv = ['evaluation','--selections',str(root/'unused.jsonl'),'--output',str(root/'out'),
                    '--method','first','--run-id','offline','--family','multihop_mt',
                    '--condition-list',str(queue),'--stop-file',str(stop_file)]
            output = io.StringIO()
            with patch('sys.argv',argv), patch('olens_improve.evaluation.signal.signal'), \
                    patch('olens_improve.evaluation.evaluate_condition',side_effect=dispatch) as call, \
                    contextlib.redirect_stdout(output):
                _main()
            self.assertEqual(completed,['first'])
            self.assertEqual(call.call_count,1)
            messages=[json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(messages[0]['condition']['method'],'first')
            self.assertEqual(messages[1]['status'],'condition_queue_stopped_at_boundary')
            self.assertEqual(messages[1]['next_condition']['method'],'second')


if __name__ == '__main__':
    unittest.main()
