import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from core import numbers


def tsv(text, confidence):
    return ("conf\ttext\n"+str(confidence)+"\t"+text+"\n").encode()


class NumberReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        directory=self.root/"numbers"/"oil"
        directory.mkdir(parents=True)
        (directory/"oil.json").write_text(json.dumps({"frame_size":[80,40],"region":[10,5,70,35]}))
        self.frame=np.full((40,80,3),255,dtype=np.uint8)

    def tearDown(self):
        self.temp.cleanup()

    def read(self, results):
        completed=[subprocess.CompletedProcess([],0,tsv(text,confidence),b"") for text,confidence in results]
        with patch.object(numbers.config,"LOCAL_TEMPLATE_DIR",self.root), patch.object(numbers.adb,"screenshot",return_value=self.frame), patch.object(numbers.shutil,"which",return_value="tesseract"), patch.object(numbers.subprocess,"run",side_effect=completed):
            return numbers.read_number("oil")

    def test_agreement_accepts_one_strong_mode(self):
        result=self.read([("4,000",93.1),("4000",0)])
        self.assertEqual(result["value"],4000)
        self.assertEqual(result["confidence"],93.1)

    def test_disagreement_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"modes disagree"):
            self.read([("4521",94),("4321",91)])

    def test_two_low_confidence_modes_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"low confidence"):
            self.read([("4000",12),("4000",8)])

    def test_resolution_change_is_rejected_before_ocr(self):
        self.frame=np.full((30,80,3),255,dtype=np.uint8)
        with patch.object(numbers.config,"LOCAL_TEMPLATE_DIR",self.root), patch.object(numbers.adb,"screenshot",return_value=self.frame), patch.object(numbers.subprocess,"run") as run:
            with self.assertRaisesRegex(ValueError,"resolution differs"):
                numbers.read_number("oil")
            run.assert_not_called()
