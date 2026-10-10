"""A prepared VAL spec cannot accidentally become a paid worker launch."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('validation_launch_test',Path('infra/launch_validation_judges.py'))
launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)


class ValidationLaunchTests(unittest.TestCase):
    def test_draft_or_missing_explicit_paid_authority_never_spawns(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'spec.json'
            for status,flag in [('draft_not_authorization',['--allow-paid']),('root_reviewed_ready',[])]:
                path.write_text(json.dumps({'status':status}))
                argv=['launch','--spec',str(path),'--family','hallucination']+flag
                with patch('sys.argv',argv),patch.object(launch,'preflight'), \
                     patch.object(launch.subprocess,'Popen') as worker:
                    with self.assertRaisesRegex(SystemExit,'explicitly authorize paid'):launch.main()
                    worker.assert_not_called()

    def test_validate_only_never_spawns_even_when_paid_flag_present(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'spec.json';path.write_text(json.dumps({'status':'root_reviewed_ready'}))
            argv=['launch','--spec',str(path),'--family','hallucination','--allow-paid','--validate-only']
            with patch('sys.argv',argv),patch.object(launch,'preflight'), \
                 patch.object(launch.subprocess,'Popen') as worker,patch('builtins.print'):
                launch.main();worker.assert_not_called()


if __name__=='__main__':unittest.main()
