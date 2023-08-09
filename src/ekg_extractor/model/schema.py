from typing import Dict

from neo4j.time import DateTime


class Timestamp:
    def __init__(self, year: int, month: int, day: int, hour: int, mins: int, sec: int):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.mins = mins
        self.sec = sec

    def __str__(self):
        return '{}-{}-{} {}:{}:{}'.format(self.year, str(self.month).zfill(2), str(self.day).zfill(2),
                                          str(self.hour).zfill(2), str(self.mins).zfill(2), str(self.sec).zfill(2))

    @staticmethod
    def parse_ts(dt: DateTime):
        return Timestamp(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


class Event:
    def __init__(self, act: str, t: float, date: Timestamp = None, extra_attr: Dict[str, str] = {}):
        self.activity = act
        self.timestamp = t
        self.date = date
        self.extra_attr = extra_attr

    @staticmethod
    def parse_evt(r, p: Dict[str, str]):
        attr = r['e']
        IGNORE_KEYS = [p['act'], p['timestamp']]
        if 'date' in p:
            datetime = Timestamp.parse_ts(attr[p['date']])
            IGNORE_KEYS.append(p['date'])
        else:
            datetime = None
        extra_attr: Dict[str, str] = {}
        for key in attr:
            if key not in IGNORE_KEYS:
                extra_attr[key] = attr[key]
        return Event(attr[p['act']], attr[p['timestamp']], datetime, extra_attr)

    def __str__(self):
        return '{}, {}, {}, {}'.format(self.activity, self.timestamp, self.date, self.extra_attr)


class Entity:
    def __init__(self, _id, extra_attr: Dict[str, str]):
        self._id = _id
        self.extra_attr = extra_attr

    @staticmethod
    def parse_ent(r, p: Dict[str, str], key: str = 'e'):
        attr = r[key]
        new_entity = Entity(attr[p['id']], {})
        for k in attr:
            if k not in [p['id']]:
                new_entity.extra_attr[k] = attr[k]
        return new_entity

    def __str__(self):
        return '{}, {}'.format(self._id, self.extra_attr)

    def __eq__(self, other):
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)


class Activity:
    def __init__(self, act: str, extra_attr: Dict[str, str]):
        self.act = act
        self.extra_attr = extra_attr

    @staticmethod
    def parse_act(r, p: Dict[str, str]):
        attr = r['s']
        new_activity: Activity = Activity('', {})
        for key in p['id']:
            if key in attr:
                new_activity.act = attr[key]
                break
        for k in attr:
            if k not in [p['id']]:
                new_activity.extra_attr[k] = attr[k]
        return new_activity

    def __str__(self):
        return '{}, {}'.format(self.act, self.extra_attr)
