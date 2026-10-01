"""Bullet R2 USB adapter. Protocol derived from Artisan's AGPL-3.0-or-later
aillio_r2.py (Artisan team, Marko Luther and mikefsq). See THIRD_PARTY.md.
No hardware access occurs until connect() is explicitly requested.
"""
import math
import struct
import threading
import time
from collections import deque

STATES = {0: 'ready', 2: 'preheating', 3: 'stabilizing', 4: 'charge',
          6: 'roasting', 7: 'cooldown', 8: 'cooling', 9: 'shutdown', 11: 'reset'}
LIMITS = {'power': (0, 10), 'fan': (1, 12), 'drum': (1, 9)}


def command_packet(payload):
    # Artisan's device-specific CRC: 16 polynomial shifts per big-endian word.
    data = bytes(payload) + bytes(4)
    crc = 0xffffffff
    for offset in range(0, len(data), 4):
        crc ^= int.from_bytes(data[offset:offset + 4], 'big')
        for _ in range(16):
            crc = ((crc << 1) ^ (0x04c11db7 if crc & 0x80000000 else 0)) & 0xffffffff
    return data[:-4] + crc.to_bytes(4, 'little')


def decode_frame(data):
    if len(data) != 64:
        raise ValueError('Expected a 64-byte R2 frame')
    if data[0] == 0xa0:
        f = lambda n: struct.unpack_from('<f', data, n)[0]
        u = lambda n: struct.unpack_from('<H', data, n)[0]
        result = dict(ibts=f(4), ror=f(8), ambient=f(12), bt=f(16), bt_ror=f(20),
                      energy=f(24), pressure=f(28), fan_rpm=u(32), inlet=u(34)/10,
                      hot_air=u(36)/10, exhaust=u(38)/10, humidity=u(42)/10,
                      machine_elapsed=data[46]*60+data[48], power=data[50],
                      fan=data[51], drum=data[53], machine_state=STATES.get(data[59], 'unknown'),
                      machine_state_code=data[59], crack_mark=data[47])
        if any(not math.isfinite(v) for v in result.values() if isinstance(v, float)):
            raise ValueError('Non-finite sensor value')
        if not (-30 <= result['ibts'] <= 400 and -30 <= result['bt'] <= 400):
            raise ValueError('Temperature outside plausible sensor range')
        if not (0 <= result['power'] <= 10 and 0 <= result['fan'] <= 12 and 0 <= result['drum'] <= 9):
            raise ValueError('Unsupported control readings; verify standard R2 model and firmware')
        return result
    if data[0] == 0xa1:
        u = lambda n: struct.unpack_from('<H', data, n)[0]
        return dict(error_count=data[4], critical=u(52),
                    errors=[dict(category=data[n], type=data[n+1], info=data[n+2], value=data[n+3]) for n in (8,12)],
                    coil_fan_rpm=u(34), coil_fan2_rpm=u(36), induction_blower_rpm=u(42),
                    ibts_fan_rpm=u(46), drum_rpm=u(48), buttons=u(58))
    if data[0] == 0xa2:
        u = lambda n: struct.unpack_from('<H', data, n)[0]
        return dict(watts=u(22)/10, voltage=u(28)/10, power_setpoint_watts=u(4),
                    line_frequency=u(6)/100, igbt_error=u(10), igbt_temp=u(12)/10,
                    chamber_temp=u(14)/10, status_register=u(18), status_error=u(20), current=u(30)/1000)
    return {}


class Bullet:
    def __init__(self):
        self.lock = threading.RLock()
        self.device = None
        self.thread = None
        self.stop = threading.Event()
        self.latest = {}
        self.updated = 0
        self.error = ''
        self.armed_until = 0
        self.pending = None
        self.telemetry_received = threading.Event()
        self.trace = deque(maxlen=600)

    def connect(self):
        if self.device is not None:
            return
        try:
            import usb.util
            import libusb_package
        except ImportError as exc:
            raise ValueError('USB libraries missing. Run Start Roasting.command on macOS or Install USB support.cmd on Windows.') from exc
        dev = libusb_package.find(idVendor=0x0483, idProduct=0xa4cd)
        if dev is None:
            raise ValueError('Bullet R2 not found. Connect USB, select USB for RoasTime on the R2, and close RoasTime/Artisan. See Connection help.')
        try:
            cfg = dev.get_active_configuration()
            intf = cfg[(1, 0)]
            usb.util.claim_interface(dev, 1)
            self.ep_in = next(ep for ep in intf if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN)
            self.ep_out = next(ep for ep in intf if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        except Exception:
            usb.util.dispose_resources(dev)
            raise
        self.device = dev
        self.latest = {}
        self.updated = 0
        self.error = ''
        self.pending = None
        self.stop.clear()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        while not self.stop.is_set():
            try:
                frame = bytes(self.ep_in.read(64, timeout=500))
                self._accept_frame(frame)
            except Exception as exc:
                if time.monotonic() - self.updated > 3:
                    with self.lock:
                        self.armed_until = 0
                        self.error = 'USB telemetry interrupted: ' + str(exc)

    def _accept_frame(self, frame):
        values = decode_frame(frame)
        with self.lock:
            self.trace.append(dict(time=time.time(), direction='in', packet=bytes(frame).hex(), decoded=values))
            self.latest.update(values)
            if 'ibts' in values:
                self.updated = time.monotonic()
                self.telemetry_received.set()
                if self.pending:
                    name, target, deadline = self.pending
                    if values.get(name) == target or (name == 'machine_state' and target == 'cooldown' and values.get(name) == 'cooling'):
                        self.pending = None
                    elif time.monotonic() > deadline:
                        self.error = 'Command was not confirmed by telemetry. Controls disarmed; check the physical panel.'
                        self.armed_until = 0
                        self.pending = None

    def status(self):
        with self.lock:
            age = time.monotonic() - self.updated
            fresh = self.device is not None and age < 3
            if self.pending and time.monotonic() > self.pending[2]:
                self.error = 'Command was not confirmed by telemetry. Controls disarmed; check the physical panel.'
                self.armed_until = 0
                self.pending = None
            if not fresh:
                self.armed_until = 0
                self.pending = None
            if self.latest.get('critical') or self.latest.get('error_count'):
                self.armed_until = 0
                self.pending = None
                self.error = 'Machine reports an error; resolve it on the physical panel.'
            return dict(connected=self.device is not None, fresh=fresh,
                        age=round(age, 1) if self.updated else None,
                        armed=fresh and time.monotonic() < self.armed_until,
                        error=self.error, pending=bool(self.pending),
                        pending_control=bool(self.pending and self.pending[0] in LIMITS), telemetry=dict(self.latest))

    def diagnostics(self):
        with self.lock:
            return dict(protocol='Artisan-derived R2 USB, incremental confirmed writes',
                        hardware_validated=False, status=self.status(), trace=list(self.trace),
                        unavailable=['absolute setpoints', 'cooling tray speed', 'back-to-back command',
                                     'hardware crack markers', 'machine buzzer and blink'])

    def arm(self, enabled):
        with self.lock:
            if enabled and not self.status()['fresh']:
                raise ValueError('Wait for fresh R2 telemetry before enabling controls')
            if enabled and (self.latest.get('critical') or self.latest.get('error_count')):
                raise ValueError('Resolve the machine error on the physical panel first')
            self.error = ''
            self.armed_until = time.monotonic() + 1800 if enabled else 0

    def command(self, name, value=None, expected_state=None):
        with self.lock:
            if not self.status()['armed']:
                raise ValueError('Controls are disarmed or telemetry is stale')
            state = self.latest.get('machine_state')
            if expected_state is not None and state != expected_state:
                raise ValueError('The R2 changed phase. Review the machine before continuing.')
            # Cooling takes priority over an in-flight P/F/D change, never over another PRS.
            cooling_priority = name == 'prs' and state == 'roasting' and self.pending and self.pending[0] in LIMITS
            if self.pending and not cooling_priority:
                raise ValueError('Waiting for the previous control change to be confirmed')
            if self.latest.get('critical') or self.latest.get('error_count'):
                self.armed_until = 0
                raise ValueError('Machine reports an error; use the physical panel')
            if name in LIMITS:
                lo, hi = LIMITS[name]
                if type(value) is not int or not lo <= value <= hi:
                    raise ValueError(f'{name} must be an integer from {lo} to {hi}')
                if state != 'roasting':
                    raise ValueError('P/F/D control is available in roasting mode; use the panel in other modes')
                old = self.latest[name]
                if abs(value-old) != 1:
                    raise ValueError('Hardware controls move one confirmed step at a time')
                code = {'power': 0x34, 'fan': 0x31, 'drum': 0x32}[name]
                payload = [code, 1 if value > old else 2, 0xaa, 0xaa]
                self.pending = (name, value, time.monotonic()+3)
            elif name == 'preheat':
                if state not in ('ready', 'preheating', 'stabilizing', 'charge'):
                    raise ValueError('Preheat target is only available before roasting')
                if type(value) is not int or not 100 <= value <= 310:
                    raise ValueError('Preheat target must be 100–310 °C')
                payload = [0x35, 0, value >> 8, value & 255]
            elif name == 'prs':
                targets = {'ready': 'preheating', 'preheating': 'charge', 'stabilizing': 'charge',
                           'charge': 'roasting', 'roasting': 'cooldown', 'cooldown': 'shutdown', 'cooling': 'shutdown', 'shutdown': 'ready'}
                if state not in targets:
                    raise ValueError('Use PRS on the physical panel for this machine state')
                payload = [0x30, 1, 0, 0]
                self.pending = ('machine_state', targets[state], time.monotonic()+3)
            else:
                raise ValueError('Unsupported machine command')
            try:
                packet = command_packet(payload)
                self.trace.append(dict(time=time.time(), direction='out', packet=packet.hex(),
                                       command=name, target=value, state=state, result='requested'))
                self.ep_out.write(packet, timeout=500)
            except Exception:
                self.trace.append(dict(time=time.time(), direction='error', command=name, target=value))
                self.pending = None
                self.armed_until = 0
                raise

    def disconnect(self):
        self.armed_until = 0
        self.stop.set()
        if self.thread:
            self.thread.join(2)
        if self.device:
            import usb.util
            usb.util.release_interface(self.device, 1)
            usb.util.dispose_resources(self.device)
        self.device = None
