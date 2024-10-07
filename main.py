import time
from config import pwm, GPIO, p_clear, p_scan, handle_key_input, scrolling_event, shutdown_event, shutdown
from scripts.clock import display_time
from scripts.weather import display_temperature, get_weather
from threading import Thread

# Ensure scrolling_event is cleared initially to start with time and weather display
scrolling_event.clear()  # This ensures scrolling is not active by default

# Function to alternate between displaying time and weather
def display_time_and_weather():
    weather_data = None
    last_weather_update = time.time()
    last_switch_time = time.time()
    display_time_mode = True  # Start by displaying time

    try:
        while not shutdown_event.is_set():  # Stop the loop if shutdown is triggered
            # Only proceed if scrolling is not active
            if not scrolling_event.is_set():
                current_time = time.time()

                # Update weather data every 20 minutes (1200 seconds)
                if current_time - last_weather_update > 1200:
                    print("[display_time_and_weather] Fetching new weather data...")
                    weather_data = get_weather()
                    last_weather_update = current_time

                # Alternate between time and weather every 15 seconds
                if current_time - last_switch_time > 15:
                    display_time_mode = not display_time_mode  # Toggle between time and weather
                    last_switch_time = current_time

                if display_time_mode:
                    print("[display_time_and_weather] Displaying time:", time.strftime("%H:%M:%S"))
                    p_clear()  # Clear the screen before displaying the time
                    display_time()  # Render the current time
                    p_scan()  # Update the display with rendered content
                else:
                    print("[display_time_and_weather] Displaying weather.")
                    p_clear()  # Clear the screen before displaying the weather
                    display_temperature()  # Render the weather information
                    p_scan()  # Update the display with rendered content

                # Check for key press to adjust brightness or other actions
                handle_key_input()

                time.sleep(1)
            else:
                print("[display_time_and_weather] Paused - scrolling is active.")
                time.sleep(0.1)  # Check every 100ms if scrolling is done

    except KeyboardInterrupt:
        pass

    finally:
        print("[display_time_and_weather] Cleaning up GPIO resources...")
        pwm.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    # Run display_time_and_weather in a separate thread
    display_thread = Thread(target=display_time_and_weather)
    display_thread.start()

    try:
        while True:
            time.sleep(1)  # Keep the main thread alive

    except KeyboardInterrupt:
        shutdown()  # Gracefully shut down on Ctrl+C

    # Wait for threads to finish
    display_thread.join()
    print("[main] Program terminated.")
