"""Real local models -> research API -> browser -> SQLite/export acceptance.
No mocked responses. Set RESEARCH_RUN_ID to inspect an existing run without inference.
"""
import csv
import io
import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path(os.environ['ANTELLIGENCE_E2E_OUTPUT']);OUT.mkdir(parents=True,exist_ok=True)
BASE=os.getenv('ANTELLIGENCE_FRONTEND_URL','http://127.0.0.1:8080')
API=os.getenv('ANTELLIGENCE_API_URL','http://127.0.0.1:18001')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
    errors=[];posts=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
    run_id=os.getenv('RESEARCH_RUN_ID')
    page.goto(BASE+'/research'+('?run='+run_id if run_id else ''),wait_until='networkidle')
    page.get_by_role('heading',name='Swarm Research Workbench',exact=True).wait_for()
    assert not posts,posts
    if not run_id:
        page.get_by_label('Run name',exact=True).fill('Two-model communication pilot — public research only')
        page.get_by_label('Tasks per dataset',exact=True).fill('1')
        page.get_by_label('Max wall seconds',exact=True).fill('900')
        with page.expect_response(lambda r:r.url==API+'/research/runs' and r.request.method=='POST',timeout=60000) as response:
            page.get_by_role('button',name='Start research run',exact=True).click()
        assert response.value.status==202,response.value.text()
        run_id=response.value.json()['run_id']
        (OUT/'started.json').write_text(json.dumps(response.value.json(),indent=2))
    for _ in range(500):
        report=page.request.get(API+'/research/runs/'+run_id,timeout=30000).json()
        (OUT/'progress.json').write_text(json.dumps({'run_id':run_id,'status':report['status'],'actual_calls':report['actual_calls'],'completed_cells':report['completed_cells'],'updated_at':report['updated_at']},indent=2))
        if report['status']!='running':break
        page.wait_for_timeout(2000)
    assert report['status']!='running','bounded browser polling exhausted'
    (OUT/'report.json').write_text(json.dumps(report,indent=2))
    page.reload(wait_until='networkidle')
    page.get_by_role('button',name='Export JSON',exact=True).wait_for(timeout=30000)
    for fmt in ('JSON','CSV'):
        with page.expect_download() as download:
            page.get_by_role('button',name='Export '+fmt,exact=True).click()
        download.value.save_as(str(OUT/('export.'+fmt.lower())))
    assert json.loads((OUT/'export.json').read_text())==report
    rows=list(csv.DictReader(io.StringIO((OUT/'export.csv').read_text())))
    assert all(None not in r and None not in r.values() for r in rows)
    assert len([r for r in rows if r['row_type']=='event'])==len(report['events'])
    assert len([r for r in rows if r['row_type']=='cell'])==report['total_cells']
    assert {r['domain'] for r in report['summary']}=={'medical','finance'}
    assert report['proof_ok'] is False and report['metered_api_cost_usd']==0
    assert all(r['gate'] in {'unknown','insufficient_evidence'} for r in report['summary'])
    assert len({e['served_model'] for e in report['events'] if e.get('served_model')})==2
    assert all('expected_answer' not in json.dumps(e['prompt_messages']) and 'tolerance' not in json.dumps(e['prompt_messages']) for e in report['events'])
    assert len(report['selected_task_ids'])==2 and report['total_cells']==len(report['cells'])==10
    page.locator('details').first.locator('summary').click()
    page.screenshot(path=str(OUT/'workbench-desktop.png'),full_page=True)
    (OUT/'body.txt').write_text(page.locator('body').inner_text())
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'workbench-mobile.png'),full_page=True)
    overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
    assert not errors,errors
    assert not overflow,'mobile horizontal overflow'
    receipt=dict(run_id=run_id,url=BASE+'/research?run='+run_id,status=report['status'],actual_calls=report['actual_calls'],stored_events=len(report['events']),cells=len(report['cells']),summary=report['summary'],json_export_exact=True,csv_aligned=True,no_post_on_mount=True,page_errors=errors,mobile_overflow=overflow)
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
    browser.close()
