"""Adversarial UI timing with real, unchanged API responses."""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.async_api import async_playwright

FRONT = os.environ.get('ANTELLIGENCE_FRONTEND_URL', 'http://127.0.0.1:8080')
API = os.environ.get('ANTELLIGENCE_API_URL', 'http://127.0.0.1:18001')
OUT = Path(os.environ['ANTELLIGENCE_E2E_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(accept_downloads=True)
        response = await page.request.get(API + '/experiments')
        items = (await response.json())['experiments']
        chosen = [x for x in items if x['status'] == 'completed' and x['case_count'] > 0][:3]
        assert len(chosen) == 3
        a, b, c = [x['experiment_id'] for x in chosen]
        reports = {}
        for ident in (a,b,c):
            response = await page.request.get(API + '/experiments/' + ident)
            reports[ident] = await response.json()
        async def loaded(ident):
            await page.locator('a[href="/tumor?run=' + reports[ident]['cases'][0]['run_id'] + '"]').wait_for()
        async def select(ident):
            index = next(i for i,item in enumerate(items) if item['experiment_id'] == ident)
            await page.locator('aside').get_by_role('button').filter(has_text='cases').nth(index).click()
        await page.goto(FRONT + '/experiments?id=' + a, wait_until='networkidle')
        await loaded(a)
        ready = asyncio.Event(); release = asyncio.Event(); delivered = asyncio.Event()
        async def delayed_get(route):
            real = await route.fetch()
            ready.set()
            await release.wait()
            await route.fulfill(response=real)
            delivered.set()
        await page.route(API + '/experiments/' + b, delayed_get)
        await select(b)
        await asyncio.wait_for(ready.wait(), 10)
        await select(c)
        await loaded(c)
        release.set(); await asyncio.wait_for(delivered.wait(),10)
        await page.wait_for_timeout(200)
        selection_safe = parse_qs(urlparse(page.url).query).get('id') == [c]
        await page.unroute(API + '/experiments/' + b)
        await page.goto(FRONT + '/experiments?id=' + a, wait_until='networkidle')
        await loaded(a)
        ready = asyncio.Event(); release = asyncio.Event(); delivered = asyncio.Event()
        async def delayed_replay(route):
            real = await route.fetch()
            assert real.status == 200
            ready.set()
            await release.wait()
            await route.fulfill(response=real)
            delivered.set()
        await page.route('**/experiments/' + a + '/replay/*', delayed_replay)
        await page.get_by_role('button',name='Replay check',exact=True).first.click()
        await asyncio.wait_for(ready.wait(),10)
        await select(b)
        await loaded(b)
        release.set(); await asyncio.wait_for(delivered.wait(),10)
        await page.wait_for_timeout(200)
        async with page.expect_download() as downloading:
            await page.get_by_role('button',name='Export JSON',exact=True).click()
        download = await downloading.value
        await download.save_as(OUT/'report-after-cross-selection.json')
        response = await page.request.get(API + '/experiments/' + b)
        stored = await response.json()
        exported = json.loads((OUT/'report-after-cross-selection.json').read_text())
        replay_safe = exported == stored and all(x['experiment_id'] == b for x in exported['replay_checks'])
        result = {'real_api_responses_only': True, 'experiments': [a,b,c], 'latest_selection_wins': selection_safe, 'replay_stays_with_source_experiment': replay_safe}
        (OUT/'receipt.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
        await browser.close()
        assert selection_safe and replay_safe, result

asyncio.run(main())
