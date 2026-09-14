import base64
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from automation import template_editor as editor
from core import assets, buttons, screens


class TemplateEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.frame=np.random.default_rng(61).integers(0,255,(80,120,3),dtype=np.uint8)
        self.patches=[patch.object(editor.config,'BASE_DIR',self.root),patch.object(editor.config,'LOCAL_TEMPLATE_DIR',self.root/'local-templates'),patch.dict(editor.FRAMES,{'token':(time.monotonic(),self.frame)},clear=True)]
        for item in self.patches:item.start()

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()

    def save(self,**changes):
        payload={'token':'token','region':[17,23,51,60],'kind':'buttons','target':'battle','name':'start','variant':'test'}
        payload.update(changes)
        return editor.execute('save',payload)

    def test_saved_crop_preserves_exact_pixels_and_is_discovered(self):
        result=self.save()
        saved=cv2.imread(str(self.root/result['path']))
        np.testing.assert_array_equal(saved,self.frame[23:60,17:51])
        self.assertEqual(buttons.template_files('battle/start'),[self.root/result['path']])
        decoded=cv2.imdecode(np.frombuffer(base64.b64decode(result['image'].split(',')[1]),np.uint8),cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(decoded,saved)

    def test_existing_variant_is_preserved(self):
        result=self.save();path=self.root/result['path'];before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'already exists'):self.save()
        self.assertEqual(before,path.read_bytes())

    def test_invalid_names_bounds_and_expired_capture(self):
        for change in [{'variant':'../escape'},{'target':'../battle'},{'name':'../battle'},{'region':[-1,0,20,20]},{'region':[0,0,121,30]},{'region':[0,0,1,1]},{'region':[True,0,20,20]},{'token':'missing'}]:
            with self.assertRaises(ValueError):self.save(**change)
        editor.FRAMES['token']=(time.monotonic()-901,self.frame)
        with self.assertRaisesRegex(ValueError,'expired'):self.save()

    def test_screen_crop_is_compared_at_original_position(self):
        result=self.save(kind='screens',name='campaign_selector')
        match=screens.inspect_reference('battle/campaign_selector',self.frame,threshold=.99)
        self.assertTrue(match['passed']);self.assertEqual(match['score'],1)
        wrong_size=np.zeros((100,120,3),np.uint8)
        with self.assertRaises(FileNotFoundError):screens.inspect_reference('battle/campaign_selector',wrong_size)

    def test_target_catalog_groups_template_types(self):
        self.save(kind='screens',name='campaign_selector')
        self.save(kind='buttons',name='start',variant='second')
        self.save(kind='numbers',name='oil')
        self.assertEqual(assets.target_catalog(),{'battle':{'buttons':['start'],'screens':['campaign_selector'],'numbers':['oil']}})

    def test_capture_is_lossless_and_does_not_tap(self):
        with patch.object(editor.utility,'connectADB',return_value='device'),patch.object(editor.utility,'getScreenshot',return_value=self.frame),patch.object(editor.utility,'tap') as tap:
            result=editor.execute('capture',{})
        tap.assert_not_called()
        self.assertEqual((result['width'],result['height']),(120,80))
        self.assertIn(result['token'],editor.FRAMES)
