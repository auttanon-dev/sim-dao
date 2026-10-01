"""Run the committed regression against the accepted source before and after the fix."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('snapshot_directory', type=Path, help='Output from prepare_snapshots.py')
args = parser.parse_args()
out = args.snapshot_directory.resolve()
repo = Path(__file__).resolve().parents[2]
env = dict(os.environ, PYTHONIOENCODING='utf-8')
script = "import sys,unittest; sys.path.insert(0,sys.argv.pop(1)); unittest.main(module='test_event_context',verbosity=2)"
for name, expected in [('accepted_before_fix', 1), ('accepted_fixed', 0)]:
    source = out / name
    if not (source / 'tiandao/sim.py').is_file():
        parser.error('Missing source snapshot: ' + str(source))
    result = subprocess.run([sys.executable, '-c', script, str(source)], cwd=repo, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    filename = 'regression_before_fix.txt' if expected else 'regression_after_fix.txt'
    (out / filename).write_bytes(result.stdout)
    print(result.stdout.decode('utf-8'))
    assert result.returncode == expected, 'Unexpected regression result for ' + name
    if expected:
        assert b'FAILED (failures=2)' in result.stdout, 'Expected exactly two moved-context failures'
print('Red/green verified; stationary controls pass before and after the fix')
