"""Recipe semantics observed in RoasTime 4.14.3; independent implementation.

Storage accepts legacy single-action steps and condition/action groups. Units are
Celsius and seconds. Import never silently drops an unsupported command or model.
"""
import copy
import json
import math
from .hardware import LIMITS

ACTIONS = set(LIMITS) | {'popup', 'end_alert', 'yellow', 'first_crack'}


def numeric(value, low, high, name, whole=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or (whole and value != int(value)):
        raise ValueError(f'{name} must be {low}–{high}' + (' (whole number)' if whole else ''))
    return int(value) if whole else value


def as_group(step):
    if 'conditions' in step:
        return copy.deepcopy(step)
    conditions = [dict(sensor=step['trigger'], op=step.get('comparison', '>='), value=step['at'])]
    if step['trigger'] != 'time':
        conditions.append(dict(sensor='time', op='>=', value=step.get('min_time', 5)))
    return dict(conditions=conditions, actions=[dict(control=step['control'], value=step['value'])], reason=step.get('reason', ''),
                after_turn=bool(step.get('after_turn', False)))


def validate_steps(steps):
    if not isinstance(steps, list) or len(steps) > 100:
        raise ValueError('A recipe supports up to 100 condition groups')
    result = copy.deepcopy(steps)
    for step in result:
        if not isinstance(step, dict):
            raise ValueError('Invalid recipe step')
        if 'conditions' not in step and not {'trigger', 'at', 'control', 'value'} <= step.keys():
            raise ValueError('Invalid recipe step')
        if 'conditions' not in step and step.get('trigger') != 'time':
            step.setdefault('min_time', 5)
            step.setdefault('comparison', '>=')
        group = as_group(step)
        conditions, actions = group.get('conditions'), group.get('actions')
        if not isinstance(conditions, list) or not 1 <= len(conditions) <= 8 or not isinstance(actions, list) or not 1 <= len(actions) <= 20:
            raise ValueError('Each group needs 1–8 conditions and 1–20 actions')
        if 'after_turn' in step and type(step['after_turn']) is not bool:
            raise ValueError('After-turn guard must be true or false')
        for c in conditions:
            if not isinstance(c, dict) or c.get('sensor') not in ('time', 'ibts', 'bt') or c.get('op') not in ('>=', '<='):
                raise ValueError('Conditions support time, IBTS or bean probe with ≥ or ≤')
            if c['sensor'] == 'time' and c['op'] != '>=':
                raise ValueError('Elapsed-time conditions must use ≥')
            numeric(c.get('value'), 0, 3600 if c['sensor'] == 'time' else 310, 'Condition')
        for a in actions:
            if not isinstance(a, dict) or a.get('control') not in ACTIONS:
                raise ValueError('Unsupported recipe action')
            if a['control'] in LIMITS:
                numeric(a.get('value'), *LIMITS[a['control']], 'Standard R2 setting', whole=True)
            elif a['control'] in ('popup', 'end_alert'):
                if not isinstance(a.get('value'), str) or not a['value'].strip() or len(a['value']) > 1000:
                    raise ValueError('Recipe alert needs text (maximum 1000 characters)')
            elif a.get('value') not in (None, 1):
                raise ValueError('Milestone action value must be 1')
        if not isinstance(group.get('reason', ''), str) or len(group.get('reason', '')) > 1500:
            raise ValueError('Recipe note too long')
    return result


def initial_settings(steps):
    values = dict(power=7, fan=3, drum=9)
    for step in steps:
        group = as_group(step)
        if group['conditions'] == [dict(sensor='time', op='>=', value=0)]:
            values.update({a['control']: int(a['value']) for a in group['actions'] if a['control'] in LIMITS})
    return values


def matches(group, sample, elapsed, rising=False):
    if group.get('after_turn') and not rising:
        return False
    for condition in group['conditions']:
        value = elapsed if condition['sensor'] == 'time' else sample.get(condition['sensor'])
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
        if not (value >= condition['value'] if condition['op'] == '>=' else value <= condition['value']):
            return False
    return True


def import_roastime(raw):
    if not isinstance(raw, dict) or raw.get('deviceType') != 'r2':
        raise ValueError('Import an explicitly labeled standard R2 recipe (deviceType: r2)')
    unit = raw.get('tempMeasurement')
    if unit not in ('C', 'F'):
        raise ValueError('Recipe must specify C or F temperature measurement')
    def celsius(v):
        numeric(v, 0, 650, 'Temperature')
        return round((v - 32) / 1.8, 6) if unit == 'F' else v
    start = raw.get('startSettings')
    if not isinstance(start, dict) or not set(LIMITS) <= start.keys():
        raise ValueError('Recipe needs initial power, fan and drum settings')
    if start.get('airHeat', 0):
        raise ValueError('Air-heater recipes are not supported by the standard R2')
    steps = [dict(trigger='time', at=0, control=k, value=start[k]) for k in LIMITS]
    events = raw.get('events')
    if isinstance(events, str):
        try:
            events = json.loads(events)
        except (ValueError, TypeError) as exc:
            raise ValueError('Invalid RoasTime events JSON') from exc
    if not isinstance(events, list) or len(events) > 96:
        raise ValueError('Invalid RoasTime event groups')
    groups = list(events)
    end = raw.get('endSettings')
    # RoasTime suppresses the separate endSettings when the first event in any
    # regular group already contains an EndRoast action.
    has_end = any(isinstance(g, list) and g and isinstance(g[0], dict) and
                  isinstance(g[0].get('actions', []), list) and
                  any(isinstance(a, dict) and a.get('action') == 4 for a in g[0].get('actions', []))
                  for g in groups)
    if end and not has_end:
        groups.append(end)
    action_names = {0:'power', 1:'drum', 2:'fan', 3:'popup', 4:'end_alert', 5:'yellow', 6:'first_crack'}
    for events in groups:
        if not isinstance(events, list) or not events:
            raise ValueError('Invalid RoasTime condition group')
        conditions, actions = [], []
        for index, event in enumerate(events):
            if not isinstance(event, dict) or type(event.get('trigger')) is not int or event['trigger'] not in (0, 1, 3):
                raise ValueError('RoasTime import supports IBTS, bean probe and elapsed time; unknown triggers are rejected')
            sensor = {0:'ibts', 1:'bt', 3:'time'}[event['trigger']]
            condition = event.get('condition', 0)
            if type(condition) is not int or condition not in (0, 1):
                raise ValueError('Unknown RoasTime comparison')
            value = numeric(event.get('value'), 0, 3600, 'Trigger value')
            if sensor == 'time':
                # RoasTime forces its second time condition to at least five seconds.
                value = max(5, value) if index == 1 else value
            else:
                value = celsius(value)
            conditions.append(dict(sensor=sensor, op='>=' if sensor == 'time' or condition == 0 else '<=', value=value))
            if not isinstance(event.get('actions', []), list):
                raise ValueError('Invalid RoasTime actions')
            for action in event.get('actions', []):
                if not isinstance(action, dict) or type(action.get('action')) is not int or action['action'] not in action_names:
                    raise ValueError('Unknown RoasTime action; import stopped without saving')
                name = action_names[action['action']]
                value = action.get('value')
                if name == 'end_alert':
                    value = value or 'Recipe end target reached. Check the beans and start cooling when ready.'
                elif name in ('yellow', 'first_crack'):
                    value = 1
                actions.append(dict(control=name, value=value))
        steps.append(dict(conditions=conditions, actions=actions))
    name = raw.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 300:
        raise ValueError('Recipe needs a name')
    preheat = celsius(raw.get('preheatTemp'))
    numeric(preheat, 100, 310, 'Preheat')
    if abs(preheat - round(preheat)) > .01:
        raise ValueError('Preheat must resolve to whole degrees Celsius')
    weight = numeric(raw.get('weight'), 200, 1000, 'Standard R2 batch weight')
    return dict(name=name.strip(), style='RoasTime · R2', preheat=round(preheat), batch_g=weight,
                notes='Imported from RoasTime. Condition groups and action order preserved.',
                steps=validate_steps(steps), import_source=copy.deepcopy(raw))


def replay_recipe(roast, preheat):
    """Replay observed P/F/D by machine time, never by temperature tracking."""
    if roast.get('mode') != 'hardware' or roast.get('status') != 'complete':
        raise ValueError('Replay requires a completed hardware roast')
    numeric(preheat, 100, 310, 'Preheat', whole=True)
    samples = roast.get('samples', [])
    if not samples or samples[0].get('elapsed', 3600) > 5:
        raise ValueError('The beginning of this roast was not recorded')
    by_time = {}
    for sample in samples:
        if sample.get('gap_before'):
            raise ValueError('This roast has a telemetry gap; create and review a recipe manually')
        elapsed = numeric(sample.get('elapsed'), 0, 3600, 'Recorded time')
        values = {k:numeric(sample.get(k), *bounds, 'Recorded setting', whole=True) for k,bounds in LIMITS.items()}
        by_time[elapsed] = values
    steps, previous = [], None
    for elapsed, values in sorted(by_time.items()):
        actions = [dict(control=k,value=v) for k,v in values.items() if previous is None or previous[k] != v]
        if actions:
            steps.append(dict(conditions=[dict(sensor='time',op='>=',value=0 if previous is None else elapsed)], actions=actions))
        previous = values
    steps.append(dict(conditions=[dict(sensor='time',op='>=',value=roast['elapsed'])],
                      actions=[dict(control='end_alert',value='Reference roast ended here. Check the beans before cooling.')]))
    return dict(name='Replay · '+roast['name'],style='Recorded settings · time',preheat=preheat,
                batch_g=roast['green_g'],reference_roast_id=roast['id'],steps=validate_steps(steps),
                notes='Observed settings replayed by elapsed time. Preheat was selected for this replay. The reference curve is visual guidance, not a temperature control target.')
