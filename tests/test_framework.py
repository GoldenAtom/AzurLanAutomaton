import threading
import unittest
from unittest.mock import patch
from automation import runtime, web


class FrameworkTests(unittest.TestCase):
    def test_idle_stops_without_android_dependencies(self):
        stop = threading.Event()
        stop.set()
        runtime.run(stop, .001)

    def test_status_reports_stopped_bot(self):
        with patch.object(web, "command", side_effect=["ActiveState=inactive\nSubState=dead\nMainPID=0", "abc123", "stopped", "ActiveState=active", "Already current"]):
            result = web.status()
        self.assertEqual(result["ActiveState"], "inactive")
        self.assertEqual(result["mode"], "idle (no game interaction)")

    def test_failed_system_command_surfaces_error(self):
        import subprocess
        with patch.object(web.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "access denied")):
            with self.assertRaisesRegex(RuntimeError, "access denied"):
                web.command("systemctl")




class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.server = web.ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, headers=None):
        import http.client
        conn = http.client.HTTPConnection(*self.server.server_address)
        conn.request("POST", path, body="{}", headers=headers or {})
        response = conn.getresponse()
        code = response.status
        response.read()
        conn.close()
        return code

    def test_cross_site_command_rejected(self):
        with patch.object(web, "command") as command:
            self.assertEqual(self.request("/api/stop"), 403)
            command.assert_not_called()

    def test_same_origin_start_and_invalid_action(self):
        host = "%s:%s" % self.server.server_address
        headers = {"Origin": "http://" + host, "X-Automaton-Control": "1", "Content-Type": "application/json"}
        with patch.object(web, "command") as command:
            self.assertEqual(self.request("/api/start", headers), 200)
            command.assert_called_once_with("systemctl", "--user", "start", web.UNIT)
            self.assertEqual(self.request("/api/reboot", headers), 404)

    def test_unexpected_host_rejected(self):
        headers = {"Host": "untrusted.example", "Origin": "http://untrusted.example", "X-Automaton-Control": "1", "Content-Type": "application/json"}
        with patch.object(web, "command") as command:
            self.assertEqual(self.request("/api/start", headers), 403)
            command.assert_not_called()

    def test_manual_routes_require_browser_protection(self):
        from automation import manual
        host = '%s:%s' % self.server.server_address
        valid = {'Origin': 'http://' + host, 'X-Automaton-Control': '1', 'Content-Type': 'application/json'}
        with patch.object(manual, 'execute', return_value={'ok': True}) as execute:
            for route in ['screenshot', 'click', 'identify', 'back']:
                for headers in [{}, {**valid, 'Origin': 'http://other.example'}, {**valid, 'X-Automaton-Control': ''}]:
                    self.assertEqual(self.request('/api/manual/' + route, headers), 403)
            execute.assert_not_called()
            self.assertEqual(self.request('/api/manual/screenshot', valid), 200)
            execute.assert_called_once_with('screenshot', {})
