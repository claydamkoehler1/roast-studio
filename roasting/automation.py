"""Confirmed, incremental recipe execution. This class never changes machine phases."""
import json
from .hardware import LIMITS
from .recipes import validate_steps, as_group, matches


class RecipeRunner:
    def __init__(self, steps, initial, recipe=True):
        self.steps = validate_steps(steps)
        self.groups = [as_group(s) for s in self.steps]
        self.initial = {key: int(value) for key, value in initial.items()}
        self.recipe = recipe
        self.state = 'running'
        self.reason = ''
        self.done = set()
        self.skipped = set()
        self.queue = [dict(control=k, value=v, index=None) for k, v in self.initial.items()]
        self.expected = None
        self.pending = None
        self.rising = False
        self.last_completed_index = None
        self.started = {}
        self.initial_indices = {i for i, g in enumerate(self.groups)
                                if g['conditions'] == [dict(sensor='time', op='>=', value=0)]}

    def mark_started(self, index, sample, elapsed, log):
        key = None if index is None or index in self.initial_indices else index
        if key in self.started or not self.recipe:
            return
        actions = ([dict(control=k, value=v) for k, v in self.initial.items()]
                   if key is None else self.groups[key]['actions'])
        settings = {k: sample[k] for k in LIMITS}
        settings.update({a['control']: a['value'] for a in actions if a['control'] in LIMITS})
        number = 1 if key is None else 2 + sum(i not in self.initial_indices for i in range(key))
        marker = dict(index=key, step=number, elapsed=elapsed, ibts=sample.get('ibts'), settings=settings)
        log('recipe_step', json.dumps(marker))
        self.started[key] = marker

    def due(self, step, sample, elapsed):
        return matches(as_group(step), sample, elapsed, self.rising)

    def pause(self, reason, log):
        if self.state == 'paused':
            return
        self.state, self.reason = 'paused', reason
        self.skipped.update(job['index'] for job in self.queue if job['index'] is not None)
        self.queue.clear()
        self.pending = None
        log('note', 'Automation paused: ' + reason)

    def resume(self, sample, elapsed, log):
        # Resuming follows future steps; do not replay old heat changes after an interruption.
        self.rising = self.rising or (elapsed > 65 and sample.get('ror', 0) > 0)
        for i, step in enumerate(self.steps):
            if i not in self.done and self.due(step, sample, elapsed):
                self.skipped.add(i)
        self.queue.clear()
        self.pending = None
        self.expected = {key: sample[key] for key in LIMITS}
        self.state, self.reason = 'running', ''
        log('note', 'Recipe resumed from current settings; overdue changes skipped')

    def tick(self, status, elapsed, send, log):
        if self.state != 'running':
            return
        if not status['fresh'] or not status['armed'] or status.get('error'):
            self.pause(status.get('error') or 'Machine controls unavailable. Enable controls, then resume.', log)
            return
        sample = status['telemetry']
        if sample.get('machine_state') != 'roasting':
            self.pause('Machine left roasting mode.', log)
            return
        self.rising = self.rising or (elapsed > 65 and sample.get('ror', 0) > 0)
        queued = {job['index'] for job in self.queue}
        due = [(i, step) for i, step in enumerate(self.steps)
               if i not in self.done | self.skipped | queued and self.due(step, sample, elapsed)]
        # Preserve the recipe's group/action order, as RoasTime does.
        for i, step in due:
            actions = self.groups[i]['actions']
            self.queue.extend(dict(action, index=i, last=j == len(actions)-1) for j, action in enumerate(actions))
        if status.get('pending'):
            return
        values = {key: sample[key] for key in LIMITS}
        if self.pending:
            key, target = self.pending
            if values[key] != target:
                self.pause('The last setting was not confirmed by the R2.', log)
                return
            self.expected[key] = target
            self.pending = None
        if self.expected is not None and values != self.expected:
            self.pause('Settings changed at the machine. Review before resuming.', log)
            return
        self.expected = values
        while self.queue:
            job = self.queue[0]
            key, target = job['control'], job['value']
            if key not in LIMITS:
                try:
                    log(key, target)
                except Exception as exc:
                    self.pause(str(exc), log)
                    return
            if key not in LIMITS or values[key] == target:
                self.mark_started(job['index'], sample, elapsed, log)
                if job['index'] is not None and job.get('last', True):
                    self.done.add(job['index'])
                    self.last_completed_index = job['index']
                if key in LIMITS:
                    log('control', f"{'recipe' if self.recipe else 'initial'}: {key}={target} confirmed")
                self.queue.pop(0)
                continue
            value = values[key] + (1 if target > values[key] else -1)
            try:
                send(key, value)
            except Exception as exc:
                self.pause(str(exc), log)
                return
            self.pending = (key, value)
            self.mark_started(job['index'], sample, elapsed, log)
            log('control', f"{'recipe' if self.recipe else 'initial'}: {key}={value} requested")
            return
        if len(self.done | self.skipped) == len(self.steps):
            self.state = 'complete'

    def snapshot(self):
        next_step = (self.steps[self.queue[0]['index']] if self.queue[0]['index'] is not None else self.queue[0]) if self.queue else next((dict(s, index=i) for i, s in enumerate(self.steps) if i not in self.done | self.skipped), None)
        return dict(state=self.state, reason=self.reason, recipe=self.recipe, next=next_step,
                    applying_index=self.queue[0]['index'] if self.queue else None,
                    initializing=any(job['index'] is None for job in self.queue),
                    last_completed_index=self.last_completed_index,
                    completed=sorted(self.done), skipped=sorted(self.skipped), total=len(self.steps))
