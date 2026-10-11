import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_expansion_reconstruction_v3 import validate_replay_source_map


POLICY='durable_cumulative_used_source_map_v2; pinned before each dependent journal commit'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path, expected):
    if digest(path)!=expected:raise ValueError('Changed pinned input')


class ResumeMapIntakeTests(unittest.TestCase):
    def fixture(self,directory):
        spec={'resume_pin_policy':POLICY,'source_sha256':{'original_source':'original_sha'}}
        (directory/'spec.json').write_text(json.dumps(spec))
        data={'spec_sha256':digest(directory/'spec.json'),'source_sha256':spec['source_sha256']|{'prior_used_vector':'vector_sha'}}
        (directory/'source-pins.json').write_text(json.dumps(data))
        terminal={'source_map_sha256':digest(directory/'source-pins.json'),'source_sha256':data['source_sha256'],'resumed_existing_cells':2,'completed_cells':6}
        return spec,terminal

    def test_retains_preinterruption_source_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);spec,status=self.fixture(folder)
            self.assertEqual(validate_replay_source_map(folder,spec,status,pin)['resumed_existing_cells'],2)

    def test_missing_or_byte_altered_map_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);spec,status=self.fixture(folder);path=folder/'source-pins.json'
            path.write_text(path.read_text()+' ')
            with self.assertRaises(ValueError):validate_replay_source_map(folder,spec,status,pin)
            path.unlink()
            with self.assertRaises(FileNotFoundError):validate_replay_source_map(folder,spec,status,pin)

    def test_valid_checksum_cannot_hide_wrong_spec_or_lost_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);spec,status=self.fixture(folder);path=folder/'source-pins.json'
            data=json.loads(path.read_text());data['spec_sha256']='wrong_spec';path.write_text(json.dumps(data));status['source_map_sha256']=digest(path)
            with self.assertRaises(ValueError):validate_replay_source_map(folder,spec,status,pin)
            data['spec_sha256']=digest(folder/'spec.json');data['source_sha256']={};path.write_text(json.dumps(data));status['source_map_sha256']=digest(path)
            with self.assertRaises(ValueError):validate_replay_source_map(folder,spec,status,pin)

    def test_actual_completed_interrupted_fixture_receipt(self):
        folder=Path('${OLENS_DATA_ROOT}/expansion-v1/reconstruction/replay-resume-fixture-v2')
        if not folder.exists():self.skipTest('Real fixture is cluster-local')
        spec=json.loads((folder/'spec.json').read_text());status=json.loads((folder/'status.json').read_text())
        result=validate_replay_source_map(folder,spec,status,pin)
        self.assertEqual(result['resumed_existing_cells'],2)
        self.assertEqual(status['completed_cells'],6)


if __name__=='__main__':unittest.main()
