import random
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from tiandao import config as C
from tiandao import rules as R
from tiandao import models as M
from tiandao.sim import Sim

sim = Sim(seed=0)
w = sim.worlds[0]

c = M.Character(1, "TestChar", 0, "วิถีดาบ", ["วิถีดาบ"], 0, blood={"human": 1.0})
c.realm = 4 # ก่อธาตุ is realm 5, so realm+1 = 5
c.dao = "วิถีดาบ"

# Test break
c.insight = 1000
res, text = R.attempt_break(sim, c, w, sim.rng)
print(res, text)

c.realm = 6
c.insight = 1000
res, text = R.attempt_break(sim, c, w, sim.rng)
print(res, text)
