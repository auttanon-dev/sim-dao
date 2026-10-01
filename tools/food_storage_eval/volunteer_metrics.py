"""Observer-only volunteer lifecycle metrics (schema 2).

Flag spells end at policy release, exact death_day, or an observed other reset.
Pruning is never a release. Production is the simulation's food tick interval,
not real daily time use: eligibility at tick entry credits [day-days, day).
"""
import collections
import statistics


def median(values):
    return statistics.median(values) if values else None


class VolunteerMetrics:
    def __init__(self, working):
        self.working = working
        self.spells = []
        self.open = {}
        self.intervals = collections.defaultdict(list)
        self.worker_days = collections.Counter()
        self.last_production_day = None
        self.last_producers = []

    def begin(self, ch, day, reason):
        if ch.alive and ch.fieldwork and ch.cid not in self.open:
            spell = dict(id=len(self.spells), cid=ch.cid, start=day, end=None, end_reason=None, entry_reason=reason)
            self.spells.append(spell)
            self.open[ch.cid] = spell

    def close(self, ch, day, reason):
        spell = self.open.pop(ch.cid, None)
        if spell is not None:
            spell.update(end=max(spell['start'], day), end_reason=reason)

    def observe(self, sim):
        for cid in list(self.open):
            ch = sim.cast[cid]
            if not ch.alive:
                self.close(ch, ch.death_day if ch.death_day is not None else sim.day, 'death')
            elif not ch.fieldwork:
                self.close(ch, sim.day, 'other')
        for cid in sim.alive_cids:
            self.begin(sim.cast[cid], sim.day, 'observed')

    def credit_production(self, sim, days):
        if days <= 0:
            return
        self.observe(sim)
        self.last_production_day = sim.day
        self.last_producers = []
        for cid in sim.alive_cids:
            ch = sim.cast[cid]
            if ch.fieldwork and self.working(ch, sim.day):
                self.last_producers.append(cid)
                start, end = sim.day - days, sim.day
                intervals = self.intervals[cid]
                # A policy exit/re-entry also separates intervals even if adjacent.
                spell_id = self.open[cid]['id']
                if intervals and intervals[-1]['end'] == start and intervals[-1]['spell'] == spell_id:
                    intervals[-1]['end'] = end
                else:
                    intervals.append(dict(start=start, end=end, spell=spell_id))
                self.worker_days[cid] += days

    def labour_transition(self, sim, before):
        for cid, was in before.items():
            ch = sim.cast[cid]
            if not ch.alive:
                self.close(ch, ch.death_day if ch.death_day is not None else sim.day, 'death')
            elif was and not ch.fieldwork:
                self.close(ch, sim.day, 'policy_release')
            elif not was and ch.fieldwork:
                self.begin(ch, sim.day, 'recruitment')

    def summary(self, sim):
        self.observe(sim)
        flagged = sorted(cid for cid in sim.alive_cids if sim.cast[cid].fieldwork)
        productive = [cid for cid in flagged if self.working(sim.cast[cid], sim.day)]
        durations = [sim.day - self.open[cid]['start'] for cid in flagged]
        productive_tenures = [sim.day - self.open[cid]['start'] for cid in productive]
        completed = [sp for sp in self.spells if sp['end'] is not None]
        by_reason = {}
        for reason in ('policy_release', 'death', 'other'):
            samples = [sp['end'] - sp['start'] for sp in completed if sp['end_reason'] == reason]
            by_reason[reason] = dict(count=len(samples), flag_tenure_days=samples, median=median(samples))
        actual = [iv['end'] - iv['start'] for group in self.intervals.values() for iv in group]
        return dict(schema_version=2, alive_flagged=len(flagged), alive_productive=len(productive),
                    last_production_day=self.last_production_day,
                    last_interval_productive_cids=sorted(self.last_producers),
                    alive_produced_last_interval=sum(cid in sim.alive_cids for cid in self.last_producers),
                    alive_flagged_produced_last_interval=sum(cid in flagged for cid in self.last_producers),
                    alive_flagged_cids=flagged, alive_productive_cids=productive,
                    open_flag_tenure_days=durations, open_flag_tenure_median=median(durations),
                    productive_people_flag_tenure_days=productive_tenures,
                    productive_people_flag_tenure_median=median(productive_tenures),
                    completed_by_reason=by_reason, flag_spells=self.spells,
                    productive_intervals={cid: iv for cid, iv in sorted(self.intervals.items())},
                    productive_interval_days=actual, productive_interval_median=median(actual),
                    productive_worker_days=sum(self.worker_days.values()),
                    productive_worker_days_by_cid=dict(sorted(self.worker_days.items())))

    def install(self, sim_class, food):
        """Install once in an isolated evaluation process, no RNG or policy changes."""
        original_adapt, original_tick = food._adapt_labour, food.tick
        original_kill, original_prune = sim_class.kill, sim_class.prune_departed

        def adapt(sim, eaters, workers, *args, **kwargs):
            before = {ch.cid: ch.fieldwork for groups in (workers, eaters) for grp in groups.values() for ch in grp}
            result = original_adapt(sim, eaters, workers, *args, **kwargs)
            self.labour_transition(sim, before)
            return result

        def tick(sim, days):
            self.credit_production(sim, days)
            result = original_tick(sim, days)
            self.observe(sim)
            return result

        def kill(sim, ch, *args, **kwargs):
            result = original_kill(sim, ch, *args, **kwargs)
            if not ch.alive:
                self.close(ch, ch.death_day if ch.death_day is not None else sim.day, 'death')
            return result

        def prune(sim, *args, **kwargs):
            self.observe(sim)  # Close death before fieldwork is discarded by Departed.
            result = original_prune(sim, *args, **kwargs)
            self.observe(sim)
            return result

        food._adapt_labour, food.tick = adapt, tick
        sim_class.kill, sim_class.prune_departed = kill, prune


def aggregate(summaries):
    """Equal-weight seed means and separately labelled pooled-person median."""
    seeds = list(summaries)
    samples = [value for s in seeds for value in s['open_flag_tenure_days']]
    seed_medians = [s['open_flag_tenure_median'] for s in seeds if s['open_flag_tenure_median'] is not None]
    return dict(seeds=len(seeds), mean_alive_flagged=statistics.mean(s['alive_flagged'] for s in seeds) if seeds else None,
                mean_alive_productive=statistics.mean(s['alive_productive'] for s in seeds) if seeds else None,
                mean_seed_flag_tenure_medians=statistics.mean(seed_medians) if seed_medians else None,
                nonempty_seed_medians=len(seed_medians), pooled_person_flag_tenure_median=median(samples))
