import math
import random
import time
import config
from config import p_clear, p_scan, p_drawPixel, display_lock, ROWS, COLS


def _for_each_pixel(func):
    for y in range(ROWS):
        for x in range(COLS):
            func(x, y)


def anim_sparkle(t):
    """Random sparkles twinkling across the panel."""
    with display_lock:
        for i in range(256):
            config.p_buf[i] = 1 if random.random() < 0.06 else 0
    p_scan()


def anim_wave(t):
    """Sine wave ribbon sweeping across."""
    p_clear()
    period = 12.0
    amplitude = 7.0
    offset = int((t * 6) % COLS)
    for x in range(COLS):
        y = int((ROWS / 2) + math.sin((x + offset) / period) * (amplitude / 2))
        if 0 <= y < ROWS:
            p_drawPixel(x, y, 1)
            if y + 1 < ROWS:
                p_drawPixel(x, y + 1, 1)
    p_scan()


def anim_swirl(t):
    """Rotating swirl field based on atan2."""
    cx, cy = (COLS - 1) / 2.0, (ROWS - 1) / 2.0
    p_clear()
    for y in range(ROWS):
        for x in range(COLS):
            dx, dy = x - cx, y - cy
            a = math.atan2(dy, dx)
            v = math.sin(4 * a + t * 2.0)
            if v > 0.6:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_plasma(t):
    """Classic plasma interference pattern."""
    p_clear()
    for y in range(ROWS):
        for x in range(COLS):
            v = 0.5 + 0.5 * math.sin(x * 0.5 + t) * math.cos(y * 0.5 - t)
            if v > 0.65:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_box_marquee(t):
    """Marching box border that chases around the edges."""
    p_clear()
    phase = int((t * 12) % (COLS * 2 + ROWS * 2))
    # Draw border
    for x in range(COLS):
        p_drawPixel(x, 0, 1)
        p_drawPixel(x, ROWS - 1, 1)
    for y in range(ROWS):
        p_drawPixel(0, y, 1)
        p_drawPixel(COLS - 1, y, 1)
    # Turn off a moving gap to create marquee effect
    perimeter = []
    for x in range(COLS):
        perimeter.append((x, 0))
    for y in range(1, ROWS):
        perimeter.append((COLS - 1, y))
    for x in range(COLS - 2, -1, -1):
        perimeter.append((x, ROWS - 1))
    for y in range(ROWS - 2, 0, -1):
        perimeter.append((0, y))
    gap_len = 4
    for i in range(gap_len):
        px, py = perimeter[(phase + i) % len(perimeter)]
        p_drawPixel(px, py, 0)
    p_scan()


def anim_pingpong(t):
    """Multiple dots bouncing around with simple physics."""
    # Seed particles once and store in module state
    if not hasattr(anim_pingpong, "particles"):
        anim_pingpong.particles = [
            {"x": random.uniform(0, COLS - 1), "y": random.uniform(0, ROWS - 1),
             "vx": random.choice([-0.7, -0.5, 0.5, 0.7]), "vy": random.choice([-0.7, -0.5, 0.5, 0.7])}
            for _ in range(4)
        ]
        anim_pingpong.last_t = t
    dt = max(0.01, t - getattr(anim_pingpong, "last_t", t))
    anim_pingpong.last_t = t

    for p in anim_pingpong.particles:
        p["x"] += p["vx"] * dt * 10
        p["y"] += p["vy"] * dt * 10
        if p["x"] < 0 or p["x"] > COLS - 1:
            p["vx"] *= -1
        if p["y"] < 0 or p["y"] > ROWS - 1:
            p["vy"] *= -1
        p["x"] = min(max(p["x"], 0), COLS - 1)
        p["y"] = min(max(p["y"], 0), ROWS - 1)

    p_clear()
    for p in anim_pingpong.particles:
        p_drawPixel(int(p["x"]), int(p["y"]), 1)
    p_scan()


def anim_rain(t):
    """Raindrops falling from the top with occasional splashes."""
    if not hasattr(anim_rain, "drops"):
        anim_rain.drops = []
    # Spawn new drops
    if random.random() < 0.4 and len(anim_rain.drops) < 20:
        anim_rain.drops.append({"x": random.randrange(COLS), "y": 0})
    # Move drops
    for d in anim_rain.drops:
        d["y"] += 1
    # Remove off-screen
    anim_rain.drops = [d for d in anim_rain.drops if d["y"] < ROWS]
    p_clear()
    for d in anim_rain.drops:
        p_drawPixel(d["x"], d["y"], 1)
        # Splash
        if d["y"] == ROWS - 1 and random.random() < 0.3:
            if d["x"] > 0:
                p_drawPixel(d["x"] - 1, d["y"], 1)
            if d["x"] < COLS - 1:
                p_drawPixel(d["x"] + 1, d["y"], 1)
    p_scan()


def anim_aurora(t):
    """Calming aurora: gentle flowing bands across the panel."""
    p_clear()
    for y in range(ROWS):
        for x in range(COLS):
            v = (
                math.sin((x * 0.3) + t * 0.8) +
                math.sin((y * 0.25) - t * 0.6) +
                math.sin((x + y) * 0.15 + t * 0.4)
            ) / 3.0
            if v > 0.35:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_life(t):
    """Conway's Game of Life evolving over time."""
    w, h = COLS, ROWS
    if not hasattr(anim_life, "grid"):
        anim_life.grid = [[1 if random.random() < 0.25 else 0 for _ in range(w)] for _ in range(h)]
        anim_life.last_step = 0
    # Step at ~6 FPS independent of t
    if t - getattr(anim_life, "last_step", 0) < 0.16:
        pass
    else:
        anim_life.last_step = t
        g = anim_life.grid
        ng = [[0] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                n = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        xx = (x + dx) % w
                        yy = (y + dy) % h
                        n += g[yy][xx]
                ng[y][x] = 1 if (n == 3 or (g[y][x] == 1 and n == 2)) else 0
        anim_life.grid = ng
    p_clear()
    for y in range(h):
        for x in range(w):
            if anim_life.grid[y][x]:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_matrix(t):
    """Matrix rain columns with trailing bits."""
    w, h = COLS, ROWS
    if not hasattr(anim_matrix, "cols"):
        anim_matrix.cols = [random.randrange(-h, 0) for _ in range(w)]
    anim_matrix.cols = [c + 1 if random.random() < 0.9 else c for c in anim_matrix.cols]
    p_clear()
    for x in range(w):
        head = anim_matrix.cols[x]
        for y in range(max(0, head - 4), min(h, head + 1)):
            if 0 <= y < h:
                p_drawPixel(x, y, 1)
        if head >= h:
            anim_matrix.cols[x] = random.randrange(-h, 0)
    p_scan()


def anim_rings(t):
    """Expanding concentric rings from center."""
    cx, cy = (COLS - 1) / 2.0, (ROWS - 1) / 2.0
    p_clear()
    r = (t * 3.0) % 12.0
    for y in range(ROWS):
        for x in range(COLS):
            d = math.hypot(x - cx, y - cy)
            if abs((d - r) % 6.0) < 0.8:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_tunnel(t):
    """Pseudo 3D tunnel using radial stripes and rotation."""
    cx, cy = (COLS - 1) / 2.0, (ROWS - 1) / 2.0
    p_clear()
    for y in range(ROWS):
        for x in range(COLS):
            dx, dy = x - cx, y - cy
            a = math.atan2(dy, dx)
            d = math.hypot(dx, dy)
            v = math.sin(d * 1.5 - t * 3.0) + math.sin(4 * a + t * 2.0)
            if v > 1.0:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_checker(t):
    """Animated checkerboard that shifts phase over time."""
    p_clear()
    phase = int((t * 6) % 2)
    for y in range(ROWS):
        for x in range(COLS):
            if ((x + y + phase) % 2) == 0:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_diamond(t):
    """Concentric diamond ripples expanding outward from the panel center."""
    p_clear()
    cx, cy = (COLS - 1) / 2.0, (ROWS - 1) / 2.0
    ripple_spacing = 6
    phase = int(t * 5.0) % ripple_spacing
    max_radius = int(cx + cy)
    radii = range(1 + phase, max_radius + 1, ripple_spacing)

    for y in range(ROWS):
        for x in range(COLS):
            distance = int(abs(x - cx) + abs(y - cy))
            if distance in radii:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_lissajous(t):
    """Lissajous figure traced by multiple points."""
    p_clear()
    a, b = 3.0, 2.0
    n = 24
    for i in range(n):
        u = t * 0.8 + (i * (math.pi * 2 / n))
        x = int((math.sin(a * u) * 0.5 + 0.5) * (COLS - 1))
        y = int((math.sin(b * u + math.pi / 2) * 0.5 + 0.5) * (ROWS - 1))
        p_drawPixel(x, y, 1)
    p_scan()


def _draw_normalized_curve(points):
    """Draw points expressed in a centered -1..1 coordinate system."""
    p_clear()
    cx, cy = (COLS - 1) / 2.0, (ROWS - 1) / 2.0
    for x, y in points:
        px = round(cx + (x * cx))
        py = round(cy + (y * cy))
        if 0 <= px < COLS and 0 <= py < ROWS:
            p_drawPixel(px, py, 1)
    p_scan()


def anim_rose(t):
    """Slowly rotating three-petal polar rose."""
    rotation = t * 0.35
    points = []
    for i in range(96):
        theta = math.tau * i / 96
        radius = 0.96 * math.cos(3 * theta)
        angle = theta + rotation
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    _draw_normalized_curve(points)


def anim_spirograph(t):
    """Rotating hypotrochoid resembling a mechanical spirograph."""
    rotation = t * 0.22
    sin_r, cos_r = math.sin(rotation), math.cos(rotation)
    points = []
    for i in range(120):
        theta = math.tau * 2 * i / 120
        x = (3.0 * math.cos(theta) + 2.6 * math.cos(1.5 * theta)) / 5.85
        y = (3.0 * math.sin(theta) - 2.6 * math.sin(1.5 * theta)) / 5.85
        points.append((x * cos_r - y * sin_r, x * sin_r + y * cos_r))
    _draw_normalized_curve(points)


def anim_chladni(t):
    """Morphing nodal lines inspired by Chladni plate modes."""
    blend = 0.5 + 0.5 * math.sin(t * 0.65)
    p_clear()
    for y in range(ROWS):
        ny = ((y + 0.5) / ROWS) - 0.5
        for x in range(COLS):
            nx = ((x + 0.5) / COLS) - 0.5
            mode_a = (
                math.cos(2 * math.pi * nx) * math.cos(3 * math.pi * ny)
                - math.cos(3 * math.pi * nx) * math.cos(2 * math.pi * ny)
            )
            mode_b = (
                math.cos(3 * math.pi * nx) * math.cos(4 * math.pi * ny)
                - math.cos(4 * math.pi * nx) * math.cos(3 * math.pi * ny)
            )
            if abs(((1.0 - blend) * mode_a) + (blend * mode_b)) < 0.14:
                p_drawPixel(x, y, 1)
    p_scan()


def anim_lemniscate(t):
    """A slowly rotating figure-eight curve."""
    rotation = t * 0.3
    sin_r, cos_r = math.sin(rotation), math.cos(rotation)
    points = []
    for i in range(80):
        theta = math.tau * i / 80
        x = 0.96 * math.cos(theta)
        y = 0.7 * math.sin(theta) * math.cos(theta)
        points.append((x * cos_r - y * sin_r, x * sin_r + y * cos_r))
    _draw_normalized_curve(points)


def anim_harmonograph(t):
    """Damped compound sine waves curling toward the center."""
    points = []
    for i in range(112):
        theta = 18.0 * i / 111
        decay = math.exp(-0.035 * theta)
        x = decay * (
            math.sin(2.0 * theta + t * 0.32)
            + 0.35 * math.sin(3.1 * theta - t * 0.17)
        ) / 1.35
        y = decay * (
            math.sin(2.7 * theta)
            + 0.35 * math.sin(1.8 * theta + t * 0.24)
        ) / 1.35
        points.append((x, y))
    _draw_normalized_curve(points)


ANIMATIONS = {
    "sparkle": anim_sparkle,
    "wave": anim_wave,
    "swirl": anim_swirl,
    "plasma": anim_plasma,
    "box": anim_box_marquee,
    "pingpong": anim_pingpong,
    "rain": anim_rain,
    "aurora": anim_aurora,
    "life": anim_life,
    "matrix": anim_matrix,
    "rings": anim_rings,
    "tunnel": anim_tunnel,
    "checker": anim_checker,
    "diamond": anim_diamond,
    "lissajous": anim_lissajous,
    "rose": anim_rose,
    "spirograph": anim_spirograph,
    "chladni": anim_chladni,
    "lemniscate": anim_lemniscate,
    "harmonograph": anim_harmonograph,
}


def run_animation_loop():
    """Background loop that renders active animation when animation_event is set."""
    print("[animations] Loop started.")
    start_time = time.time()
    while not config.shutdown_event.is_set():
        if config.animation_event.is_set() and config.current_animation in ANIMATIONS:
            # Pause scrolling while animating
            config.scrolling_event.clear()
            func = ANIMATIONS[config.current_animation]
            t = time.time() - start_time
            try:
                func(t)
            except Exception as e:
                print(f"[animations] Error in '{config.current_animation}': {e}")
            time.sleep(max(0.01, config.current_animation_speed))
        else:
            time.sleep(0.05)
    print("[animations] Loop ended.")
