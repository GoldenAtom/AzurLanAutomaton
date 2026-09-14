import subprocess
import unittest
from unittest.mock import patch
import numpy as np
from core import adb, vision
from automation import manual


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(12)
        self.screen = self.rng.integers(0, 255, (100, 160, 3), dtype=np.uint8)
        self.template = self.screen[60:80, 110:140].copy()

    def test_roi_coordinates_are_full_frame_centers(self):
        match = vision.best_template(self.screen, self.template, .95, (90, 40, 160, 100))
        self.assertTrue(match.passed)
        self.assertEqual((match.x, match.y, match.width, match.height), (125, 70, 30, 20))

    def test_failed_match_still_has_diagnostics(self):
        other = self.rng.integers(0, 255, self.template.shape, dtype=np.uint8)
        match = vision.best_template(self.screen, other, .99)
        self.assertFalse(match.passed)
        self.assertIsNone(vision.find_template(self.screen, other, .99))
        self.assertTrue(np.isfinite(match.score))

    def test_invalid_region_and_blank_template_fail(self):
        with self.assertRaises(ValueError):
            vision.best_template(self.screen, self.template, region=(-1, 0, 100, 100))
        with self.assertRaises(ValueError):
            vision.best_template(self.screen, np.zeros_like(self.template))
        with self.assertRaises(ValueError):
            vision.best_template(self.screen, np.zeros((20, 30, 4), dtype=np.uint8))

    def test_alpha_template(self):
        alpha = np.full(self.template.shape[:2], 255, dtype=np.uint8)
        alpha[:3] = 0
        rgba = np.dstack((self.template, alpha))
        match = vision.best_template(self.screen, rgba, .99)
        self.assertTrue(match.passed)
        self.assertEqual((match.x, match.y), (125, 70))


class ManualTests(unittest.TestCase):
    def test_click_uses_one_screenshot_and_exact_match(self):
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        match = vision.Match(.98, 60, 40, 12, 8, .93)
        with patch.object(manual.utility, 'connectADB', return_value='device'), patch.object(manual.utility, 'getScreenshot', return_value=image) as capture, patch.object(manual.utility, 'inspectButton', return_value=match) as detect, patch.object(manual.utility, 'tap') as tap:
            result = manual.execute('click', {'button': 'redo_sortie'})
            capture.assert_called_once()
            self.assertIs(detect.call_args.args[1], image)
            tap.assert_called_once_with(60, 40)
            self.assertTrue(result['clicked'])

    def test_below_threshold_never_taps(self):
        with patch.object(manual.utility, 'connectADB'), patch.object(manual.utility, 'getScreenshot', return_value=np.zeros((80,100,3),dtype=np.uint8)), patch.object(manual.utility, 'inspectButton', return_value=vision.Match(.3, 60, 40, 12, 8)), patch.object(manual.utility, 'tap') as tap:
            result = manual.execute('click', {})
            self.assertFalse(result['clicked'])
            tap.assert_not_called()

    def test_invalid_threshold_rejected_before_adb(self):
        with patch.object(manual.utility, 'connectADB') as connect:
            for bad in [float('nan'), -1, 2, True, '0.9']:
                with self.assertRaises(ValueError):
                    manual.execute('click', {'threshold': bad})
            connect.assert_not_called()

    def test_overlapping_manual_action_rejected(self):
        with manual.LOCK:
            with self.assertRaisesRegex(RuntimeError, 'Another manual'):
                manual.execute('screenshot', {})


class AdbTests(unittest.TestCase):
    def test_waydroid_ip_discovery(self):
        with patch.object(adb.config, 'DEVICE', ''), patch.object(adb.shutil, 'which', return_value='/usr/bin/waydroid'), patch.object(adb.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'IP address: 192.168.240.42\n', '')):
            self.assertEqual(adb.discover_device(), '192.168.240.42:5555')

    def test_ambiguous_devices_fail(self):
        with patch.object(adb.config, 'DEVICE', ''), patch.object(adb.shutil, 'which', return_value=None), patch.object(adb, '_host', return_value=b'List of devices attached\na device\nb device\n'):
            with self.assertRaises(RuntimeError):
                adb.discover_device()

    def test_tap_is_not_retried(self):
        with patch.object(adb, '_device', 'device'), patch.object(adb, '_host', side_effect=RuntimeError('Lost reply')) as host:
            with self.assertRaises(RuntimeError):
                adb.tap(10, 20)
            host.assert_called_once()

    def test_stale_device_reconnects(self):
        with patch.object(adb, '_device', 'stale'), patch.object(adb, 'run_text', side_effect=RuntimeError('offline')), patch.object(adb, 'connect', return_value=True) as connect:
            self.assertTrue(adb.is_alive())
            connect.assert_called_once()

class CompatibilityTests(unittest.TestCase):
    def test_missing_template_stays_false_for_existing_exists_api(self):
        from core import buttons
        with patch.object(buttons, 'template_files', return_value=[]):
            self.assertFalse(buttons.button_exists('confirm', np.zeros((10,10,3), dtype=np.uint8)))
