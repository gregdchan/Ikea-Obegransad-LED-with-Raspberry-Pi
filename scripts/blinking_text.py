import time
from config import p_clear, p_scan, render_word, COLS

def blink_text(word, delay=0.5, blink_count=3):
    for char in word:
        # Clear the screen and calculate the centered position for each letter
        total_width = 8 if (char.isupper() or char.isdigit()) else 6
        x_start = (COLS - total_width) // 2

        for _ in range(blink_count):
            p_clear()
            render_word(char, x_start, 0, large_numbers=False)
            p_scan()
            time.sleep(delay)
            p_clear()
            p_scan()
            time.sleep(delay)

        # Ensure the character stays lit after blinking
        p_clear()
        render_word(char, x_start, 0, large_numbers=False)
        p_scan()
        time.sleep(delay)

    # Final clear after the entire word has blinked
    p_clear()
    p_scan()