import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] > 5:
                raise ValueError('This database was created by a newer version of Roast Studio')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS lots (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, origin TEXT NOT NULL,
                process TEXT NOT NULL, supplier TEXT NOT NULL, received TEXT NOT NULL,
                stock_g REAL NOT NULL CHECK(stock_g>=0), cost_per_kg REAL NOT NULL CHECK(cost_per_kg>=0),
                notes TEXT NOT NULL DEFAULT '', archived INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, style TEXT NOT NULL,
                preheat INTEGER NOT NULL, batch_g REAL NOT NULL, notes TEXT NOT NULL,
                steps TEXT NOT NULL, reference_roast_id INTEGER);
            CREATE TABLE IF NOT EXISTS roasts (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, lot_id INTEGER REFERENCES lots(id),
                profile_id INTEGER REFERENCES profiles(id), mode TEXT NOT NULL,
                status TEXT NOT NULL, started TEXT NOT NULL, ended TEXT,
                green_g REAL NOT NULL, roasted_g REAL, cost_per_kg REAL NOT NULL,
                elapsed REAL NOT NULL DEFAULT 0, seasoning INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '', score REAL, tasting TEXT NOT NULL DEFAULT '',
                rest_days INTEGER NOT NULL DEFAULT 5);
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY, roast_id INTEGER NOT NULL REFERENCES roasts(id),
                elapsed REAL NOT NULL, data TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS sample_roast_time ON samples(roast_id,elapsed);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, roast_id INTEGER NOT NULL REFERENCES roasts(id),
                elapsed REAL NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY, lot_id INTEGER NOT NULL REFERENCES lots(id),
                roast_id INTEGER REFERENCES roasts(id), amount_g REAL NOT NULL,
                reason TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, lot_id INTEGER NOT NULL REFERENCES lots(id),
                profile_id INTEGER REFERENCES profiles(id), batch_g REAL NOT NULL,
                scheduled TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned',
                roast_id INTEGER REFERENCES roasts(id));
            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY, roast_id INTEGER NOT NULL REFERENCES roasts(id),
                count INTEGER NOT NULL, grams_each REAL NOT NULL, price_each REAL NOT NULL,
                created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS maintenance (
                id INTEGER PRIMARY KEY, task TEXT NOT NULL, notes TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ai_jobs (
                id INTEGER PRIMARY KEY, status TEXT NOT NULL, created TEXT NOT NULL, ended TEXT,
                model TEXT NOT NULL, context TEXT NOT NULL, result TEXT, error TEXT NOT NULL DEFAULT '',
                profile_id INTEGER REFERENCES profiles(id));
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, context TEXT NOT NULL,
                created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                role TEXT NOT NULL, content TEXT NOT NULL, created TEXT NOT NULL,
                job_id INTEGER REFERENCES ai_jobs(id));
            CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
            ''')
            # Additive migration preserves v1 inventory, telemetry and recipes.
            for table, column in (('lots', 'details'), ('profiles', 'guidance')):
                columns = {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}
                if column not in columns:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT NOT NULL DEFAULT '{{}}'")
            if 'lot_id' not in {row['name'] for row in db.execute('PRAGMA table_info(ai_jobs)')}:
                db.execute('ALTER TABLE ai_jobs ADD COLUMN lot_id INTEGER REFERENCES lots(id)')
            if db.execute('PRAGMA user_version').fetchone()[0] < 5:
                # Preserve the old hidden IBTS delay on existing recipes as explicit
                # metadata. Imported/new rules use their own conditions instead.
                def preserve_legacy(steps):
                    for step in steps:
                        if step.get('trigger') == 'ibts' and 'min_time' not in step:
                            step.update(min_time=65, after_turn=True)
                    return steps
                for row in db.execute('SELECT id,steps FROM profiles').fetchall():
                    db.execute('UPDATE profiles SET steps=? WHERE id=?', (json.dumps(preserve_legacy(json.loads(row['steps']))), row['id']))
                for row in db.execute('SELECT id,data FROM workspace').fetchall():
                    workspace = json.loads(row['data'])
                    if 'steps' in workspace:
                        preserve_legacy(workspace['steps'])
                        db.execute('UPDATE workspace SET data=? WHERE id=?', (json.dumps(workspace), row['id']))
            db.execute('PRAGMA user_version=5')
            db.execute("UPDATE ai_jobs SET status='failed',error='The app stopped before Astra finished. Generate again.',ended=? WHERE status='running'", (now(),))
            defaults = dict(studio='Roast Studio', units='F', astra_expertise='beginner', bag_g=340.194, sale_price=17,
                            packaging=0.75, energy=0.10, fee_percent=3, loss_percent=15,
                            labor_per_bag=0, fixed_per_bag=0, machine_seasoned=False)
            for key, value in defaults.items():
                db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (key, json.dumps(value)))
            # No invented stock or roast history. A suggested profile is explicitly a guide.
            if not db.execute('SELECT 1 FROM profiles LIMIT 1').fetchone():
                db.execute('INSERT INTO profiles(name,style,preheat,batch_g,notes,steps) VALUES (?,?,?,?,?,?)',
                           ('Guatemala · first exploration', 'City+ / balanced', 230, 500,
                            'Starting worksheet, not a validated roast recipe. Adjust from observed color, aroma, first crack and your cupping. Preheat is an editable starting assumption.',
                            json.dumps([{'trigger': 'time', 'at': 0, 'control': 'power', 'value': 7},
                                        {'trigger': 'time', 'at': 0, 'control': 'fan', 'value': 3},
                                        {'trigger': 'time', 'at': 0, 'control': 'drum', 'value': 9}])))
            db.execute("UPDATE roasts SET status='interrupted', ended=? WHERE status IN ('roasting','cooling')", (now(),))

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            with db:
                yield db
        finally:
            db.close()

    def all(self, sql, params=()):
        with self.db() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def one(self, sql, params=()):
        result = self.all(sql, params)
        if not result:
            raise ValueError('Record not found')
        return result[0]

    def settings(self):
        return {r['key']: json.loads(r['value']) for r in self.all('SELECT * FROM settings')}

    def roast(self, rid):
        r = self.one('SELECT r.*,l.name AS lot_name FROM roasts r LEFT JOIN lots l ON l.id=r.lot_id WHERE r.id=?', (rid,))
        r['samples'] = [dict(json.loads(s['data']), elapsed=s['elapsed']) for s in self.all('SELECT * FROM samples WHERE roast_id=? ORDER BY elapsed', (rid,))]
        r['events'] = self.all('SELECT * FROM events WHERE roast_id=? ORDER BY elapsed,id', (rid,))
        return r

    def backup(self, target):
        with self.db() as source:
            dest = sqlite3.connect(target)
            try:
                source.backup(dest)
            finally:
                dest.close()
