import time
from threading import Thread
import config
from config import (
    pwm, GPIO,
    p_clear, p_scan,
    handle_key_input, scrolling_event,
    shutdown_event, shutdown,
    current_scrolling_text,  # Not strictly needed here, but available if desired
    countdown_event, animation_event
)
from scripts.clock import display_time
from scripts.weather import display_temperature, get_weather_snapshot
from scripts.weather_animations import render_weather_frame


DEFAULT_DISPLAY_STAGES = (
    ("clock", 12.0),
    ("temperature", 5.0),
    ("weather", 7.0),
)

def intro_greeting():
    """
    Optional: Show a quick greeting or blinking text at startup.
    Could also call a scroll function if you like.
    """
    print("[intro_greeting] Hello from LED Matrix!")
    time.sleep(1)  # Just a small pause for effect

def display_time_and_weather():
    """
    1. Optionally greet at boot.
    2. Loop until shutdown_event is set:
       - If scrolling_event is set, we pause time/weather to avoid concurrency.
       - Refresh weather data through the shared 20-minute cache.
       - Cycle through clock, temperature, and animated conditions.
       - Rely on final 'shutdown()' for GPIO cleanup, not here.
    """
    stage_index = 0
    stage_started = time.monotonic()
    mode_changed = True
    weather_snapshot = None
    config.current_default_view = "clock"

    try:
        # Boot-time optional greeting
        intro_greeting()

        while not shutdown_event.is_set():
            # Keep the physical brightness button synchronized in every mode.
            handle_key_input()

            # Foreground modes own the panel while active.
            if scrolling_event.is_set() or countdown_event.is_set() or animation_event.is_set():
                # print("[time/weather] paused because scrolling_event is set.")
                time.sleep(0.1)
                continue

            current_time = time.monotonic()
            if config.default_cycle_reset_event.is_set():
                config.default_cycle_reset_event.clear()
                stage_index = 0
                stage_started = current_time
                weather_snapshot = None
                mode_changed = True

            stage, duration = DEFAULT_DISPLAY_STAGES[stage_index]
            if current_time - stage_started >= duration:
                stage_index = (stage_index + 1) % len(DEFAULT_DISPLAY_STAGES)
                stage, duration = DEFAULT_DISPLAY_STAGES[stage_index]
                if stage == "weather":
                    weather_snapshot = get_weather_snapshot()
                    if weather_snapshot is None:
                        stage_index = 0
                        stage, duration = DEFAULT_DISPLAY_STAGES[stage_index]
                stage_started = current_time
                mode_changed = True

            config.current_default_view = stage
            if stage == "clock":
                display_time(force=mode_changed)
            elif stage == "temperature":
                display_temperature(force=mode_changed)
            else:
                weather_snapshot = weather_snapshot or get_weather_snapshot()
                if weather_snapshot:
                    config.current_weather_condition = weather_snapshot["description"].title()
                    config.current_weather_scene = render_weather_frame(
                        weather_snapshot,
                        current_time - stage_started,
                        segment_duration=duration,
                    )

            p_scan()
            mode_changed = False

            time.sleep(0.08 if stage == "weather" else 0.1)

    except KeyboardInterrupt:
        print("[time/weather] KeyboardInterrupt – stopping loop.")
    finally:
        # We do NOT clean up GPIO here to avoid conflicts with the scroll thread.
        # Let the global 'shutdown()' handle it once everything is done.
        print("[time/weather] Exiting display_time_and_weather loop (no GPIO cleanup here).")

if __name__ == "__main__":
    # Run display_time_and_weather in a separate thread
    display_thread = Thread(target=display_time_and_weather, daemon=True)
    display_thread.start()

    try:
        # Keep the main thread alive
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("[main] KeyboardInterrupt => calling shutdown()")
        shutdown()

    # Wait for display_thread to finish
    display_thread.join()
    print("[main] Program terminated.")
