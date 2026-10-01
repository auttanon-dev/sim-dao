"""Two-year seed-11 metric-only / production-fix controls; never an 18-seed sweep."""
import argparse
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = '2fe002436c5c8a8483e2d4fa86834eae1773f265'
ap = argparse.ArgumentParser()
ap.add_argument('out', type=pathlib.Path)
args = ap.parse_args()
p = args.out.resolve()
if p.exists(): ap.error('choose a new output directory; existing evidence is never overwritten')
p.mkdir(parents=True)
archive = subprocess.check_output(['git', '-C', str(REPO), 'archive', BASE, 'tiandao'])
(p / 'before.tar').write_bytes(archive)
(p / 'before').mkdir()
tarfile.open(fileobj=io.BytesIO(archive)).extractall(p / 'before', filter='data')
shutil.copytree(REPO / 'tiandao', p / 'after' / 'tiandao',
                ignore=shutil.ignore_patterns('__pycache__', 'world.save*', 'backups', 'archive', '*.jsonl'))
env = os.environ | {'PYTHONIOENCODING': 'utf-8'}
runner = REPO / 'tools/food_storage_eval/balance_run.py'
checker = REPO / 'tools/food_storage_eval/check_observer.py'

def run(command, output):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', env=env)
    output.write_text(result.stdout, encoding='utf-8')
    output.with_suffix(output.suffix + '.err').write_text(result.stderr, encoding='utf-8')
    if result.returncode: raise RuntimeError(f'failed: {command}: {result.stderr}')

for name, source in [('metrics_only', 'before'), ('production_fix', 'after'), ('repeat', 'after')]:
    run([sys.executable, str(runner), str(p / source), '11', 'D', '--years', '2'], p / f'{name}.json')
for name, source in [('metrics_only', 'before'), ('production_fix', 'after')]:
    run([sys.executable, str(checker), str(p / source), str(p / f'{name}.json')], p / f'{name}_observer.txt')
before, after, repeat = [json.loads((p / f'{name}.json').read_text(encoding='utf-8'))
                         for name in ('metrics_only', 'production_fix', 'repeat')]
assert after == repeat, 'determinism changed (complete output JSON)'
keys = ['produced', 'volunteer_days', 'recruits', 'releases', 'kids', 'adults', 'food_gap', 'gold_gap', 'rng_sha256']
result = dict(base_revision=BASE, seed=11, years=2, observer_controls='passed', determinism='passed',
              compared={k: {'metrics_only': before[k], 'production_fix': after[k]} for k in keys},
              same_food_stats=before['food_stats_raw'] == after['food_stats_raw'],
              same_stocks=before['granary_sha256'] == after['granary_sha256'],
              same_volunteer_metrics=before['volunteer_metrics'] == after['volunteer_metrics'],
              schema_version=2, endpoint_metrics=after['volunteer_metrics'],
              base_archive_sha256=hashlib.sha256(archive).hexdigest(),
              after_food_sha256=hashlib.sha256((p/'after/tiandao/food.py').read_bytes()).hexdigest())
(p / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ('endpoint_metrics',)}, indent=2))
