"""Verify retained artifacts, or explicitly reproduce the closed bounded case."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

KIT = Path(__file__).resolve().parent
REVISION = '95b07ea260d19771810e7748eb61fbbb50db2174'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def compare(observe, control, expected):
    keys = read(KIT / 'purity.json')['compared_keys']
    assert all(observe[k] == control[k] for k in keys), 'Observer/control differ'
    for result in (observe, control):
        assert result['end_day'] == 11010
        for day, group in (('10950', 'anchor10950_expected'), ('10980', 'anchor10980_expected')):
            actual = result['boundary_hashes'][day]
            assert all(actual[k] == v for k, v in expected[group].items()), 'Anchor differs'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    index = read(KIT / 'artifact_hashes.json')
    for name, expected_hash in index['retained_files'].items():
        assert hashlib.sha256((KIT / name).read_bytes()).hexdigest() == expected_hash, name
    evidence = read(KIT / 'purity_evidence.json')
    compare(evidence['observe'], evidence['control'], evidence)
    summary = read(KIT / 'summary.json')
    endpoint = summary['endpoint']
    assert endpoint['food_gap'] < 1e-4 and endpoint['gold_gap'] < 1e-6
    assert endpoint['demand_closure_gap'] < 1e-4
    for checks in summary['independent_checks'].values():
        assert all(v < 1e-6 for k, v in checks.items() if k.endswith('_gap'))
    if args.verify_only:
        assert args.output is None, '--verify-only takes no output directory'
        print('Retained hashes, purity, anchors and closure checks passed; no simulation run.')
        return
    if args.output is None:
        parser.error('Specify a new output directory, or --verify-only')
    if sys.version_info[:3] != (3, 12, 10):
        parser.error('Exact reproduction requires Python 3.12.10')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    archive = output / 'source.tar'
    repo = KIT.parents[2]
    subprocess.run(['git', 'archive', '--format=tar', '--output', str(archive), REVISION], cwd=repo, check=True)
    manifest = read(KIT / 'manifest.json')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['source_archive_sha256']
    subprocess.run(['tar', '-xf', str(archive), '-C', str(source)], check=True)
    env = os.environ | {'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    for mode in ('observe', 'control'):
        with (output / (mode + '.json')).open('w', encoding='utf-8') as stdout, \
                (output / (mode + '.stderr')).open('w', encoding='utf-8') as stderr:
            subprocess.run([sys.executable, str(KIT / 'worker.py'), str(source), '--mode', mode,
                            '--progress', str(output / 'progress.jsonl')], cwd=source,
                           env=env, stdout=stdout, stderr=stderr, check=True)
    observe, control = (read(output / (mode + '.json')) for mode in ('observe', 'control'))
    compare(observe, control, evidence)
    for result in (observe, control):
        assert result['food_gap'] < 1e-4 and result['gold_gap'] < 1e-6
        assert result['demand_closure_gap'] < 1e-4
    print('Reproduction stopped at day 11010; purity, anchors and endpoint closures passed.')


if __name__ == '__main__':
    main()
