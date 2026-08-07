import time
from threading import Thread
from config import (
    pwm, GPIO,
    p_clear, p_scan,
    handle_key_input, scrolling_event,
    shutdown_event, shutdown,
    current_scrolling_text,  # Not strictly needed here, but available if desired
    countdown_event, animation_event
)
from scripts.clock import display_time
from scripts.weather import display_temperature, get_weather

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
       - Refresh weather data every 20 minutes.
       - Switch between time and weather every 15s.
       - Rely on final 'shutdown()' for GPIO cleanup, not here.
    """
    weather_data = None
    last_weather_update = time.time()
    last_switch_time = time.time()
    display_time_mode = True

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

            # Update weather data every 20 min
            current_time = time.time()
            if (current_time - last_weather_update) > 1200:
                print("[time/weather] Fetching new weather data...")
                weather_data = get_weather()  
                last_weather_update = current_time

            # Switch between time & weather every 15s
            mode_changed = False
            if (current_time - last_switch_time) > 15:
                display_time_mode = not display_time_mode
                last_switch_time = current_time
                mode_changed = True

            # Show time or weather (display functions handle their own clearing now)
            if display_time_mode:
                display_time(force=mode_changed)
            else:
                display_temperature(force=mode_changed)
            
            p_scan()

            # Adaptive sleep: longer when no changes expected
            # Clock updates every minute, weather updates every 20 min, mode switches every 15s
            sleep_duration = 1.0
            time.sleep(sleep_duration)

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
