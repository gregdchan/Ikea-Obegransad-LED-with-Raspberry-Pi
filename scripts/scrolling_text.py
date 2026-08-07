# scrolling_text.py

import time
import config
from config import (
    p_clear,
    p_scan,
    render_word,
    COLS,
    scrolling_event,
    shutdown_event
)

def scroll_text(
    text: str,
    delay: float = 0.12,
    repeat: bool = True,        # Default to True for continuous scrolling
    bounce: bool = False,
    large_numbers: bool = False,
    y_offset: int = 4
):
    """
    Continuously scrolls the given text across the 16x16 matrix,
    unless changed or stopped:
      - If 'repeat=True', once text goes off-screen, x_pos resets for another pass.
      - If 'bounce=True', text reverses direction when hitting edges.
      - If 'current_scrolling_text' changes mid-loop, we break out immediately (Approach A).
      - If 'scrolling_event' is cleared, we pause to let the time/weather loop run.

    :param text: The text to scroll.
    :param delay: Delay (seconds) between shifts in x_pos (controls speed).
    :param repeat: If True, once the text moves off left edge, x_pos resets for another pass.
    :param bounce: If True, reverse direction at left/right edges for a back-and-forth effect.
    :param large_numbers: If True, digits render in large font.
    :param y_offset: Vertical position for rendering (default 4 is near center).
    """

    print(f"[scroll_text] >>> START: text='{text}', delay={delay}, bounce={bounce}, repeat={repeat}")

    # If text is empty, bail out
    if not text:
        print("[scroll_text] No text provided. Exiting immediately.")
        return

    # Scroll in the large 6x7 font (same look as the clock/temperature digits).
    # It has no lowercase, so uppercase for display; keep `text` as-is because
    # the interrupt check compares it against config.current_scrolling_text.
    display_text = text.upper()

    # If very short (≤2 chars), render statically centered instead of scrolling
    trimmed = display_text.strip()
    if len(trimmed) <= 2:
        # Center horizontally: large font advances 7 px/char (6px glyph + 1 spacing)
        glyph_width = 7 * len(trimmed) - 1
        x_center = max(0, (COLS - glyph_width) // 2)
        if config.transitions_enabled:
            config.transition_to_text_with_randomize(
                trimmed,
                x_start=x_center,
                y_start=y_offset,
                force_small=False,
            )
        else:
            render_word(
                trimmed,
                x_start=x_center,
                y_start=y_offset,
                large_numbers=True,
                force_small=False,
            )
        p_scan()
        # Keep displaying until text changes or scrolling is stopped
        while not shutdown_event.is_set() and scrolling_event.is_set() and config.current_scrolling_text == text:
            time.sleep(0.1)
        return

    # Each large glyph advances by 7px (6px glyph + 1px spacing)
    text_width = 7 * len(display_text)

    # Before scrolling, optionally show a quick transition preview if enabled
    if getattr(config, 'transitions_enabled', True):
        preview_width = 7 * len(display_text)
        preview_x = max(0, (COLS - preview_width) // 2)
        config.transition_to_text_with_randomize(display_text, x_start=preview_x, y_start=y_offset, force_small=False)

    # Enter from the edge opposite the selected travel direction.
    direction = getattr(config, 'scroll_direction', -1)
    x_pos = COLS if direction < 0 else -text_width

    while not shutdown_event.is_set():
        # If scrolling_event is cleared => time/weather active => wait
        if not scrolling_event.is_set():
            time.sleep(0.1)
            continue

        # If user changed global text => mismatch => break old loop
        if config.current_scrolling_text != text:
            print("[scroll_text] New text arrived, interrupting old scroll.")
            break

        # Render the text at current x
        # render_word handles p_clear() internally
        render_word(
            display_text,
            x_start=x_pos,
            y_start=y_offset,
            large_numbers=True,
            force_small=False
        )
        p_scan()

        # Read direction on every frame so the setting applies immediately.
        direction = getattr(config, 'scroll_direction', -1)
        x_pos += direction
        time.sleep(delay)

        # Handle bounce or normal
        if bounce:
            if x_pos <= -text_width or x_pos >= COLS:
                config.scroll_direction = -direction
        else:
            passed_left = direction < 0 and x_pos < -text_width
            passed_right = direction > 0 and x_pos > COLS
            if not repeat and (passed_left or passed_right):
                break
            if repeat and passed_left:
                x_pos = COLS
            elif repeat and passed_right:
                x_pos = -text_width

    print(f"[scroll_text] <<< END: text='{text}'")

    # FINAL NOTE: We do NOT p_clear() here, so the last frame remains displayed
    # If you want the LED matrix cleared at the end, uncomment below:
    #
    # p_clear()
    # p_scan()
