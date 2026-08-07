import math
import time

from config import COLS, ROWS, p_clear, p_drawPixel


NEW_MOON_EPOCH = 947182440  # 2000-01-06 18:14 UTC
SYNODIC_MONTH_SECONDS = 2551442.9


def moon_phase(timestamp=None):
    """Return the approximate lunar phase as a value from 0 to 1."""
    timestamp = time.time() if timestamp is None else timestamp
    return ((timestamp - NEW_MOON_EPOCH) / SYNODIC_MONTH_SECONDS) % 1.0


def weather_scene_for_condition(condition_id, icon=""):
    """Map an OpenWeather condition ID and icon to a matrix scene."""
    condition_id = int(condition_id or 0)
    is_night = str(icon).endswith("n")
    if 200 <= condition_id < 300:
        return "thunderstorm"
    if 300 <= condition_id < 600:
        return "rain"
    if 600 <= condition_id < 700:
        return "snow"
    if 700 <= condition_id < 800:
        return "fog"
    if condition_id == 800:
        return "clear_night" if is_night else "clear_day"
    if condition_id in (801, 802):
        return "partly_cloudy_night" if is_night else "partly_cloudy_day"
    return "clouds"


def _pixel(x, y, value=1):
    if 0 <= x < COLS and 0 <= y < ROWS:
        p_drawPixel(x, y, value)


def _draw_sun(t, cx=7.5, cy=7.5):
    for step in range(32):
        angle = math.tau * step / 32
        _pixel(round(cx + math.cos(angle) * 3), round(cy + math.sin(angle) * 3))

    ray_tip = 5 + (int(t * 4) % 3)
    rotation = t * 0.65
    for ray in range(8):
        angle = rotation + (math.tau * ray / 8)
        for radius in range(5, ray_tip + 1):
            _pixel(round(cx + math.cos(angle) * radius), round(cy + math.sin(angle) * radius))


def _draw_moon(t, timestamp=None, cx=7.5, cy=7.5):
    phase = moon_phase(timestamp)
    illuminated = (1.0 - math.cos(math.tau * phase)) / 2.0
    waxing = phase < 0.5
    radius = 5.4

    for y in range(2, 14):
        dy = y - cy
        if abs(dy) > radius:
            continue
        half_width = math.sqrt((radius * radius) - (dy * dy))
        left = math.ceil(cx - half_width)
        right = math.floor(cx + half_width)
        width = right - left + 1
        lit_width = round(width * illuminated)
        lit_start = right - lit_width + 1 if waxing else left
        for x in range(lit_start, lit_start + lit_width):
            _pixel(x, y)

    stars = ((1, 2), (14, 3), (2, 13), (13, 12))
    twinkle_phase = int(t * 3)
    for index, (x, y) in enumerate(stars):
        if (index + twinkle_phase) % 3:
            _pixel(x, y)


CLOUD_ROWS = (
    "...###...",
    ".#######.",
    "#########",
    ".#######.",
    "..#####..",
)


def _draw_cloud(x_origin, y_origin, erase_background=False):
    if erase_background:
        for y in range(y_origin, y_origin + len(CLOUD_ROWS)):
            for x in range(x_origin, x_origin + len(CLOUD_ROWS[0])):
                _pixel(x, y, 0)
    for dy, row in enumerate(CLOUD_ROWS):
        for dx, value in enumerate(row):
            if value == "#":
                _pixel(x_origin + dx, y_origin + dy)


def _draw_drifting_cloud(t, y=6, speed=2.0, erase_background=False):
    x = int(t * speed) % COLS
    for origin in (x, x - COLS):
        _draw_cloud(origin, y, erase_background=erase_background)


def _draw_precipitation(t, snow=False):
    speed = 3 if snow else 7
    phase = int(t * speed)
    for index, x in enumerate((2, 5, 8, 11, 14)):
        y = 9 + ((phase + index * 2) % 7)
        _pixel(x, y)
        if snow and (phase + index) % 2 == 0:
            _pixel(x - 1, y)
            _pixel(x + 1, y)


def _draw_fog(t):
    for index, y in enumerate((4, 7, 10, 13)):
        offset = int(t * (1 + index * 0.25)) % 6
        for x in range(-6, COLS + 6, 6):
            for segment in range(4):
                _pixel(x + offset + segment, y)


def render_weather_frame(snapshot, t, timestamp=None):
    """Render one weather frame and return the selected scene name."""
    condition_id = snapshot.get("condition_id", 0) if snapshot else 0
    icon = snapshot.get("icon", "") if snapshot else ""
    scene = weather_scene_for_condition(condition_id, icon)
    p_clear()

    if scene == "clear_day":
        _draw_sun(t)
    elif scene == "clear_night":
        _draw_moon(t, timestamp=timestamp)
    elif scene in ("partly_cloudy_day", "partly_cloudy_night"):
        if scene.endswith("day"):
            _draw_sun(t * 0.35, cx=4.5, cy=4.5)
        else:
            _draw_moon(t, timestamp=timestamp, cx=4.5, cy=4.5)
        _draw_drifting_cloud(t, y=7, speed=1.5, erase_background=True)
    elif scene == "rain":
        _draw_cloud(3, 2)
        _draw_precipitation(t)
    elif scene == "thunderstorm":
        _draw_cloud(3, 2)
        if int(t * 3) % 3 != 2:
            for x, y in ((9, 8), (7, 11), (9, 11), (6, 15)):
                _pixel(x, y)
    elif scene == "snow":
        _draw_cloud(3, 2)
        _draw_precipitation(t, snow=True)
    elif scene == "fog":
        _draw_fog(t)
    else:
        _draw_drifting_cloud(t, y=5, speed=1.2)
        _draw_drifting_cloud(t + 5, y=9, speed=0.8)

    return scene
