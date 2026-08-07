import time
import config
from config import p_clear, p_scan, render_char, display_lock
from scripts.clock import display_time


def _render_mm_ss(total_seconds: int):
    mins = max(0, total_seconds) // 60
    secs = max(0, total_seconds) % 60
    m1 = str(mins // 10)
    m2 = str(mins % 10)
    s1 = str(secs // 10)
    s2 = str(secs % 10)
    # Center two digits per row horizontally: advance ~7px per large glyph, total 14, offset x=1
    x0 = 1
    p_clear()
    render_char(x0 + 0, 0, m1, size="large")
    render_char(x0 + 8, 0, m2, size="large")
    render_char(x0 + 0, 8, s1, size="large")
    render_char(x0 + 8, 8, s2, size="large")
    p_scan()


def _render_done():
    # Render "00" over "00" to show finished
    _render_mm_ss(0)


def run_countdown_loop():
    """Background loop that renders countdown while countdown_event is set."""
    print("[countdown] Loop started.")
    while not config.shutdown_event.is_set():
        if getattr(config, 'countdown_event', None) and config.countdown_event.is_set():
            remaining = int(round(getattr(config, 'countdown_target_epoch', 0.0) - time.time()))
            if remaining <= 0:
                _render_done()
                # Playful transition back to time/weather if enabled
                # Clear first to prevent repaint, then transition
                config.countdown_event.clear()
                try:
                    if getattr(config, 'transitions_enabled', True):
                        config.randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
                except Exception:
                    pass
                # Immediately render time to resume visuals
                try:
                    display_time(force=True); p_scan()
                except Exception:
                    pass
                time.sleep(0.5)
                continue
            _render_mm_ss(remaining)
            time.sleep(0.2)
        else:
            time.sleep(0.1)
    print("[countdown] Loop ended.")

