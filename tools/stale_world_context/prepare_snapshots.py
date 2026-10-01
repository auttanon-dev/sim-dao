"""Build fresh, revision-pinned source snapshots for this historical bug."""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output_directory', type=Path, help='New directory; existing outputs are refused')
args = parser.parse_args()
out = args.output_directory.resolve()
out.mkdir(parents=True, exist_ok=False)
repo = Path(__file__).resolve().parents[2]
baseline = '32c147809b80927480c663d72bd5a2ea42b15f62'
accepted = '560d879dc4f6d9f23f1421a44b2fc6aaa39cc115'
addition = '''        # Nested world events (notably conscription) can move the active actor.
        # Prepare peers, eligibility, targets and action funds in the actor's
        # current world, after those events, rather than the world of this turn's start.
        world = self.world(actor.world_id)

'''
anchor = '        # เด็กมีชีวิตและประวัติของตัวเอง แต่ยังไม่ใช้เมนูการกระทำของผู้ใหญ่ การปล่อยลงไป'
for name, revision, fixed in [('baseline', baseline, False), ('baseline_fixed', baseline, True),
                              ('accepted_before_fix', accepted, False), ('accepted_fixed', accepted, True)]:
    dest = out / name
    dest.mkdir()
    archive = out / (name + '.tar')
    subprocess.run(['git', 'archive', '--format=tar', '--output=' + str(archive), revision, 'tiandao'],
                   cwd=repo, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter='data')
    if fixed:
        simfile = dest / 'tiandao/sim.py'
        text = simfile.read_text(encoding='utf-8')
        assert text.count(anchor) == 1, 'Unexpected snapshot context'
        simfile.write_text(text.replace(anchor, addition + anchor), encoding='utf-8')
    hashes = {str(f.relative_to(dest)): hashlib.sha256(f.read_bytes()).hexdigest()
              for f in dest.rglob('*') if f.is_file()}
    (out / (name + '_manifest.json')).write_text(json.dumps(dict(base_revision=revision,
        fixed=fixed, files=hashes), indent=2), encoding='utf-8')
print('Created four pinned snapshots in', out)
