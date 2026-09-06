"""Real browser acceptance for the Experiment Lab; no mocked API data."""
import csv
import io
import json
import os
from pathlib import Path
from urllib.parse import unquote
from playwright.sync_api import sync_playwright

OUT = Path(os.environ['ANTELLIGENCE_E2E_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.getenv('ANTELLIGENCE_FRONTEND_URL', 'http://127.0.0.1:8081').rstrip('/')
API = os.getenv('ANTELLIGENCE_API_URL', 'http://127.0.0.1:8001').rstrip('/')
SEEDS = [17, 23, 42, 71, 99]
ARMS = ['no_bots', 'fixed', 'pheromone']

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1440, 'height':1000}, accept_downloads=True)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + '/', wait_until='networkidle')
    page.screenshot(path=str(OUT/'home.png'), full_page=True)
    page.get_by_text('Experiment Lab', exact=True).first.click(timeout=5000)
    page.get_by_role('heading', name='Experiment Lab', exact=True).wait_for()
    page.screenshot(path=str(OUT/'lab-before.png'), full_page=True)
    page.get_by_label('Experiment name', exact=True).fill('Swarm controls — five-seed experiment')
    page.get_by_label('Seeds', exact=True).fill(', '.join(map(str,SEEDS)))
    page.get_by_label('Steps per run', exact=True).fill('100')
    page.get_by_label('Nanobots', exact=True).fill('10')
    with page.expect_response(lambda r: r.url.rstrip('/') == API+'/experiments' and r.request.method=='POST', timeout=120000) as completed:
        page.get_by_role('button', name='Run experiment', exact=True).click()
    response = completed.value
    assert response.status == 200, (response.status,response.text())
    experiment = response.json()
    (OUT/'experiment-post.json').write_text(json.dumps(experiment,indent=2))
    assert experiment['status']=='completed', experiment
    assert experiment['case_count']==len(SEEDS)*len(ARMS)==len(experiment['cases'])
    assert experiment['seed_count']==len(SEEDS)
    assert experiment['matched_initial_geometry'] is True
    cases = experiment['cases']
    assert [(c['seed'],c['arm']) for c in cases] == [(s,a) for s in SEEDS for a in ARMS]
    assert len({c['run_id'] for c in cases})==len(cases)
    for seed in SEEDS:
        group=[c for c in cases if c['seed']==seed]
        assert len({c['initial_geometry_hash'] for c in group})==1
        assert all(c['initial_geometry_hash'] for c in group)
        assert [c['config']['n_nanobots'] for c in group]==[0,10,10]
        assert [c['config']['pheromones_enabled'] for c in group]==[False,False,True]
        for case in group:
            assert case['config']['seed']==seed and case['config']['offline'] is True
            assert case['config']['agent_type']=='Rule-Based'
            assert case['initial_living_cells']>0
            expected=100*(case['initial_living_cells']-case['final_living_cells'])/case['initial_living_cells']
            assert abs(case['net_cell_reduction_pct']-expected)<1e-7
            page.locator('a[href*="'+case['run_id']+'"]').first.wait_for()
    assert experiment['experiment_id'] in page.url, page.url
    page.get_by_role('columnheader',name='vs fixed (pp)',exact=True).wait_for(timeout=5000)
    page.get_by_role('columnheader',name='vs no bots (pp)',exact=True).wait_for(timeout=5000)
    stored = page.request.get(API+'/experiments/'+experiment['experiment_id'])
    assert stored.status==200 and stored.json()==experiment
    for format_name in ['JSON','CSV']:
        with page.expect_download() as downloaded:
            page.get_by_role('button',name='Export '+format_name,exact=True).click()
        target=OUT/('report.'+format_name.lower())
        downloaded.value.save_as(str(target))
    assert json.loads((OUT/'report.json').read_text())==experiment
    all_csv_rows=list(csv.DictReader(io.StringIO((OUT/'report.csv').read_text())))
    assert all(None not in row and None not in row.values() for row in all_csv_rows)
    rows=[row for row in all_csv_rows if row['row_type']=='case']
    summary_rows=[row for row in all_csv_rows if row['row_type']=='summary']
    assert len(rows)==len(cases)
    assert len(summary_rows)==len(ARMS)
    assert len(all_csv_rows)==len(rows)+len(summary_rows)
    assert {row['case_id'] for row in rows}=={c['case_id'] for c in cases}
    assert {row['run_id'] for row in rows}=={c['run_id'] for c in cases}
    case=cases[1]
    with page.expect_response(lambda r: '/replay/' in r.url and r.request.method=='POST',timeout=60000) as replayed:
        page.get_by_role('button',name='Replay check',exact=True).nth(1).click()
    replay_response=replayed.value
    assert replay_response.status==200, replay_response.text()
    check=replay_response.json()
    assert check['case_id']==case['case_id'] and check['status']=='matched',check
    assert check['expected_trace_hash']==check['actual_trace_hash']==case['trace_hash']
    assert check['replay_run_id']!=case['run_id']
    original=page.request.get(API+'/simulation/tumor/runs/'+case['run_id']).json()
    rerun=page.request.get(API+'/simulation/tumor/runs/'+check['replay_run_id']).json()
    for key in ['config','history','final_metrics','tumor_statistics','total_time','total_steps_run']:
        assert original[key]==rerun[key],key
    assert original['proof_ok'] is False and rerun['proof_ok'] is False
    with page.expect_response(lambda r: '/replay/' in r.url and r.request.method=='POST',timeout=60000) as replayed_again:
        page.get_by_role('button',name='Replay check',exact=True).nth(1).click()
    second_check=replayed_again.value.json()
    assert second_check['status']=='matched'
    assert second_check['replay_run_id'] not in [case['run_id'],check['replay_run_id']]
    page.get_by_text('checked: '+second_check['checked_at'],exact=True).wait_for()
    with page.expect_download() as replay_export:
        page.get_by_role('button',name='Export JSON',exact=True).click()
    replay_export.value.save_as(str(OUT/'report-after-replays.json'))
    stored_with_replays=page.request.get(API+'/experiments/'+experiment['experiment_id']).json()
    assert len(stored_with_replays['replay_checks'])==2
    assert json.loads((OUT/'report-after-replays.json').read_text())==stored_with_replays
    page.reload(wait_until='networkidle')
    page.locator('a[href*="'+case['run_id']+'"]').first.wait_for()
    fresh=page.request.get(API+'/experiments/'+experiment['experiment_id']).json()
    assert any(c['case_id']==case['case_id'] and c['status']=='matched' for c in fresh['replay_checks'])
    page.screenshot(path=str(OUT/'lab-after.png'),full_page=True)
    (OUT/'lab-after.txt').write_text(page.locator('body').inner_text())
    (OUT/'experiment-final.json').write_text(json.dumps(fresh,indent=2))
    (OUT/'replay-check.json').write_text(json.dumps(check,indent=2))
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'lab-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
    assert not errors,errors
    receipt={'url':page.url,'experiment_id':experiment['experiment_id'],'cases':len(cases),'seeds':SEEDS,'arms':ARMS,'same_initial_geometry':True,'exact_saved_report':True,'json_export_exact':True,'csv_cases':len(rows),'local_replay':check['status'],'actual_replay_trace_equal':True,'proof_ok':False,'page_errors':errors,'screenshot':str(OUT/'lab-after.png')}
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    browser.close()
