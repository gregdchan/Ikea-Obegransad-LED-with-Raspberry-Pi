# scrolling_text.py
import time
from config import p_clear, p_scan, render_word, COLS

def scroll_text(word, delay=0.1):
    # Get total width of rendered word to know how far to scroll
    total_width = sum(8 if (ch.isupper() or ch.isdigit()) else 6 for ch in word)
    x_start = COLS  # Start scrolling from the right side of the display

    while x_start > -total_width:
        p_clear()  # Clear the display buffer before each new position
        render_word(word, x_start, 0, large_numbers=False)  # Use render_word with dynamic number sizing
        p_scan()  # Refresh display to show new position
        x_start -= 1  # Shift position left by one
        time.sleep(delay)  # Delay between each shift for scrolling effect

    # Final clear after scrolling completes
    p_clear()
    p_scan()
