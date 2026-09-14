"""Validated block programs: data only, never eval or generated Python."""
import copy
import json
import math
from pathlib import Path
import re
import secrets
import threading
import time
import config

GUARD=threading.RLock()


def directory():
    path=config.BASE_DIR/"local-programs";path.mkdir(exist_ok=True);return path


def runtime_dir():
    path=config.BASE_DIR/"local-runtime";path.mkdir(exist_ok=True);return path


def slug(name):
    if not isinstance(name,str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}",name):
        raise ValueError("Use a name of 1–48 lowercase letters, digits, hyphens or underscores")
    return name


def atomic(path,value):
    temporary=path.with_name(path.name+"."+secrets.token_hex(4)+".tmp")
    try:
        temporary.write_text(json.dumps(value,allow_nan=False),encoding="utf-8")
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)


def read_status():
    path=runtime_dir()/"status.json"
    try:return json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return {"state":"idle","events":[],"variables":{}}


def number(value,low=0,high=86400):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f"Number must be between {low} and {high}")
    return value


def validate(program):
    if not isinstance(program,dict) or program.get("version")!=1:raise ValueError("Unsupported program version")
    count=0
    def expr(e,depth):
        if depth>16 or not isinstance(e,dict):raise ValueError("Invalid/deep expression")
        op=e.get("op")
        if op=="value":
            value=e.get("value")
            if not isinstance(value,bool):number(value,-1e9,1e9)
        elif op=="variable":slug(e.get("name"))
        elif op=="compare":
            if e.get("test") not in (">",">=","<","<=","==","!="):raise ValueError("Invalid comparison")
            expr(e.get("left"),depth+1);expr(e.get("right"),depth+1)
        elif op=="visible":slug(e.get("button"));number(e.get("threshold"),0,1)
        elif op=="screen":
            from core.screens import Screen
            Screen(e.get("name"))
        elif op=="not":expr(e.get("value"),depth+1)
        else:raise ValueError("Unknown expression: "+str(op))
    def blocks(items,depth=0):
        nonlocal count
        if depth>12 or not isinstance(items,list):raise ValueError("Invalid/deep block sequence")
        for node in items:
            count+=1
            if count>2000 or not isinstance(node,dict):raise ValueError("Program too large or invalid")
            op=node.get("op")
            if op=="wait":number(node.get("seconds"))
            elif op in ("press","wait_button"):
                slug(node.get("button"));number(node.get("threshold"),0,1)
                if op=="wait_button":number(node.get("timeout"),.1,3600);number(node.get("interval"),.2,60)
            elif op=="tap":number(node.get("x"),0,16383);number(node.get("y"),0,16383)
            elif op=="if":expr(node.get("condition"),0);blocks(node.get("then"),depth+1);blocks(node.get("else"),depth+1)
            elif op=="repeat":
                n=number(node.get("count"),0,10000)
                if int(n)!=n:raise ValueError("Repeat count must be an integer")
                blocks(node.get("body"),depth+1)
            elif op=="while":expr(node.get("condition"),0);number(node.get("timeout"),.1,86400);blocks(node.get("body"),depth+1)
            elif op=="call":slug(node.get("program"))
            elif op=="set":slug(node.get("variable"));expr(node.get("value"),0)
            elif op=="read_number":slug(node.get("source"));slug(node.get("variable"))
            elif op=="return":expr(node.get("value"),0)
            elif op in ("log","fail"):
                if not isinstance(node.get("message"),str) or len(node["message"])>500:raise ValueError("Invalid message")
            else:raise ValueError("Unknown block: "+str(op))
    blocks(program.get("steps"))
    return program


def list_programs():return sorted(p.stem for p in directory().glob("*.json"))

def load(name):return json.loads((directory()/(slug(name)+".json")).read_text())


def save(name,program):
    slug(name);validate(program)
    if len(json.dumps(program))>400000:raise ValueError("Program exceeds 400 KB")
    with GUARD:
        path=directory()/(name+".json")
        if path.exists():
            backups=directory()/"history";backups.mkdir(exist_ok=True)
            atomic(backups/(name+"-"+str(time.time_ns())+".json"),json.loads(path.read_text()))
            for old in sorted(backups.glob(name+"-*.json"))[:-10]:old.unlink()
        atomic(path,program)
    return {"message":"Saved "+name,"names":list_programs()}


def snapshot(name):
    result={};visiting=set()
    def visit(current):
        if len(visiting)>16:raise ValueError("Program call depth exceeds 16")
        if current in visiting:raise ValueError("Recursive program calls are not allowed: "+current)
        if current in result:return
        visiting.add(current)
        try:doc=validate(load(current))
        except FileNotFoundError:raise ValueError("Missing called program: "+current)
        def walk(nodes):
            for n in nodes:
                if n["op"]=="call":visit(n["program"])
                for key in ("then","else","body"):
                    if key in n:walk(n[key])
        walk(doc["steps"]);visiting.remove(current);result[current]=doc
        if len(result)>100:raise ValueError("Too many called programs")
    visit(slug(name));return result


def queue(name,dry=False,max_seconds=43200):
    number(max_seconds,1,86400)
    if not isinstance(dry,bool):raise ValueError("dry must be boolean")
    with GUARD:
        path=runtime_dir()/"request.json";status=read_status()
        if path.exists() or (status.get("state") in ("queued","running","stopping")):
            raise ValueError("A program is already running or queued")
        library=snapshot(name)
        request={"id":secrets.token_hex(12),"name":name,"dry":dry,"max_seconds":max_seconds,"library":library,"created":time.time()}
        atomic(runtime_dir()/"status.json",{"state":"queued","name":name,"run_id":request["id"],"dry":dry,"events":[],"variables":{},"updated":time.time()})
        atomic(path,request)
        return {"message":"Queued "+name,"id":request["id"]}


def stop():
    with GUARD:
        (runtime_dir()/"request.json").unlink(missing_ok=True)
        atomic(runtime_dir()/"stop.json",{"time":time.time()})
        status=read_status()
        if status.get("state")=="queued":
            status.update(state="stopped",updated=time.time());atomic(runtime_dir()/"status.json",status)
    return {"message":"Stop requested. An in-flight ADB command may take up to its timeout to finish."}


class Stopped(Exception):pass
class Returned(Exception):
    def __init__(self,value):self.value=value


class Interpreter:
    def __init__(self,library,adapter,cancel=lambda:False,publish=lambda state:None,max_seconds=43200,dry=False):
        self.library=copy.deepcopy(library);self.adapter=adapter;self.cancel=cancel;self.publish=publish
        self.deadline=time.monotonic()+max_seconds;self.deadlines=[];self.steps=0;self.dry=dry
        self.state={"state":"running","variables":{"last_result":True},"events":[],"block":None,"program":None}
        self.last_publish=0
    def report(self,message=None,force=False):
        if message:self.state["events"]=(self.state["events"]+[message])[-50:]
        now=time.monotonic()
        if force or now-self.last_publish>.25:
            self.publish(copy.deepcopy(self.state));self.last_publish=now
    def check(self):
        if self.cancel():raise Stopped()
        if time.monotonic()>min([self.deadline]+self.deadlines):raise RuntimeError("Program time limit reached")
        self.report()
    def wait(self,seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            self.check();time.sleep(min(.1,max(0,end-time.monotonic())))
    def expression(self,node):
        self.check();op=node["op"];v=self.state["variables"]
        if op=="value":return node["value"]
        if op=="variable":
            if node["name"] not in v:raise ValueError("Variable not set: "+node["name"])
            return v[node["name"]]
        if op=="visible":return False if self.dry else self.adapter.visible(node["button"],node["threshold"])
        if op=="screen":return False if self.dry else self.adapter.screen()==node["name"]
        if op=="not":return not self.expression(node["value"])
        a=self.expression(node["left"]);b=self.expression(node["right"])
        return {">":lambda:a>b,">=":lambda:a>=b,"<":lambda:a<b,"<=":lambda:a<=b,"==":lambda:a==b,"!=":lambda:a!=b}[node["test"]]()
    def call(self,name,depth=0):
        if depth>16:raise ValueError("Program call depth exceeded")
        previous=self.state["program"];self.state["program"]=name
        try:self.sequence(self.library[name]["steps"],depth);return self.state["variables"]["last_result"]
        except Returned as result:return result.value
        finally:self.state["program"]=previous
    def sequence(self,nodes,depth=0):
        for node in nodes:
            self.check();self.steps+=1
            if self.steps>200000:raise RuntimeError("Program step budget exceeded")
            self.state["block"]=node.get("id");op=node["op"];v=self.state["variables"]
            self.report(f"{self.state['program']}: {op}",True)
            if op=="wait":self.wait(min(node["seconds"],.01) if self.dry else node["seconds"])
            elif op=="press":v["last_result"]=False if self.dry else self.adapter.press(node["button"],node["threshold"])
            elif op=="tap":
                if not self.dry:self.adapter.tap(node["x"],node["y"])
                v["last_result"]=not self.dry
            elif op=="wait_button":
                end=time.monotonic()+node["timeout"];v["last_result"]=False
                while not self.dry:
                    self.check()
                    if self.adapter.visible(node["button"],node["threshold"]):v["last_result"]=True;break
                    if time.monotonic()>=end:break
                    self.wait(min(node["interval"],max(0,end-time.monotonic())))
            elif op=="if":self.sequence(node["then"] if self.expression(node["condition"]) else node["else"],depth)
            elif op=="repeat":
                for _ in range(int(node["count"])):self.check();self.sequence(node["body"],depth)
            elif op=="while":
                self.deadlines.append(time.monotonic()+node["timeout"])
                try:
                    while self.expression(node["condition"]):self.sequence(node["body"],depth);self.wait(.01 if self.dry else .1)
                finally:self.deadlines.pop()
            elif op=="call":v["last_result"]=self.call(node["program"],depth+1)
            elif op=="set":v[node["variable"]]=self.expression(node["value"])
            elif op=="read_number":v[node["variable"]]=0 if self.dry else self.adapter.read_number(node["source"])
            elif op=="return":raise Returned(self.expression(node["value"]))
            elif op=="log":self.report(node["message"],True)
            elif op=="fail":raise RuntimeError(node["message"])
            self.report(force=True)
