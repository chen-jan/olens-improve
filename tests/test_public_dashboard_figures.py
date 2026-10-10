import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_public_dashboard as public


class PublicFigureTests(unittest.TestCase):
    def test_reviewed_figures_require_exact_source_and_file_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);files=[]
            for name in ('development-scaling-cell.png','development-scaling-cell.pdf',
                         'development-scaling-item.png','development-scaling-item.pdf'):
                (directory/name).write_bytes(name.encode())
                files.append({'path':name,'sha256':hashlib.sha256(name.encode()).hexdigest()})
            receipt={'reviewed_by':'root','source':{'sha256':'source'},'files':files}
            (directory/'figure-data.json').write_text(json.dumps(receipt))
            self.assertEqual(len(public.development_figure_files(directory,'source')),4)
            with self.assertRaisesRegex(ValueError,'bind'):public.development_figure_files(directory,'foreign')
            (directory/files[0]['path']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'bytes'):public.development_figure_files(directory,'source')

    def test_quote_sanitization_change_is_detectable_not_silent(self):
        safe={'text':'I would join, but cannot physically attend. 2+2=4.'}
        self.assertEqual(public.public_data(safe),safe)
        self.assertNotEqual(public.public_data({'text':'The job 12345 failed.'}),{'text':'The job 12345 failed.'})


if __name__=='__main__':unittest.main()
