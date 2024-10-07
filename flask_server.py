from flask import Flask, render_template, request, jsonify, redirect, url_for
from config import GPIO, brightness_levels, set_brightness, render_word, p_scan, p_clear, COLS
from threading import Thread, Lock, Event
import time
import sys
import main

app = Flask(__name__)

brightness_lock = Lock()  # Lock to prevent race conditions on brightness changes
brightness_index = 0  # Track the current brightness level index globally
stop_event = Event()  # Event to signal stopping threads
scrolling_event = main.scrolling_event  # Use the scrolling_event from main

# Global variables to store the text and scroll speed
scrolling_text = ""
scroll_speed = 0.15  # Default scroll speed

# Flask route to turn off the display (set brightness to 0)
@app.route('/turn_off', methods=['POST'])
def turn_off():
    global brightness_index
    with brightness_lock:
        brightness_index = 0  # Set the brightness index to 0 for turning off
        set_brightness(brightness_levels[brightness_index])  # Set the brightness to 0 (off)
    return redirect('/')

# Flask route to turn on the display (set brightness to default)
@app.route('/turn_on', methods=['POST'])
def turn_on():
    global brightness_index
    with brightness_lock:
        brightness_index = 2  # Set the brightness index to the default level (assuming 1 is default)
        set_brightness(brightness_levels[brightness_index])  # Set the brightness to default
    return redirect('/')

# Flask route to set a specific brightness level
@app.route('/set_brightness', methods=['POST'])
def set_brightness_from_web():
    global brightness_index
    brightness = int(request.form.get('brightness'))  # Get the brightness level from form data
    if brightness in brightness_levels:  # Ensure the brightness value is valid
        with brightness_lock:
            brightness_index = brightness_levels.index(brightness)  # Update the brightness index
            set_brightness(brightness)  # Set the actual brightness
        return redirect('/')
    else:
        return jsonify({"error": "Invalid brightness level"}), 400

# Flask route for the main index page (for brightness control)
@app.route('/')
def index():
    return render_template('index.html', current_brightness=brightness_levels[brightness_index])

# Route for scrolling text with adjustable scroll speed
@app.route('/scroll_text', methods=['POST'])
def scroll_text_route():
    global scrolling_text, scroll_speed
    scrolling_text = request.form.get('text')  # Get text from the form input
    speed = float(request.form.get('speed'))  # Get scroll speed from form input
    scroll_speed = speed  # Set the scroll speed
    scrolling_event.set()  # Signal that scrolling should start
    return redirect(url_for('index'))

# Route to stop scrolling text
@app.route('/stop_scroll', methods=['POST'])
def stop_scroll():
    global scrolling_text
    scrolling_text = ""  # Clear the scrolling text to stop scrolling
    scrolling_event.clear()  # Signal that scrolling should stop
    return redirect(url_for('index'))

# Function to scroll the text on the LED matrix
def scroll_text(text):
    global scroll_speed
    display_width = 16  # The width of your display matrix in pixels
    text_width = len(text) * 8  # Calculate total width of the text (8 pixels per character)

    # If the text is less than 3 characters, display it statically
    if len(text) < 3:
        with brightness_lock:
            p_clear()  # Clear the screen
            render_word(text, 0, 4)  # Display the text statically at the leftmost edge (no scrolling)
            p_scan()  # Push buffer to the display
        return

    # Start scrolling from outside the right edge of the display
    start_offset = display_width  # This positions the text just outside the right edge of the display
    end_offset = -(text_width)  # Continue scrolling until the text is fully off the left edge

    print(f"[scroll_text] Starting text scroll: {text}")

    for offset in range(start_offset, end_offset, -1):  # Move the text from right to left
        with brightness_lock:
            if not scrolling_text or stop_event.is_set():
                break  # Exit if scrolling_text has been cleared or stop event is set
        p_clear()  # Clear the screen before each render
        render_word(text, offset, 4)  # Render the text at the current offset
        p_scan()  # Push buffer to the display
        time.sleep(scroll_speed)  # Control the speed of scrolling

# Background thread to handle the scrolling
def scroll_thread():
    global scrolling_text
    try:
        while not stop_event.is_set():  # Check the stop event to gracefully shutdown
            if scrolling_event.is_set() and scrolling_text:
                scroll_text(scrolling_text)
            else:
                time.sleep(0.1)  # Check every 100ms if scrolling should start
    except Exception as e:
        print(f"[scroll_thread] Exception: {e}")

# Function to start the Flask server
def run_flask_server():
    app.run(host='0.0.0.0', port=5000)

# Gracefully shut down the program
def shutdown():
    print("[shutdown] Shutting down...")
    stop_event.set()  # Signal threads to stop
    scrolling_event.clear()  # Ensure scrolling stops
    
    try:
        GPIO.cleanup()  # Clean up GPIO resources
    except Exception as e:
        print(f"[shutdown] Exception during GPIO cleanup: {e}")

    # Wait for threads to finish
    try:
        if display_thread.is_alive():
            display_thread.join()
        if scrolling_display_thread.is_alive():
            scrolling_display_thread.join()
    except Exception as e:
        print(f"[shutdown] Exception while waiting for threads to terminate: {e}")
    
    print("[shutdown] Threads have terminated.")
    sys.exit(0)  # Exit the program

if __name__ == "__main__":
    try:
        # Start the LED matrix display in a background thread
        display_thread = Thread(target=main.display_time_and_weather, daemon=True)
        display_thread.start()

        # Start the background thread for scrolling
        scrolling_display_thread = Thread(target=scroll_thread, daemon=True)
        scrolling_display_thread.start()

        # Run the Flask server in a separate thread
        flask_thread = Thread(target=run_flask_server, daemon=True)
        flask_thread.start()

        # Keep the main thread alive to handle shutdown
        while flask_thread.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        shutdown()
    except Exception as e:
        print(f"[main] Exception: {e}")
        shutdown()
