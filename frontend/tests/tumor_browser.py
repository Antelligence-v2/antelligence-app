"""Real local-browser acceptance; no simulated API responses."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(os.getenv('ANTELLIGENCE_E2E_OUTPUT', 'out/browser-acceptance'))
OUT.mkdir(parents=True, exist_ok=True)
URL = os.getenv('ANTELLIGENCE_FRONTEND_URL', 'http://127.0.0.1:8081/tumor')
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(URL)
    with page.expect_response(lambda r: '/simulation/tumor/run' in r.url and r.request.method == 'POST', timeout=120000) as event:
        page.get_by_role('button', name='Run Simulation').click()
    response = event.value
    result = response.json()
    (OUT / 'browser-run.json').write_text(json.dumps(result, indent=2))
    assert response.status == 200, result
    assert result['total_steps_run'] == result['config']['max_steps']
    assert result['tumor_statistics']['initial_living_cells'] > 0
    assert result['proof_ok'] is False
    assert result['proof_staged'] is True
    assert result['final_metrics']['total_api_calls'] == 0
    page.get_by_text('Simulation complete! Results loaded for playback.', exact=True).wait_for(timeout=10000)
    assert 'Failed to run simulation' not in page.locator('body').inner_text()
    page.get_by_text(result['run_id'], exact=True).wait_for(timeout=15000)
    page.reload()
    page.get_by_text(result['run_id'], exact=True).wait_for(timeout=15000)
    with page.expect_response(lambda r: r.url.endswith('/simulation/tumor/runs/' + result['run_id'])) as retrieved:
        page.get_by_role('button', name='Retrieve', exact=True).click()
    persisted = retrieved.value.json()
    assert persisted == result
    with page.expect_download() as download:
        page.get_by_role('button', name='Export JSON', exact=True).click()
    download.value.save_as(OUT / 'browser-export.json')
    exported = json.loads((OUT / 'browser-export.json').read_text())
    assert exported == result['provenance']
    assert not errors, errors
    body = page.locator('body').inner_text()
    (OUT / 'browser-after.txt').write_text(body)
    page.screenshot(path=str(OUT / 'browser-after.png'), full_page=True)
    receipt = {'url': page.url, 'run_id': result['run_id'], 'config_hash': result['config_hash'],
               'steps': result['total_steps_run'], 'initial_living_cells': result['tumor_statistics']['initial_living_cells'],
               'api_calls': result['final_metrics']['total_api_calls'], 'proof_ok': result['proof_ok'],
               'persisted_equals_post': persisted == result, 'export_equals_provenance': exported == result['provenance'],
               'page_errors': errors, 'screenshot': str(OUT / 'browser-after.png')}
    (OUT / 'browser-receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    browser.close()

