"""Program execution belongs to the bot service, not browser request threads."""
import json
import logging
import time
from automation import programs
from core.action_lock import android_owner

class Android:
    def press(self,name,threshold):
        import utility
        utility.connectADB();frame=utility.getScreenshot()
        return utility.click(name,frame,threshold)
    def visible(self,name,threshold):
        import utility
        try:
            utility.connectADB();return utility.exists(name,utility.getScreenshot(),threshold)
        except (OSError,RuntimeError) as exc:
            logging.getLogger("program").warning("Button read unavailable: %s",exc)
            return False
    def tap(self,x,y):
        import utility
        utility.connectADB();frame=utility.getScreenshot()
        if not (0<=x<frame.shape[1] and 0<=y<frame.shape[0]):raise ValueError("Tap coordinates outside framebuffer")
        utility.tap(x,y)
    def screen(self):
        import utility
        utility.connectADB();return utility.identifyScreen().value
    def read_number(self,name):
        import utility
        utility.connectADB();return utility.readNumber(name)["value"]


def serve(stop):
    root=programs.runtime_dir();log=logging.getLogger("program")
    previous=programs.read_status()
    if previous.get("state") in ("running","stopping"):
        previous.update(state="interrupted",error="Bot service restarted; run was not resumed",updated=time.time())
        programs.atomic(root/"status.json",previous)
    while not stop.wait(.2):
        request_path=root/"request.json"
        try:request=json.loads(request_path.read_text())
        except (FileNotFoundError,json.JSONDecodeError):continue
        request_path.unlink(missing_ok=True)
        state={"state":"failed","events":[],"variables":{}}
        def publish(value):
            value.update(run_id=request["id"],name=request["name"],dry=request["dry"],updated=time.time())
            programs.atomic(root/"status.json",value)
        def cancelled():
            if stop.is_set():return True
            try:return json.loads((root/"stop.json").read_text())["time"]>=request["created"]
            except (FileNotFoundError,json.JSONDecodeError):return False
        try:
            if time.time()-request["created"]>60:raise ValueError("Queued run expired; start it again")
            for document in request["library"].values():programs.validate(document)
            with android_owner():
                engine=programs.Interpreter(request["library"],Android(),cancelled,publish,request["max_seconds"],request["dry"])
                state=engine.state;publish(state.copy())
                result=engine.call(request["name"])
                state.update(state="completed",result=result)
        except programs.Stopped:state.update(state="stopped")
        except Exception as exc:
            state.update(state="failed",error=str(exc));log.exception("Program failed")
        finally:
            publish(state);log.info("Run %s: %s",request["name"],state["state"])
