#!/usr/bin/env python3
"""Silent bottom-screen trackpad."""
from __future__ import annotations

import fcntl
import glob
import os
import select
import signal
import struct
import time


EVENT = struct.Struct("llHHi")
SETUP = struct.Struct("HHHH80sI")

EV_SYN, EV_KEY, EV_REL, EV_ABS = 0x00, 0x01, 0x02, 0x03
SYN_REPORT, SYN_DROPPED = 0, 3
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 0x2F, 0x35, 0x36, 0x39
REL_X, REL_Y, REL_HWHEEL, REL_WHEEL, REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES = 0, 1, 6, 8, 11, 12
BTN_LEFT, BTN_RIGHT = 0x110, 0x111

UINPUT = "/dev/uinput"
SCREEN_WIDTH, SCREEN_HEIGHT = 1240, 1080
TAP_TIME, TAP_DISTANCE, SCROLL_UNITS_PER_PIXEL = 0.25, 12.0, 12.0

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_RELBIT = 0x40045566
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_DEV_SETUP = 0x405C5503


def raw_to_screen(raw_x: int, raw_y: int) -> tuple[float, float]:
    return float(raw_y), float(SCREEN_HEIGHT - 1 - raw_x)


class Mouse:
    def __init__(self) -> None:
        self.fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            for code in (BTN_LEFT, BTN_RIGHT):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
            for code in (REL_X, REL_Y, REL_WHEEL, REL_HWHEEL, REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES):
                fcntl.ioctl(self.fd, UI_SET_RELBIT, code)
            setup = SETUP.pack(0x06, 0x1234, 0x5678, 1, b"Ratatoskr Trackpad", 0)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except BaseException:
            os.close(self.fd)
            raise
        self.last_motion = 0.0
        self.scroll_x = 0.0
        self.scroll_y = 0.0
        self.wheel_x = 0.0
        self.wheel_y = 0.0

    def _write(self, events: list[tuple[int, int, int]]) -> None:
        now = time.time()
        sec, usec = int(now), int((now % 1) * 1_000_000)
        packet = b"".join(EVENT.pack(sec, usec, kind, code, value) for kind, code, value in events)
        packet += EVENT.pack(sec, usec, EV_SYN, SYN_REPORT, 0)
        os.write(self.fd, packet)

    def move(self, dx: int, dy: int) -> None:
        if dx or dy:
            self._write([(EV_REL, REL_X, dx), (EV_REL, REL_Y, dy)])
            self.last_motion = time.monotonic()

    def _wake_pointer(self) -> None:
        if time.monotonic() - self.last_motion > 2.0:
            self.move(1, 0)
            self.move(-1, 0)

    def click(self, button: int) -> None:
        self._wake_pointer()
        self._write([(EV_KEY, button, 1)])
        time.sleep(0.02)
        self._write([(EV_KEY, button, 0)])

    def scroll(self, dx: float, dy: float) -> None:
        self._wake_pointer()
        self.scroll_x += dx * SCROLL_UNITS_PER_PIXEL
        self.scroll_y += dy * SCROLL_UNITS_PER_PIXEL
        hi_x, hi_y = int(self.scroll_x), int(self.scroll_y)
        self.scroll_x -= hi_x
        self.scroll_y -= hi_y
        if not hi_x and not hi_y:
            return
        events = []
        if hi_x:
            events.append((EV_REL, REL_HWHEEL_HI_RES, hi_x))
            self.wheel_x += hi_x
            notches = int(self.wheel_x / 120)
            self.wheel_x -= notches * 120
            if notches:
                events.append((EV_REL, REL_HWHEEL, notches))
        if hi_y:
            events.append((EV_REL, REL_WHEEL_HI_RES, hi_y))
            self.wheel_y += hi_y
            notches = int(self.wheel_y / 120)
            self.wheel_y -= notches * 120
            if notches:
                events.append((EV_REL, REL_WHEEL, notches))
        self._write(events)

    def close(self) -> None:
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)


class Touchpad:
    def __init__(self, mouse: Mouse) -> None:
        self.mouse = mouse
        self.pad_points: dict[int, tuple[float, float]] = {}
        self.gesture_start = 0.0
        self.gesture_max_fingers = 0
        self.travel = 0.0
        self.pointer_active = False
        self.pointer_rest = [0.0, 0.0]
        self.last_centroid = (0.0, 0.0)
        self.last_seen = time.monotonic()

    def reset(self) -> None:
        self._cancel_gesture(time.monotonic())

    def _cancel_gesture(self, now: float) -> None:
        self.pad_points.clear()
        self.gesture_start = now
        self.gesture_max_fingers = 0
        self.pointer_active = False
        self.travel = 0.0

    def update(self, contacts: dict[int, tuple[float, float]], now: float) -> None:
        self.last_seen = now
        previous = dict(self.pad_points)
        current = dict(contacts)

        if not current:
            if previous:
                self._finish_gesture(now)
            self.pad_points = {}
            return

        if not previous:
            self.gesture_start = now
            self.gesture_max_fingers = 0
            self.travel = 0.0
            self.pointer_active = False
            self.pointer_rest = [0.0, 0.0]

        count = len(current)
        self.gesture_max_fingers = max(self.gesture_max_fingers, count)
        if current.keys() != previous.keys():
            self.last_centroid = self._centroid(current)
            self.pad_points = current
            return

        if count == 1:
            tid = next(iter(current))
            old_x, old_y = previous[tid]
            x, y = current[tid]
            dx, dy = x - old_x, y - old_y
            self.travel += (dx * dx + dy * dy) ** 0.5
            if not self.pointer_active:
                if self.travel < TAP_DISTANCE and now - self.gesture_start < TAP_TIME:
                    self.pad_points = current
                    return
                self.pointer_active = True
            gain = 1
            self.pointer_rest[0] += dx * gain
            self.pointer_rest[1] += dy * gain
            move_x, move_y = int(self.pointer_rest[0]), int(self.pointer_rest[1])
            self.pointer_rest[0] -= move_x
            self.pointer_rest[1] -= move_y
            self.mouse.move(move_x, move_y)
        elif count == 2:
            for tid, (x, y) in current.items():
                old_x, old_y = previous[tid]
                self.travel += ((x - old_x) ** 2 + (y - old_y) ** 2) ** 0.5
            centroid = self._centroid(current)
            dx = centroid[0] - self.last_centroid[0]
            dy = centroid[1] - self.last_centroid[1]
            self.mouse.scroll(dx, -dy)
            self.last_centroid = centroid
        self.pad_points = current

    def _finish_gesture(self, now: float) -> None:
        tap_distance = TAP_DISTANCE * max(1, self.gesture_max_fingers)
        is_tap = now - self.gesture_start < TAP_TIME and self.travel < tap_distance
        if is_tap and self.gesture_max_fingers == 1:
            self.mouse.click(BTN_LEFT)
        elif is_tap and self.gesture_max_fingers == 2:
            self.mouse.click(BTN_RIGHT)
        self.gesture_max_fingers = 0
        self.pointer_active = False
        self.travel = 0.0
        self.pointer_rest = [0.0, 0.0]
        self.gesture_start = now

    @staticmethod
    def _centroid(contacts: dict[int, tuple[float, float]]) -> tuple[float, float]:
        return (
            sum(point[0] for point in contacts.values()) / len(contacts),
            sum(point[1] for point in contacts.values()) / len(contacts),
        )

    def expire(self, now: float) -> None:
        if self.owners and now - self.last_seen > 2.0:
            self.reset()


class MultitouchParser:
    def __init__(self) -> None:
        self.tail = b""
        self.slot = 0
        self.tracking: dict[int, int] = {}
        self.raw: dict[int, list[int]] = {}

    def feed(self, data: bytes) -> list[dict[int, tuple[float, float]] | None]:
        data = self.tail + data
        size = len(data) - len(data) % EVENT.size
        self.tail = data[size:]
        frames = []
        for offset in range(0, size, EVENT.size):
            _, _, kind, code, value = EVENT.unpack_from(data, offset)
            if kind == EV_SYN and code == SYN_DROPPED:
                self.tracking.clear()
                self.raw.clear()
                frames.append(None)
            elif kind == EV_ABS:
                if code == ABS_MT_SLOT:
                    self.slot = value
                elif code == ABS_MT_TRACKING_ID:
                    if value < 0:
                        self.tracking.pop(self.slot, None)
                    else:
                        self.tracking[self.slot] = value
                elif code == ABS_MT_POSITION_X:
                    self.raw.setdefault(self.slot, [0, 0])[0] = value
                elif code == ABS_MT_POSITION_Y:
                    self.raw.setdefault(self.slot, [0, 0])[1] = value
            elif kind == EV_SYN and code == SYN_REPORT:
                framthes.append({
                    tid: raw_to_screen(*self.raw.get(slot, (0, 0)))
                    for slot, tid in self.tracking.items()
                })
        return frames


def find_touchscreen() -> str:
    for node in sorted(glob.glob("/dev/input/event*")):
        name_path = f"/sys/class/input/{os.path.basename(node)}/device/name"
        try:
            with open(name_path, encoding="utf-8") as name_file:
                name = name_file.read().strip().lower()
            if "bottom" in name and "touchscreen" in name:
                return node
        except OSError:
            continue
    raise FileNotFoundError("bottom touchscreen not found")


def resync(parser: MultitouchParser, fd: int) -> None:
    ioc_read = 2

    def eviocgabs(code: int) -> int:
        return (ioc_read << 30) | (24 << 16) | (ord("E") << 8) | (0x40 + code)

    def eviocgmtslots(length: int) -> int:
        return (ioc_read << 30) | (length << 16) | (ord("E") << 8) | 0x0A

    absinfo = bytearray(24)
    fcntl.ioctl(fd, eviocgabs(ABS_MT_SLOT), absinfo)
    slots = struct.unpack("6i", absinfo)[2] + 1
    values = {}
    for code in (ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y):
        buffer = bytearray(struct.pack("I", code) + bytes(4 * slots))
        fcntl.ioctl(fd, eviocgmtslots(len(buffer)), buffer)
        values[code] = struct.unpack(f"{slots}i", buffer[4:])
    parser.tracking.clear()
    parser.raw.clear()
    for slot in range(slots):
        tid = values[ABS_MT_TRACKING_ID][slot]
        if tid >= 0:
            parser.tracking[slot] = tid
            parser.raw[slot] = [values[ABS_MT_POSITION_X][slot], values[ABS_MT_POSITION_Y][slot]]


def run() -> None:
    touch_fd = os.open(find_touchscreen(), os.O_RDONLY | os.O_NONBLOCK)
    mouse = None
    try:
        evio_grab = (1 << 30) | (struct.calcsize("i") << 16) | (ord("E") << 8) | 0x90
        fcntl.ioctl(touch_fd, evio_grab, 1)
        mouse = Mouse()
        touchpad = Touchpad(mouse)
        parser = MultitouchParser()
        stopped = False

        def stop(*_) -> None:
            nonlocal stopped
            stopped = True

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        while not stopped:
            readable, _, _ = select.select([touch_fd], [], [], 0.2)
            if not readable:
                touchpad.expire(time.monotonic())
                continue
            data = os.read(touch_fd, EVENT.size * 256)
            now = time.monotonic()
            for contacts in parser.feed(data):
                if contacts is None:
                    touchpad.reset()
                    resync(parser, touch_fd)
                    contacts = {
                        tid: raw_to_screen(*parser.raw[slot])
                        for slot, tid in parser.tracking.items()
                    }
                touchpad.update(contacts, now)
    finally:
        if mouse is not None:
            mouse.close()
        try:
            evio_grab = (1 << 30) | (struct.calcsize("i") << 16) | (ord("E") << 8) | 0x90
            fcntl.ioctl(touch_fd, evio_grab, 0)
        finally:
            os.close(touch_fd)


if __name__ == "__main__":
    run()
