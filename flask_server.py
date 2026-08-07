##########################################################
# flask_server.py (FIXED for continuous scrolling)
##########################################################
from flask import Flask, render_template, request, jsonify, redirect, url_for
from threading import Thread, Lock, Event
import time, sys, os

import config
from config import (
    GPIO, brightness_levels, set_brightness,
    scrolling_event, shutdown_event,
    randomize_pixels
)
from scripts.scrolling_text import scroll_text as actual_scroll_text
from scripts.animations import ANIMATIONS, run_animation_loop
from scripts.clock import display_time
from config import p_scan
from scripts.countdown import run_countdown_loop
import scripts.weather as weather
import main   # For display_time_and_weather

app = Flask(__name__)

brightness_lock = Lock()
mode_lock = Lock()
stop_event = Event()  # Local event if you want to stop the scroll_worker manually


def device_state():
    """Return one consistent snapshot for the UI and command responses."""
    brightness = config.brightness_value
    # p_buf_prev is the last frame latched to the hardware. Convert its physical
    # wiring order back to row-major screen order for the browser preview.
    with config.display_lock:
        latched_buffer = config.p_buf_prev[:]
    framebuffer = [
        int(bool(latched_buffer[config.lut[y][x]]))
        for y in range(config.ROWS)
        for x in range(config.COLS)
    ]
    scrolling = scrolling_event.is_set() and bool(config.current_scrolling_text)
    animation = (
        config.current_animation
        if config.animation_event.is_set() and config.current_animation
        else None
    )
    countdown_remaining = None
    if config.countdown_event.is_set():
        countdown_remaining = max(
            0,
            int(round(config.countdown_target_epoch - time.time())),
        )

    if countdown_remaining is not None:
        mode = "pomodoro" if config.timer_mode == "pomodoro" else "countdown"
    elif animation:
        mode = "animation"
    elif scrolling:
        mode = "message"
    else:
        mode = config.current_default_view

    return {
        "powered": brightness > 0,
        "brightness": brightness,
        "brightness_levels": brightness_levels,
        "framebuffer": framebuffer,
        "mode": mode,
        "scrolling": scrolling,
        "last_message": config.current_scrolling_text or None,
        "scroll_speed": config.current_scrolling_speed,
        "animation": animation,
        "animation_speed": config.current_animation_speed,
        "weather": {
            "condition": config.current_weather_condition,
            "scene": config.current_weather_scene,
        },
        "countdown_remaining": countdown_remaining,
        "pomodoro": {
            "phase": config.pomodoro_phase,
            "session": config.pomodoro_session,
            "sessions": config.pomodoro_sessions,
        },
        "settings": {
            "scroll_direction": config.scroll_direction,
            "transitions_enabled": config.transitions_enabled,
            "weather_city": config.weather_city,
            "weather_api_key_configured": bool(config.weather_api_key),
        },
    }


def command_response(message):
    """Use JSON for the app, while preserving ordinary form fallbacks."""
    wants_json = (
        request.headers.get("X-Requested-With") == "fetch"
        or request.accept_mimetypes.best == "application/json"
    )
    if wants_json:
        return jsonify({"ok": True, "message": message, "state": device_state()})
    return redirect(url_for("index"))


def stop_active_modes():
    """Stop all foreground renderers before starting another one."""
    config.current_scrolling_text = ""
    scrolling_event.clear()
    config.animation_event.clear()
    config.current_animation = None
    config.countdown_event.clear()
    config.countdown_target_epoch = 0.0
    config.timer_mode = None
    config.pomodoro_phase = None
    config.pomodoro_session = 0


def transition_back_to_clock():
    config.current_default_view = "clock"
    config.default_cycle_reset_event.set()
    try:
        if config.transitions_enabled:
            randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
    except Exception:
        pass
    try:
        display_time(force=True)
        p_scan()
    except Exception:
        pass

##########################################################
# Routes
##########################################################
@app.route("/")
def index():
    """Render the controls with a complete initial device snapshot."""
    return render_template(
        "index.html",
        initial_state=device_state(),
    )

@app.route("/turn_on", methods=["POST"])
def turn_on():
    with brightness_lock:
        set_brightness(config.last_nonzero_brightness or config.DEFAULT_BRIGHTNESS)
    return command_response("Display turned on")

@app.route("/turn_off", methods=["POST"])
def turn_off():
    with brightness_lock:
        set_brightness(0)
    return command_response("Display turned off")

@app.route("/set_brightness", methods=["POST"])
def set_brightness_from_web():
    try:
        val = int(request.form.get("brightness", "").strip())
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid brightness"}), 400

    if 0 <= val <= 255:
        with brightness_lock:
            set_brightness(val)
        return command_response("Brightness updated")
    else:
        return jsonify({"error": "Brightness must be between 0 and 255"}), 400

@app.route("/scroll_text", methods=["POST"])
def scroll_text_route():
    """
    Immediately override any existing scroll with new text:
      1) Clear old text => old loop breaks
      2) Set new text/speed in config => new loop begins
      3) Raise scrolling_event => scroll worker runs
    """
    text = request.form.get("text", "").strip()
    speed_str = request.form.get("speed", "0.15").strip()

    print(f"[scroll_text_route] Received text='{text}', speed='{speed_str}'")

    if not text:
        print("[scroll_text_route] ERROR: No text provided")
        return jsonify({"error": "No text provided"}), 400

    try:
        new_speed = float(speed_str)
    except ValueError:
        print("[scroll_text_route] ERROR: Invalid speed")
        return jsonify({"error": "Invalid speed"}), 400

    if not 0.02 <= new_speed <= 1.0:
        return jsonify({"error": "Speed must be between 0.02 and 1 second"}), 400

    with mode_lock:
        stop_active_modes()
        time.sleep(0.05)  # let the previous renderer observe its cleared event
        config.current_scrolling_text = text
        config.current_scrolling_speed = new_speed
        scrolling_event.set()
    print(f"[scroll_text_route] Updated text='{text}', speed={new_speed}. Triggering scroll.")

    return command_response("Message started")

@app.route("/stop_scroll", methods=["POST"])
def stop_scroll():
    """
    Stop scrolling => revert to clock by clearing text & event
    """
    print("[stop_scroll] Called. Transitioning out, then clearing text & event.")
    with mode_lock:
        config.current_scrolling_text = ""
        scrolling_event.clear()
        transition_back_to_clock()
    return command_response("Message stopped")

@app.route("/set_animation", methods=["POST"])
def set_animation():
    name = request.form.get("name", "").strip()
    speed_str = request.form.get("speed", "0.08").strip()
    try:
        speed = float(speed_str)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid animation speed"}), 400
    if name not in ANIMATIONS:
        return jsonify({"error": "Unknown animation"}), 400

    with mode_lock:
        stop_active_modes()
        config.current_animation_speed = min(1.0, max(0.01, speed))
        config.current_animation = name
        config.animation_event.set()
    return command_response(f"{name.replace('_', ' ').title()} animation started")

@app.route("/stop_animation", methods=["POST"])
def stop_animation():
    with mode_lock:
        config.animation_event.clear()
        config.current_animation = None
        transition_back_to_clock()
    return command_response("Animation stopped")

@app.route("/start_countdown", methods=["POST"])
def start_countdown():
    try:
        minutes = int(request.form.get("minutes", "0").strip() or 0)
        seconds = int(request.form.get("seconds", "0").strip() or 0)
        total = minutes * 60 + seconds
    except Exception:
        return jsonify({"error": "Invalid minutes/seconds"}), 400
    if total <= 0 or seconds < 0 or seconds > 59 or minutes < 0:
        return jsonify({"error": "Set a countdown longer than zero"}), 400

    with mode_lock:
        stop_active_modes()
        config.timer_mode = "countdown"
        config.countdown_target_epoch = time.time() + total
        config.countdown_event.set()
    return command_response("Countdown started")


@app.route("/start_pomodoro", methods=["POST"])
def start_pomodoro():
    try:
        work_minutes = int(request.form.get("work_minutes", "25").strip())
        short_break_minutes = int(request.form.get("short_break_minutes", "5").strip())
        long_break_minutes = int(request.form.get("long_break_minutes", "15").strip())
        sessions = int(request.form.get("sessions", "4").strip())
    except (AttributeError, TypeError, ValueError):
        return jsonify({"error": "Invalid Pomodoro settings"}), 400

    durations = (work_minutes, short_break_minutes, long_break_minutes)
    if any(value < 1 or value > 99 for value in durations) or not 1 <= sessions <= 12:
        return jsonify({"error": "Use 1-99 minutes and 1-12 focus sessions"}), 400

    with mode_lock:
        stop_active_modes()
        config.timer_mode = "pomodoro"
        config.pomodoro_phase = "work"
        config.pomodoro_session = 1
        config.pomodoro_sessions = sessions
        config.pomodoro_work_seconds = work_minutes * 60
        config.pomodoro_short_break_seconds = short_break_minutes * 60
        config.pomodoro_long_break_seconds = long_break_minutes * 60
        config.countdown_target_epoch = time.time() + config.pomodoro_work_seconds
        config.countdown_event.set()
    return command_response("Focus session started")

@app.route("/stop_countdown", methods=["POST"])
def stop_countdown():
    with mode_lock:
        config.countdown_event.clear()
        config.countdown_target_epoch = 0.0
        config.timer_mode = None
        config.pomodoro_phase = None
        config.pomodoro_session = 0
        transition_back_to_clock()
    return command_response("Countdown stopped")


@app.route("/show_clock", methods=["POST"])
def show_clock():
    with mode_lock:
        stop_active_modes()
        transition_back_to_clock()
    return command_response("Clock restored")

@app.route("/status", methods=["GET"])
def status():
    return jsonify(device_state())

@app.route("/update_settings", methods=["POST"])
def update_settings():
    try:
        sd = request.form.get("scroll_direction")
        tr = request.form.get("transitions_enabled")
        city = request.form.get("weather_city", "").strip()
        apikey = request.form.get("weather_api_key", "").strip()

        settings_payload = {}
        if sd in ("-1", "1"):
            settings_payload['scroll_direction'] = int(sd)
        if tr is not None:
            settings_payload['transitions_enabled'] = (tr == 'on' or tr == 'true' or tr == '1')
        if city:
            settings_payload['weather_city'] = city
        if apikey:
            settings_payload['weather_api_key'] = apikey

        if settings_payload:
            config.update_settings(**settings_payload)
        if city or apikey:
            weather.invalidate_weather_cache()
            config.default_cycle_reset_event.set()
        return command_response("Settings saved")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

##########################################################
# Scrolling Thread
##########################################################
def scroll_worker():
    """
    Continuously checks if scrolling_event is set + config.current_scrolling_text
    We'll use repeat=True in actual_scroll_text so it never ends on its own
    unless a new text arrives or /stop_scroll is called.
    """
    print("[scroll_worker] Thread started. Ready to scroll text on demand.")

    while not stop_event.is_set() and not shutdown_event.is_set():
        # If event is set and text is not empty
        if scrolling_event.is_set() and config.current_scrolling_text:
            text_to_scroll = config.current_scrolling_text
            print(f"[scroll_worker] Starting scroll for '{text_to_scroll}' at speed={config.current_scrolling_speed}")

            # Force indefinite repeat => never ends unless interrupted or /stop_scroll
            actual_scroll_text(
                text_to_scroll,
                delay=config.current_scrolling_speed,
                repeat=True,        # <--- Continuous scroll
                large_numbers=False
            )

            # If actual_scroll_text returns normally, we see if it was truly done or interrupted
            if config.current_scrolling_text == text_to_scroll:
                # Without repeat, you'd do text="" but let's keep indefinite
                # So we do NOTHING here => text remains, event remains
                print(f"[scroll_worker] Indefinite scroll ended? Possibly old code. But leaving text in place.")
            else:
                print(f"[scroll_worker] Scroll was interrupted with new text '{config.current_scrolling_text}'")

        else:
            time.sleep(0.1)

    print("[scroll_worker] Exiting. stop_event or shutdown_event was set.")

def run_flask_server():
    port = int(os.environ.get("PORT", 5000))
    print(f"[flask_server] Starting on port {port}...")
    app.run(host="0.0.0.0", port=port)
    print("[flask_server] Flask server stopped.")

def shutdown():
    print("[shutdown] Stopping threads & cleaning up.")
    stop_event.set()
    scrolling_event.clear()
    try:
        GPIO.cleanup()
    except Exception as e:
        print("[shutdown] GPIO cleanup error:", e)
    sys.exit(0)

##########################################################
# Main Entry
##########################################################
if __name__ == "__main__":
    try:
        # Start the main time/weather loop in the background
        display_thread = Thread(target=main.display_time_and_weather, daemon=True)
        display_thread.start()

        # Start scrolling worker
        worker = Thread(target=scroll_worker, daemon=True)
        worker.start()

        # Start animations loop
        anim_worker = Thread(target=run_animation_loop, daemon=True)
        anim_worker.start()

        # Start countdown loop
        countdown_worker = Thread(target=run_countdown_loop, daemon=True)
        countdown_worker.start()

        # Start Flask (blocking)
        run_flask_server()

    except KeyboardInterrupt:
        print("[main] KeyboardInterrupt => shutdown()")
        shutdown()
    except Exception as e:
        print(f"[main] Exception: {e}")
        shutdown()
