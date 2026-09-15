import copy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation import programs
from core.action_lock import android_owner


def doc(steps):return {'version':1,'steps':steps}
def literal(value):return {'op':'value','value':value}
def variable(name):return {'op':'variable','name':name}

class InterpreterTests(unittest.TestCase):
    def execute(self,steps,adapter=None,**kwargs):
        document=programs.validate(doc(steps));engine=programs.Interpreter({'main':document},adapter or Mock(),**kwargs);engine.call('main');return engine
    def test_press_false_takes_else_branch(self):
        adapter=Mock();adapter.press.return_value=False
        engine=self.execute([{'op':'press','button':'battle','threshold':.93},{'op':'if','condition':variable('last_result'),'then':[{'op':'fail','message':'wrong branch'}],'else':[{'op':'set','variable':'branch','value':literal(2)}]}],adapter)
        self.assertEqual(engine.state['variables']['branch'],2)
    def test_oil_supervisor_calls_child_four_times(self):
        child=doc([{'op':'press','button':'farm_start','threshold':.9},{'op':'return','value':variable('last_result')}])
        main=doc([{'op':'read_number','source':'oil','variable':'oil'},{'op':'if','condition':{'op':'compare','test':'>','left':variable('oil'),'right':literal(3000)},'then':[{'op':'repeat','count':4,'body':[{'op':'call','program':'farm_4_8'}]}],'else':[]}])
        adapter=Mock();adapter.read_number.return_value=4000;adapter.press.return_value=True
        engine=programs.Interpreter({'main':main,'farm_4_8':child},adapter);engine.call('main')
        self.assertEqual(adapter.press.call_count,4)
    def test_call_stores_returned_value_like_a_function(self):
        child=doc([{'op':'return','value':literal(42)}])
        main=doc([{'op':'call','program':'child','result':'answer'}])
        engine=programs.Interpreter({'main':main,'child':child},Mock());engine.call('main')
        self.assertEqual(engine.state['variables']['answer'],42)
        self.assertEqual(engine.state['variables']['last_result'],42)
    def test_wait_timeout_returns_false(self):
        adapter=Mock();adapter.visible.return_value=False
        engine=self.execute([{'op':'wait_button','button':'battle','threshold':.9,'timeout':.1,'interval':.2}],adapter)
        self.assertFalse(engine.state['variables']['last_result'])
    def test_wait_success_returns_true(self):
        adapter=Mock();adapter.visible.return_value=True
        engine=self.execute([{'op':'wait_button','button':'battle','threshold':.9,'timeout':1,'interval':.2}],adapter)
        self.assertTrue(engine.state['variables']['last_result'])
    def test_target_screen_wait_uses_qualified_dropdown_value(self):
        adapter=Mock();adapter.screen_visible.return_value=True
        engine=self.execute([{'op':'wait_screen','screen':'battle/campaign_selector','threshold':.72,'timeout':1,'interval':.2}],adapter)
        self.assertTrue(engine.state['variables']['last_result'])
        adapter.screen_visible.assert_called_once_with('battle/campaign_selector',.72)
    def test_cancel_interrupts_wait(self):
        started=time.monotonic()
        with self.assertRaises(programs.Stopped):self.execute([{'op':'wait','seconds':100}],cancel=lambda:time.monotonic()-started>.05)
        self.assertLess(time.monotonic()-started,.5)
    def test_dry_run_never_uses_android(self):
        adapter=Mock()
        engine=self.execute([{'op':'press','button':'battle','threshold':.9},{'op':'read_number','source':'oil','variable':'oil'},{'op':'tap','x':10,'y':10},{'op':'wait','seconds':30}],adapter,dry=True)
        self.assertEqual(adapter.mock_calls,[]);self.assertEqual(engine.state['variables']['oil'],0)
    def test_while_has_deadline_even_with_long_wait_body(self):
        with self.assertRaisesRegex(RuntimeError,'time limit'):
            self.execute([{'op':'while','condition':literal(True),'timeout':.1,'body':[{'op':'wait','seconds':100}]}])
    def test_library_snapshot_is_immutable(self):
        library={'main':doc([{'op':'set','variable':'x','value':literal(1)}])}
        engine=programs.Interpreter(library,Mock());library['main']['steps'][0]['value']['value']=5;engine.call('main')
        self.assertEqual(engine.state['variables']['x'],1)
    def test_unknown_operations_and_invalid_limits_rejected(self):
        for node in [{'op':'exec','code':'print(1)'},{'op':'wait','seconds':float('nan')},{'op':'repeat','count':1.5,'body':[]},{'op':'call','program':'../../bad'},{'op':'press','button':'battle/menu/start','threshold':.9}]:
            with self.assertRaises(ValueError):programs.validate(doc([node]))
    def test_unreadable_number_ends_run(self):
        adapter=Mock();adapter.read_number.side_effect=ValueError('unreadable')
        with self.assertRaisesRegex(ValueError,'unreadable'):self.execute([{'op':'read_number','source':'oil','variable':'oil'},{'op':'press','button':'battle','threshold':.9}],adapter)
        adapter.press.assert_not_called()

class ProgramStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.p=patch.object(programs.config,'BASE_DIR',Path(self.temp.name));self.p.start()
    def tearDown(self):self.p.stop();self.temp.cleanup()
    def test_save_load_and_history(self):
        programs.save('one',doc([]));programs.save('one',doc([{'op':'wait','seconds':1}]))
        self.assertEqual(programs.load('one')['steps'][0]['seconds'],1)
        self.assertEqual(len(list((programs.directory()/'history').glob('*.json'))),1)
    def test_favorite_catalog_and_reversible_delete(self):
        programs.save('one',doc([]));programs.save('two',doc([]))
        programs.favorite('two',True)
        self.assertEqual([(item['name'],item['favorite']) for item in programs.catalog()],[('two',True),('one',False)])
        result=programs.delete('two')
        self.assertIn('recovery copy',result['message'])
        self.assertEqual(programs.list_programs(),['one'])
        self.assertEqual(len(list((programs.directory()/'deleted').glob('two-*.json'))),1)
    def test_recursive_and_missing_calls_are_rejected(self):
        programs.save('one',doc([{'op':'call','program':'two'}]))
        with self.assertRaisesRegex(ValueError,'Missing'):programs.snapshot('one')
        programs.save('two',doc([{'op':'call','program':'one'}]))
        with self.assertRaisesRegex(ValueError,'Recursive'):programs.snapshot('one')
    def test_queue_captures_saved_definition(self):
        programs.save('one',doc([]));programs.queue('one',True)
        with self.assertRaises(ValueError):programs.queue('one',True)
        programs.stop();self.assertFalse((programs.runtime_dir()/'request.json').exists())
    def test_android_owner_excludes_other_actions(self):
        with android_owner():
            with self.assertRaisesRegex(RuntimeError,'owned'):
                with android_owner():pass
