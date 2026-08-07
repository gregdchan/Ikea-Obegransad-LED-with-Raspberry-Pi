##########################################################
# flask_server.py (FIXED for continuous scrolling)
##########################################################
from flask import Flask, render_template, request, jsonify, redirect, url_for
from threading import Thread, Lock, Event
import time, sys

import config
from config import (
    GPIO, brightness_levels, set_brightness,
    scrolling_event, shutdown_event,
    randomize_pixels
)
from scripts.scrolling_text import scroll_text as actual_scroll_text
from scripts.animations import run_animation_loop
from scripts.clock import display_time
from config import p_scan
from scripts.countdown import run_countdown_loop
import main   # For display_time_and_weather

app = Flask(__name__)

brightness_lock = Lock()
stop_event = Event()  # Local event if you want to stop the scroll_worker manually
DEFAULT_BRIGHTNESS_INDEX = 1

##########################################################
# Routes
##########################################################
@app.route("/")
def index():
    """
    Renders index.html, passing 'current_brightness'
    so the dropdown reflects the server's brightness state.
    """
    return render_template(
        "index.html",
        current_brightness=brightness_levels[config.brightness_index],
        settings={
            "scroll_direction": config.scroll_direction,
            "transitions_enabled": config.transitions_enabled,
            "weather_city": getattr(config, 'weather_city', ''),
            "weather_api_key": getattr(config, 'weather_api_key', ''),
        }
    )

@app.route("/turn_on", methods=["POST"])
def turn_on():
    with brightness_lock:
        config.brightness_index = DEFAULT_BRIGHTNESS_INDEX
        set_brightness(brightness_levels[config.brightness_index])
    return redirect("/")

@app.route("/turn_off", methods=["POST"])
def turn_off():
    with brightness_lock:
        config.brightness_index = 0
        set_brightness(brightness_levels[config.brightness_index])
    return redirect("/")

@app.route("/set_brightness", methods=["POST"])
def set_brightness_from_web():
    try:
        val = int(request.form.get("brightness", "").strip())
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid brightness"}), 400

    if val in brightness_levels:
        with brightness_lock:
            config.brightness_index = brightness_levels.index(val)
            set_brightness(val)
        return redirect("/")
    else:
        return jsonify({"error": "Invalid brightness level"}), 400

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

    # If an animation is running, transition then stop it
    try:
        if getattr(config, 'animation_event', None) and config.animation_event.is_set():
            # First stop animation to prevent it from repainting during transition
            config.animation_event.clear()
            config.current_animation = None
            if getattr(config, 'transitions_enabled', True):
                randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
    except Exception:
        pass

    # Force stop old scroll by clearing old text & event
    config.current_scrolling_text = ""
    scrolling_event.clear()
    time.sleep(0.05)  # tiny delay to ensure old loop sees the mismatch

    # Now set new text & speed
    config.current_scrolling_text = text
    config.current_scrolling_speed = new_speed

    # Raise event => new scroll
    scrolling_event.set()
    print(f"[scroll_text_route] Updated text='{text}', speed={new_speed}. Triggering scroll.")

    return redirect(url_for("index"))

@app.route("/stop_scroll", methods=["POST"])
def stop_scroll():
    """
    Stop scrolling => revert to clock by clearing text & event
    """
    print("[stop_scroll] Called. Transitioning out, then clearing text & event.")
    config.current_scrolling_text = ""
    scrolling_event.clear()
    # Brief randomization effect after stopping scroll to avoid race with scroll loop
    try:
        if getattr(config, 'transitions_enabled', True):
            randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
    except Exception as _:
        pass
    # Render a time frame to immediately resume visuals
    try:
        display_time(); p_scan()
    except Exception:
        pass
    return redirect(url_for("index"))

@app.route("/set_animation", methods=["POST"])
def set_animation():
    name = request.form.get("name", "").strip()
    speed_str = request.form.get("speed", "0.08").strip()
    try:
        config.current_animation_speed = max(0.01, float(speed_str))
    except Exception:
        pass
    # Stop scrolling text, set animation
    config.current_scrolling_text = ""
    scrolling_event.clear()
    if name:
        config.current_animation = name
        config.animation_event.set()
    return redirect(url_for("index"))

@app.route("/stop_animation", methods=["POST"])
def stop_animation():
    config.animation_event.clear()
    config.current_animation = None
    # Brief playful transition after animation is fully stopped
    try:
        if getattr(config, 'transitions_enabled', True):
            randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
    except Exception as _:
        pass
    try:
        display_time(); p_scan()
    except Exception:
        pass
    return redirect(url_for("index"))

@app.route("/start_countdown", methods=["POST"])
def start_countdown():
    try:
        minutes = int(request.form.get("minutes", "0").strip() or 0)
        seconds = int(request.form.get("seconds", "0").strip() or 0)
        total = max(0, minutes * 60 + seconds)
    except Exception:
        return jsonify({"error": "Invalid minutes/seconds"}), 400

    # Stop other modes (ensure animations stop first, then transition)
    try:
        if getattr(config, 'animation_event', None) and config.animation_event.is_set():
            config.animation_event.clear()
            config.current_animation = None
            if getattr(config, 'transitions_enabled', True):
                randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
    except Exception:
        pass

    config.current_scrolling_text = ""
    scrolling_event.clear()

    # Start countdown
    config.countdown_target_epoch = time.time() + total
    config.countdown_event.set()
    return redirect(url_for("index"))

@app.route("/stop_countdown", methods=["POST"])
def stop_countdown():
    # Stop then transition
    config.countdown_event.clear()
    config.countdown_target_epoch = 0.0
    try:
        if getattr(config, 'transitions_enabled', True):
            randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
    except Exception:
        pass
    try:
        display_time(); p_scan()
    except Exception:
        pass
    return redirect(url_for("index"))

@app.route("/status", methods=["GET"])
def status():
    """
    For the front-end to see if we're scrolling:
    It's scrolling if event is set AND there's text.
    """
    scrolling = scrolling_event.is_set() and bool(config.current_scrolling_text)
    # Compute countdown remaining if active
    remaining = None
    if config.countdown_event.is_set():
        try:
            remaining = max(0, int(round(config.countdown_target_epoch - time.time())))
        except Exception:
            remaining = None
    return jsonify({
        "scrolling": scrolling,
        "queue_length": 0,
        "last_message": config.current_scrolling_text or None,
        "animation": config.current_animation,
        "countdown_remaining": remaining
    })

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
        return redirect(url_for("index"))
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
    print("[flask_server] Starting on port 5000...")
    app.run(host="0.0.0.0", port=5000)
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
