import time
from config import p_clear, p_scan, render_word, display_lock, pause_display, resume_display

# scrolling_text.py

# Function to handle scrolling text (this will run in a separate thread)
def scroll_text(text, sleep_duration=0.2):
    
    # Check if the text is less than 3 characters
    if len(text) < 3:
        print(f"[scroll_text] Text is too short to scroll: {text}")
        with display_lock:
            p_clear()  # Clear the display
            render_word(text, 0, 4)  # Display the text statically
            p_scan()  # Update the display
        time.sleep(3)  # Keep the text on screen for a short duration before resuming
        resume_display()  # Resume the display updates
        return  # Exit the function since no scrolling is needed

    # If text is 3 characters or more, scroll the text
    pause_display()  # Pause time/weather display

    try:
        with display_lock:
            length = len(text) * 8  # Calculate total length of the text to scroll
            print(f"[scroll_text] Starting text scroll: {text}")

            scroll_range = 16 + length  # Precompute the range limit
            # Start scrolling from off the right edge (from display_width)
            for offset in range(16, -(length), -1):  # Scroll from right to left
                p_clear()  # Clear the screen
                render_word(text, offset, 4)  # Render the text at the new offset (-offset: horizontal position, 4: vertical position)
                p_scan()  # Update the display with the new frame
                time.sleep(sleep_duration)  # Adjust speed for smoother scrolling
    finally:
        print("[scroll_text] Finished text scroll.")
        # After scrolling ends, resume the time and weather display
        resume_display()
