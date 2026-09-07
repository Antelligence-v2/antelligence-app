"""Rebuild the pinned research fixture from explicitly downloaded source files.

No network/inference. Usage: python scripts/build_research_fixtures.py RAW_DIRECTORY
Raw hashes/URLs and licenses are part of the generated manifest. Every excluded
record has a recorded reason. Selection precedes model execution, not result-driven.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from backend.research_data import BUNDLE_PATH, digest, project_finqa, project_pubmed

SOURCES = {
    'pubmedqa.json': ('8b3276be8942ebbd77f3ddcda12c1749bf0e490045a736fd8438ee40cf37a41d', 'pubmedqa/pubmedqa', '1cbae8e92f72f20c8d3747cbb3bf5bc53554d997', 'data/ori_pqal.json'),
    'pubmedqa-test.json': ('939fe566f09017d13b1ca64d2ddfee0bc2374b366048152997669cccedc44d51', 'pubmedqa/pubmedqa', '1cbae8e92f72f20c8d3747cbb3bf5bc53554d997', 'data/test_ground_truth.json'),
    'finqa-dev.json': ('a847fb7e0d61a3125a1e2909852df6b89f1ee64d2c5ff1bf689e332214deee51', 'czyssrs/FinQA', '0f16e2867befa6840783e58be38c9efb9229d742', 'dataset/dev.json'),
    'finqa-test.json': ('831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc', 'czyssrs/FinQA', '0f16e2867befa6840783e58be38c9efb9229d742', 'dataset/test.json'),
}


def build(raw_dir):
    source_manifest, raw = {}, {}
    for name, (sha, repo, rev, path) in SOURCES.items():
        data = (raw_dir / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError(f'Pinned source checksum mismatch: {name}')
        raw[name] = json.loads(data)
        source_manifest[name] = {'sha256': sha, 'url': f'https://raw.githubusercontent.com/{repo}/{rev}/{path}', 'bytes': len(data)}
    tasks, audit = [], {}
    for dataset in ('pubmedqa', 'finqa'):
        for split in ('development', 'evaluation'):
            if dataset == 'pubmedqa':
                rows = [(sid, row) for sid, row in raw['pubmedqa.json'].items()
                        if (sid in raw['pubmedqa-test.json']) == (split == 'evaluation')]
            else:
                rows = [(row['id'], row) for row in raw['finqa-dev.json' if split == 'development' else 'finqa-test.json']]
            accepted, excluded = [], []
            for sid, row in rows:
                try:
                    task = project_pubmed(sid, row, split) if dataset == 'pubmedqa' else project_finqa(row, split)
                    accepted.append(task)
                except ValueError as exc:
                    excluded.append({'source_id': sid, 'reason': str(exc)})
            accepted.sort(key=lambda t: hashlib.sha256(t['source_id'].encode()).hexdigest())
            assert len(accepted) >= 50
            tasks.extend(accepted[:50])
            audit[f'{dataset}:{split}'] = {'source_count': len(rows), 'eligible_count': len(accepted),
                  'selected_count': 50, 'excluded': excluded,
                  'exclusion_counts': dict(Counter(x['reason'] for x in excluded))}
    datasets = []
    for key, label, domain, license, rev, url in [
        ('pubmedqa', 'PubMedQA abstract QA (compact public subset)', 'medical',
         'Repository MIT; underlying abstracts retain source rights. Attribution: Jin et al., PubMedQA (2019).',
         SOURCES['pubmedqa.json'][2], 'https://pubmedqa.github.io/'),
        ('finqa', 'FinQA-derived numeric QA (compact public subset)', 'finance',
         'Dataset CC BY 4.0; repository code MIT. Attribution: Chen et al., FinQA (2021).',
         SOURCES['finqa-dev.json'][2], 'https://finqasite.github.io/')]:
        datasets.append(dict(key=key, label=label, domain=domain, license=license, revision=rev, source_url=url,
                 source_sha256=digest({n: d for n, d in source_manifest.items() if n.startswith(key)}),
                 development_count=50, evaluation_count=50, limitations=[
                     'Public data; contamination unknown. Compact bounded-context subset, not the entire benchmark.',
                     'Development/evaluation IDs are disjoint; no model-unseen claim.',
                     'FinQA answers require explicit units; inconsistent/non-numeric labels excluded before experiments.' if key == 'finqa'
                     else 'Abstract QA measures literature comprehension, not clinical decisions.']))
    assert len(tasks) == len({t['task_id'] for t in tasks}) == 200
    bundle = dict(schema_version='antelligence.research-fixtures.v1', selection='SHA256(source_id) order, first 50 eligible per official split; no model outcomes',
                  sources=source_manifest, audit=audit, datasets=datasets, tasks=tasks)
    BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    BUNDLE_PATH.write_bytes(data)
    print(json.dumps({'output': str(BUNDLE_PATH), 'sha256': hashlib.sha256(data).hexdigest(), 'tasks': len(tasks),
                      'audit': {k: {n: v for n, v in d.items() if n != 'excluded'} for k,d in audit.items()}}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_directory', type=Path)
    build(parser.parse_args().raw_directory)
