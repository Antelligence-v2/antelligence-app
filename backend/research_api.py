"""Bounded local research jobs with SQLite event checkpoints and no execution tools."""
from __future__ import annotations
import fcntl
import ipaddress
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.research_data import BUNDLE_SHA256, LIMITATIONS, digest, load_bundle, select_tasks
from backend.research_models import LocalModels, MODELS
from backend.swarm_core import PROTOCOLS, estimate_calls, output_policy_catalog, run_task, summarize


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    model_keys: list[Literal['qwen','phi4']] = Field(min_length=1,max_length=2)
    protocols: list[Literal['single','independent_vote','peer_review','signal_board']] = Field(min_length=1,max_length=4)
    datasets: list[Literal['pubmedqa','finqa']] = Field(min_length=1,max_length=2)
    split: Literal['development','evaluation']
    tasks_per_dataset: int = Field(ge=1,le=50)
    temperature: float = Field(ge=0,le=1)
    seed: int = Field(ge=0,le=2147483647)
    max_tokens: int = Field(ge=64,le=512)
    target_accuracy: float = Field(gt=0,le=1)
    max_calls: int = Field(ge=1,le=600)
    max_wall_seconds: int = Field(ge=10,le=3600)
    output_policy: Literal['prompt_only','constrained_short_v1','source_calculation_v1'] = 'prompt_only'

    @model_validator(mode='after')
    def unique_lists(self):
        for field in ('model_keys','protocols','datasets'):
            values=getattr(self,field)
            if len(values) != len(set(values)):
                raise ValueError(f'Duplicate {field}')
        return self


def now():
    return datetime.now(timezone.utc).isoformat()


class ResearchStore:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as con:
            con.execute('CREATE TABLE IF NOT EXISTS research_runs (run_id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    def connect(self):
        return sqlite3.connect(self.path, timeout=10)
    def save(self,body):
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT body FROM research_runs WHERE run_id=?',(body['run_id'],)).fetchone()
            if row and json.loads(row[0]).get('cancel_requested'):
                body['cancel_requested']=True
            text=json.dumps(body,ensure_ascii=False,allow_nan=False)
            con.execute('INSERT INTO research_runs VALUES (?,?) ON CONFLICT(run_id) DO UPDATE SET body=excluded.body',(body['run_id'],text))
    def get(self,run_id):
        with self.connect() as con:
            row=con.execute('SELECT body FROM research_runs WHERE run_id=?',(str(run_id),)).fetchone()
        if not row: raise HTTPException(404,'Research run not found')
        return json.loads(row[0])
    def list(self,limit=50):
        with self.connect() as con:
            rows=con.execute('SELECT body FROM research_runs ORDER BY rowid DESC LIMIT ?',(limit+1,)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def request_cancel(self,run_id):
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT body FROM research_runs WHERE run_id=?',(str(run_id),)).fetchone()
            if not row: raise HTTPException(404,'Research run not found')
            body=json.loads(row[0])
            if body['status']=='running':
                body.update(cancel_requested=True,updated_at=now())
                con.execute('UPDATE research_runs SET body=? WHERE run_id=?',(json.dumps(body,allow_nan=False),str(run_id)))
        return body
    def recover(self):
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            for run_id,text in con.execute('SELECT run_id,body FROM research_runs').fetchall():
                body=json.loads(text)
                if body['status']=='running':
                    body.update(status='interrupted',updated_at=now())
                    body['errors'].append('Backend restarted without an active worker; no automatic resume.')
                    # Pending placeholders remain in all denominators. Never promote partial evidence.
                    body['summary']=summarize(body['cells'],body['request']['target_accuracy'])
                    con.execute('UPDATE research_runs SET body=? WHERE run_id=?',(json.dumps(body,allow_nan=False),run_id))


class ResearchService:
    def __init__(self,path,models_factory=LocalModels):
        self.store=ResearchStore(path)
        self.models_factory=models_factory
        self.lock_path=Path(str(path)+'.research.lock')
        self.thread=None
        self.worker_failure=None

    def acquire(self):
        handle=self.lock_path.open('a+')
        try: fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close(); return None
        return handle

    def recover(self):
        handle=self.acquire()
        if handle:
            try: self.store.recover()
            finally: handle.close()

    def catalog(self):
        self.recover()
        return dict(models=self.models_factory().catalog(),datasets=load_bundle()['datasets'],
                    output_policies=output_policy_catalog(),
                    protocols=[dict(id=p,label=p.replace('_',' ').title(),description={
                        'single':'One blind answer per model (cheaper baseline).',
                        'independent_vote':'Three blind samples per model, strict-majority vote.',
                        'peer_review':'Blind claims, named peer critique, then revisions.',
                        'signal_board':'Typed task-scoped signals with round snapshots and one-round TTL.'}[p],
                        calls_per_model=1 if p=='single' else 3) for p in PROTOCOLS],
                    limits=dict(max_calls=600,max_wall_seconds=3600,max_tasks_per_dataset=50),limitations=LIMITATIONS)

    def start(self,request):
        data=request.model_dump()
        tasks=select_tasks(data['datasets'],data['split'],data['tasks_per_dataset'],data['seed'])
        calls=estimate_calls(len(tasks),len(data['model_keys']),data['protocols'])
        if calls>data['max_calls']: raise HTTPException(422,f'Estimated {calls} calls exceeds explicit budget')
        handle=self.acquire()
        if handle is None: raise HTTPException(409,'Another local research run is active; no queue')
        try:
            self.store.recover()
            models=self.models_factory()
            try: roster=models.pin(data['model_keys'])
            except Exception as exc: raise HTTPException(409,str(exc)) from exc
            cells=[]
            for task in tasks:
                for protocol in data['protocols']:
                    variants=[('single:'+m,[m]) for m in data['model_keys']] if protocol=='single' else [(protocol,data['model_keys'])]
                    for variant,keys in variants:
                        cells.append(dict(cell_id=f'{task["task_id"]}:{variant}',task_id=task['task_id'],dataset=task['dataset'],domain=task['domain'],
                           variant=variant,protocol=protocol,model_keys=keys,output_policy=data['output_policy'],status='error',answer=None,expected_answer=task['expected_answer'],
                           correct=None,instruction_compliant=False,call_count=0,prompt_tokens=0,completion_tokens=0,elapsed_s=0.,messages=[],
                           usage_complete=False,error='Not evaluated (pending or interrupted).'))
            run_id=str(uuid4()); stamp=now()
            body=dict(schema_version='antelligence.swarm-research.v1',run_id=run_id,name=data['name'],created_at=stamp,updated_at=stamp,
                      status='running',request=data,request_hash=digest(data),dataset_manifest={
                          'bundle_sha256':BUNDLE_SHA256,'datasets':[d for d in load_bundle()['datasets'] if d['key'] in data['datasets']]},
                      models=roster,selected_task_ids=[t['task_id'] for t in tasks],total_cells=len(cells),completed_cells=0,
                      estimated_calls=calls,actual_calls=0,cells=cells,summary=summarize(cells,data['target_accuracy']),events=[],errors=[],
                      limitations=LIMITATIONS,metered_api_cost_usd=0,proof_ok=False,cancel_requested=False,
                      source_hashes={p.name:digest(p.read_text()) for p in [Path(__file__),Path(__file__).with_name('swarm_core.py'),Path(__file__).with_name('source_calculation.py'),Path(__file__).with_name('research_models.py'),Path(__file__).with_name('research_data.py')]})
            self.store.save(body)
            self.worker_failure=None
            self.thread=threading.Thread(target=self._run,args=(body,tasks,models,handle),daemon=True,name='antelligence-research')
            self.thread.start()
            return {'run_id':run_id,'status':'running'}
        except Exception:
            handle.close(); raise

    def _run(self,body,tasks,models,handle):
        started=time.monotonic(); data=body['request']; attempted=0; completed=set()
        def stopped():
            return bool(self.store.get(body['run_id']).get('cancel_requested')) or attempted>=data['max_calls'] or time.monotonic()-started>=data['max_wall_seconds']
        def infer(key,messages,**settings):
            nonlocal attempted
            if stopped(): raise RuntimeError('Research execution budget/cancel boundary reached')
            attempted+=1
            # Reserve calls durably before network work; lost responses remain unknown after restart.
            body['actual_calls']=attempted; body['updated_at']=now(); self.store.save(body)
            if hasattr(models,'timeout'):
                models.timeout=max(.1,min(120.,data['max_wall_seconds']-(time.monotonic()-started)))
            return models.infer(key,messages,**settings)
        def emit(event):
            body['events'].append(event)
            cell_id=event['message_id'].rsplit(':message-',1)[0]
            for cell in body['cells']:
                if cell['cell_id']==cell_id:
                    cell['messages'].append(event)
                    cell['call_count']=len(cell['messages'])
                    for field in ('prompt_tokens','completion_tokens','elapsed_s'):
                        cell[field]=sum(e.get(field) or 0 for e in cell['messages'])
                    break
            body['summary']=summarize(body['cells'],data['target_accuracy'])
            body['updated_at']=now();self.store.save(body)
        try:
            for task in tasks:
                for protocol in data['protocols']:
                    if stopped(): break
                    results=run_task(task,data['model_keys'],protocol,
                              {k:data[k] for k in ('temperature','seed','max_tokens')},infer,emit,stopped,
                              output_policy=data['output_policy'])
                    for cell in results:
                        for i,old in enumerate(body['cells']):
                            if old['cell_id']==cell['cell_id']:
                                body['cells'][i]=cell; completed.add(cell['cell_id']);break
                    body['completed_cells']=len(completed)
                    body['summary']=summarize(body['cells'],data['target_accuracy'])
                    body['updated_at']=now();self.store.save(body)
                if stopped(): break
            body['cancel_requested']=bool(self.store.get(body['run_id']).get('cancel_requested'))
            interrupted=body['cancel_requested'] or (len(completed)<body['total_cells'])
            if interrupted:
                body['status']='interrupted'
                body['errors'].append('Cancelled or bounded call/wall budget reached; unfinished tasks remain unknown.')
            elif any(c['status']=='error' for c in body['cells']):
                body['status']='partial' if any(c['status']!='error' for c in body['cells']) else 'failed'
            else: body['status']='completed'
        except Exception as exc:
            body['status']='partial' if completed else 'failed'
            body['errors'].append(f'{type(exc).__name__}: {exc}')
        finally:
            try:
                body['updated_at']=now();body['summary']=summarize(body['cells'],data['target_accuracy']);self.store.save(body)
            except Exception as exc:
                # Never claim a durable terminal state if the checkpoint itself failed.
                self.worker_failure=f'{type(exc).__name__}: {exc}'
            handle.close()


def _private(request: Request):
    host=request.client.host if request.client else ''
    try: loopback=ipaddress.ip_address(host).is_loopback
    except ValueError: loopback=host=='testclient'
    if not loopback: raise HTTPException(403,'Research API is local-only')
    origin=request.headers.get('origin')
    if origin and urlparse(origin).hostname not in {'localhost','127.0.0.1','::1'}:
        raise HTTPException(403,'Research API rejects non-local origins')


def make_router(service):
    router=APIRouter(prefix='/research',dependencies=[Depends(_private)])
    @router.get('/catalog')
    def catalog(): return service.catalog()
    @router.post('/runs',status_code=202)
    def start(request: ResearchRequest): return service.start(request)
    @router.get('/runs')
    def library(limit: Annotated[int,Query(ge=1,le=50)]=50):
        service.recover();rows=service.store.list(limit)
        return {'items':[{**{k:r[k] for k in ('run_id','name','created_at','status','completed_cells','total_cells')},
                          'output_policy':r.get('request',{}).get('output_policy','prompt_only')}
                         for r in rows[:limit]],'has_more':len(rows)>limit}
    @router.get('/runs/{run_id}')
    def report(run_id: UUID):
        service.recover();return service.store.get(run_id)
    @router.post('/runs/{run_id}/cancel')
    def cancel(run_id: UUID):
        service.recover();return service.store.request_cancel(run_id)
    return router
