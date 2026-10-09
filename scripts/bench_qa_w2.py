#!/usr/bin/env python3
"""Run the preregistered research-QA benchmark with append-only evidence."""
from __future__ import annotations
import argparse, asyncio, csv, hashlib, json, os, pathlib, sys, time
from datetime import datetime, timezone
from typing import Any
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.research_models import LocalModels, MODELS
from backend.research_data import select_tasks
from backend.swarm_core import run_task, summarize
from antelligence.providers import Budgeted, OpenAICompatProvider
OUT=ROOT/'docs/research/slm-vs-frontier-20261008'
LEDGER=ROOT/'ledger/goal-2026-10-08-usage.jsonl'
ARMS=('single','independent_vote','signal_board','evidence_exchange','evidence_isolated','solo_refine')
CALLS={'single':1,'independent_vote':3,'signal_board':9,'evidence_exchange':6,'evidence_isolated':6,'solo_refine':6}

def utc(): return datetime.now(timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def append(path,row):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a',encoding='utf8') as f: f.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n')
def load_tasks():
 import json as j
 d=j.loads((ROOT/'backend/research_fixtures/tasks.json').read_text())
 return d['tasks']
def infer_factory(provider, model, ledger, tier):
 def infer(model_key,messages,**kw):
  started=time.monotonic(); requested=model_key
  try:
   from antelligence.providers.base import ChatRequest
   req=ChatRequest(model=model,messages=tuple(messages),max_tokens=kw['max_tokens'],temperature=kw['temperature'],seed=kw['seed'],response_format=kw.get('response_format'))
   res=asyncio.run(provider.complete(req))
   row={'timestamp_utc':utc(),'tier':tier,'provider':provider.describe().get('provider'),'model_id_requested':requested,'model_id_served':res.model,'prompt_tokens':res.prompt_tokens,'completion_tokens':res.completion_tokens,'latency_s':res.elapsed_s,'cost_usd':(res.extra or {}).get('cost_usd','subscription' if tier=='frontier' else 0),'request_hash':res.request_hash}
   append(ledger,row)
   return {'content':res.content,'response_id':res.response_id,'requested_model':requested,'served_model':res.model,'prompt_tokens':res.prompt_tokens,'completion_tokens':res.completion_tokens,'elapsed_s':res.elapsed_s,'finish_reason':res.finish_reason}
  except Exception as e:
   append(ledger,{'timestamp_utc':utc(),'tier':tier,'provider':provider.describe().get('provider'),'model_id_requested':requested,'model_id_served':None,'prompt_tokens':None,'completion_tokens':None,'latency_s':time.monotonic()-started,'cost_usd':'subscription' if tier=='frontier' else 0,'error':f'{type(e).__name__}: {e}'})
   raise
 return infer

def make_provider(spec):
 return OpenAICompatProvider(spec['base_url'],api_key=spec.get('api_key'),allowed_models=[spec['model']],require_model_match=True,require_stop=True,extra_body=spec.get('extra_body'))
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--model',required=True); ap.add_argument('--tier',choices=['local','frontier'],required=True); ap.add_argument('--provider',required=True); ap.add_argument('--base-url',required=True); ap.add_argument('--api-key'); ap.add_argument('--served-model'); ap.add_argument('--limit',type=int,default=0); ap.add_argument('--seed',type=int,default=0); ap.add_argument('--smoke',action='store_true'); ap.add_argument('--protocols',default=','.join(ARMS)); args=ap.parse_args()
 selected=tuple(x for x in args.protocols.split(',') if x)
 if any(x not in ARMS for x in selected): raise SystemExit('unknown protocol')
 OUT.mkdir(parents=True,exist_ok=True); tasks=[t for t in load_tasks() if t['split']==('development' if args.smoke else 'evaluation')];
 if args.limit: tasks=tasks[:args.limit]
 model=args.served_model or args.model; inner=OpenAICompatProvider(args.base_url,api_key=args.api_key,allowed_models=[model],require_model_match=True,require_stop=True)
 budget=Budgeted(inner); infer=infer_factory(budget,model,LEDGER,args.tier)
 if args.tier=='local':
  catalog=LocalModels().catalog(); print(json.dumps({'local_catalog':catalog},sort_keys=True))
 raw=OUT/f'raw-{args.tier}-{args.model}-seed{args.seed}.jsonl'; cells=[]
 for i,t in enumerate(tasks,1):
  for arm in selected:
   events=[]
   def emit(e): events.append(e)
   try: cell=run_task(t,[model],arm,{'temperature':0.0,'seed':args.seed,'max_tokens':512},infer,emit,lambda:False)[0]
   except Exception as e: cell={'task_id':t['task_id'],'domain':t['domain'],'variant':f'{arm}:{model}','protocol':arm,'model_keys':[model],'status':'transport_failure','answer':None,'correct':None,'call_count':CALLS[arm],'prompt_tokens':0,'completion_tokens':0,'elapsed_s':0.0,'usage_complete':False,'error':f'{type(e).__name__}: {e}'}
   cell.update({'tier':args.tier,'model_id':model,'seed':args.seed,'task_split':t['split'],'requested_calls':CALLS[arm],'events':events})
   append(raw,cell); cells.append(cell)
  if i%5==0: print(f'completed {i}/{len(tasks)}',flush=True)
 rows=summarize(cells,target_accuracy=0.5,min_cases=30)
 for r in rows: r.update({'tier':args.tier,'model_id':model,'seed':args.seed})
 outcsv=OUT/'results.csv'; exists=outcsv.exists()
 with outcsv.open('a',newline='',encoding='utf8') as f:
  fields=['tier','model_id','seed','domain','variant','protocol','task_count','completed_count','correct_count','error_count','abstained_count','invalid_count','coverage','task_success_rate','answered_accuracy','wilson_lower_95','call_count','prompt_tokens','completion_tokens','elapsed_s','usage_complete','gate']; w=csv.DictWriter(f,fieldnames=fields); 
  if not exists: w.writeheader()
  for r in rows: w.writerow({k:r.get(k) for k in fields})
 manifest={'tier':args.tier,'model_id':model,'seed':args.seed,'split':tasks[0]['split'] if tasks else None,'task_count':len(tasks),'raw_file':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'usage':budget.usage.to_dict(),'created_utc':utc()}
 (OUT/f'manifest-{args.tier}-{args.model}-seed{args.seed}.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 print(json.dumps(manifest,indent=2,sort_keys=True))
if __name__=='__main__': main()
