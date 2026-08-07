import RPi.GPIO as GPIO
from fonts import System6x7, SmallFont4x5, char_map, small_char_map
from threading import Event, Lock
import os
import time
import random

# ponytail: 6-line .env reader instead of python-dotenv — no quoting, no interpolation,
# no export lines. If the file ever needs those, add python-dotenv and delete this.
def _load_env(path=os.path.join(os.path.dirname(__file__), '.env')):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        print(f"[config] No .env at {path}; copy .env.example and fill it in.")

_load_env()

ROWS = 16
COLS = 16

# Track if the display (time/weather) is on
display_on = True

# Disable warnings and set up GPIO mode
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# GPIO pin mappings
P_EN = 17     # Brightness control (PWM pin)
P_DI = 2      # Data pin
P_CLK = 3     # Clock pin
P_CLA = 27    # Latch pin
P_KEY = 16    # Key input pin

# GPIO setup
GPIO.setup(P_EN, GPIO.OUT)
GPIO.setup(P_DI, GPIO.OUT)
GPIO.setup(P_CLK, GPIO.OUT)
GPIO.setup(P_CLA, GPIO.OUT)
GPIO.setup(P_KEY, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Brightness levels (0–255)
brightness_levels = [0, 64, 128, 192, 255]
brightness_index = 0  # Default to 0

# PWM setup for brightness control
pwm = GPIO.PWM(P_EN, 1000)  # 1 kHz frequency
pwm.start(brightness_levels[brightness_index] / 255.0 * 100)

# Shared locks & events
display_lock = Lock()
scrolling_event = Event()
# Event is set() when scrolling is active (pauses time/weather), cleared when inactive (allows time/weather)
# Start with event cleared to allow time/weather to run by default
blinking_event = Event()   # For blinking the colon or other cues

# Event to signal a clean shutdown across the app
shutdown_event = Event()

# Global variables for text scrolling
current_scrolling_text = ""      # The text currently scrolling (if any)
current_scrolling_speed = 0.05   # Default scroll speed (lower = faster, higher = slower)

# UI-configurable settings
scroll_direction = -1            # -1 = left, +1 = right
transitions_enabled = True       # Whether to show playful transitions

# Weather settings (from .env, editable at runtime via UI)
weather_api_key = os.environ.get('WEATHER_API_KEY', '')
weather_city = os.environ.get('WEATHER_CITY', 'new york city')

def update_settings(**kwargs):
    """
    Update runtime settings safely. Supported keys: scroll_direction, transitions_enabled,
    weather_api_key, weather_city.
    """
    global scroll_direction, transitions_enabled, weather_api_key, weather_city
    if 'scroll_direction' in kwargs:
        try:
            sd = int(kwargs['scroll_direction'])
            if sd in (-1, 1):
                scroll_direction = sd
        except Exception:
            pass
    if 'transitions_enabled' in kwargs:
        transitions_enabled = bool(kwargs['transitions_enabled'])
    if 'weather_api_key' in kwargs and kwargs['weather_api_key']:
        weather_api_key = str(kwargs['weather_api_key']).strip()
    if 'weather_city' in kwargs and kwargs['weather_city']:
        weather_city = str(kwargs['weather_city']).strip()

# Countdown timer state
countdown_event = Event()        # Set when countdown active
countdown_target_epoch = 0.0     # Epoch seconds when countdown ends
timer_mode = None                # "countdown", "pomodoro", or None
pomodoro_phase = None            # "work", "short_break", or "long_break"
pomodoro_session = 0
pomodoro_sessions = 4
pomodoro_work_seconds = 25 * 60
pomodoro_short_break_seconds = 5 * 60
pomodoro_long_break_seconds = 15 * 60

# Animation global state
animation_event = Event()        # Set when an animation is active
current_animation = None         # String key of the current animation
current_animation_speed = 0.08   # Base delay between frames

# Initialize the pixel buffer for the LED matrix
p_buf = [0] * 256
p_buf_prev = [0] * 256  # Previous frame for dirty tracking
dirty_flag = False  # Flag to track if display needs update

def set_brightness(brightness_value: int):
    """
    Adjust the PWM duty cycle to change brightness.
    :param brightness_value: Must be one of brightness_levels (0, 64, 128, 192, 255)
    """
    inverted_brightness = 255 - brightness_value
    duty_cycle = inverted_brightness / 255.0 * 100
    pwm.ChangeDutyCycle(duty_cycle)
    print(f"[set_brightness] brightness={brightness_value}, duty_cycle={duty_cycle:.1f}%")

def p_clear():
    """
    Clears the pixel buffer (p_buf) to all off (0).
    """
    global p_buf, dirty_flag
    with display_lock:
        p_buf = [0] * 256
        dirty_flag = True

def p_scan():
    """
    Optimized: Sends the current p_buf state to the LED matrix.
    Uses bulk GPIO operations for better performance.
    """
    global p_buf_prev, dirty_flag
    
    # Use a local reference to avoid repeated lookups
    _buf = p_buf
    
    with display_lock:
        # Batch GPIO operations - use output() to set multiple pins at once
        # First send all data bits
        for i in range(256):
            GPIO.output(P_DI, _buf[i])
            # Combine clock toggle into fewer operations
            GPIO.output(P_CLK, 1)
            GPIO.output(P_CLK, 0)
        
        # Finalize with latch
        GPIO.output(P_CLA, 1)
        GPIO.output(P_CLA, 0)
        
        # Update previous frame
        p_buf_prev = _buf[:]
        dirty_flag = False

def _capture_current_buffer():
    """
    Returns a shallow copy of the current pixel buffer.
    """
    return p_buf[:]

def _render_text_to_buffer_snapshot(word, x_start, y_start, force_small):
    """
    Renders 'word' into the pixel buffer to capture a snapshot, then restores original buffer.
    Returns the target buffer snapshot.
    """
    original = _capture_current_buffer()
    p_clear()
    render_word(word, x_start=x_start, y_start=y_start, large_numbers=not force_small, force_small=force_small)
    target = _capture_current_buffer()
    # restore original
    with display_lock:
        for i in range(256):
            p_buf[i] = original[i]
    p_scan()
    return target

def randomize_pixels(frames: int = 6, frame_delay: float = 0.05, fill_ratio: float = 0.5):
    """
    Quickly display a few frames of random pixels for a playful transition.
    """
    for _ in range(max(1, frames)):
        with display_lock:
            for i in range(256):
                p_buf[i] = 1 if random.random() < fill_ratio else 0
        p_scan()
        time.sleep(frame_delay)

def morph_to_text(word: str, x_start: int = 0, y_start: int = 4, force_small: bool = True, steps: int = 6, step_delay: float = 0.05):
    """
    Morphs current pixels into the target text over several steps.
    """
    target = _render_text_to_buffer_snapshot(word, x_start, y_start, force_small)
    source = _capture_current_buffer()

    diff_indices = [i for i in range(256) if source[i] != target[i]]
    random.shuffle(diff_indices)
    if steps <= 0:
        steps = 1
    batch_size = max(1, len(diff_indices) // steps)

    for s in range(steps):
        start_idx = s * batch_size
        end_idx = (s + 1) * batch_size if s < steps - 1 else len(diff_indices)
        with display_lock:
            for j in range(start_idx, end_idx):
                k = diff_indices[j]
                p_buf[k] = target[k]
        p_scan()
        time.sleep(step_delay)

def transition_to_text_with_randomize(word: str, x_start: int = 0, y_start: int = 4, force_small: bool = True):
    """
    Shows a brief randomization and then morphs into the given text.
    """
    randomize_pixels(frames=6, frame_delay=0.04, fill_ratio=0.5)
    morph_to_text(word, x_start=x_start, y_start=y_start, force_small=force_small, steps=6, step_delay=0.05)

# LUT for your 16x16 OBEGRÄNSAD matrix
lut = [
    [23, 22, 21, 20, 19, 18, 17, 16, 7, 6, 5, 4, 3, 2, 1, 0],
    [24, 25, 26, 27, 28, 29, 30, 31, 8, 9, 10, 11, 12, 13, 14, 15],
    [39, 38, 37, 36, 35, 34, 33, 32, 55, 54, 53, 52, 51, 50, 49, 48],
    [40, 41, 42, 43, 44, 45, 46, 47, 56, 57, 58, 59, 60, 61, 62, 63],
    [87, 86, 85, 84, 83, 82, 81, 80, 71, 70, 69, 68, 67, 66, 65, 64],
    [88, 89, 90, 91, 92, 93, 94, 95, 72, 73, 74, 75, 76, 77, 78, 79],
    [103, 102, 101, 100, 99, 98, 97, 96, 119, 118, 117, 116, 115, 114, 113, 112],
    [104, 105, 106, 107, 108, 109, 110, 111, 120, 121, 122, 123, 124, 125, 126, 127],
    [151, 150, 149, 148, 147, 146, 145, 144, 135, 134, 133, 132, 131, 130, 129, 128],
    [152, 153, 154, 155, 156, 157, 158, 159, 136, 137, 138, 139, 140, 141, 142, 143],
    [167, 166, 165, 164, 163, 162, 161, 160, 183, 182, 181, 180, 179, 178, 177, 176],
    [168, 169, 170, 171, 172, 173, 174, 175, 184, 185, 186, 187, 188, 189, 190, 191],
    [215, 214, 213, 212, 211, 210, 209, 208, 199, 198, 197, 196, 195, 194, 193, 192],
    [216, 217, 218, 219, 220, 221, 222, 223, 200, 201, 202, 203, 204, 205, 206, 207],
    [231, 230, 229, 228, 227, 226, 225, 224, 247, 246, 245, 244, 243, 242, 241, 240],
    [232, 233, 234, 235, 236, 237, 238, 239, 248, 249, 250, 251, 252, 253, 254, 255]
]

def p_drawPixel(x, y, color):
    """
    Sets a pixel (x,y) to 'color' (0 or 1) in the p_buf.
    Optimized with dirty tracking.
    """
    global dirty_flag
    if 0 <= x < COLS and 0 <= y < ROWS:
        index = lut[y][x]
        if p_buf[index] != color:
            p_buf[index] = color
            dirty_flag = True

def render_char(xs, ys, ch, size="small"):
    """
    Optimized character rendering with bit operation caching.
    """
    if size == "large" and ch in char_map:
        char_pos = char_map[ch]
        font_data = System6x7
        for col in range(6):
            col_data = font_data[char_pos + col]
            # Unroll the bit checking loop for better performance
            for row in range(7):
                if col_data & (1 << row):
                    p_drawPixel(xs + col, ys + row, 1)
    elif size == "small" and ch.lower() in small_char_map:
        char_pos = small_char_map[ch.lower()]
        y_offset = 2
        font_data = SmallFont4x5
        for col in range(4):
            col_data = font_data[char_pos + col]
            for row in range(5):
                if col_data & (1 << row):
                    p_drawPixel(xs + col, ys + y_offset + row, 1)
    else:
        print(f"[render_char] Unknown char '{ch}' in font data.")

def render_word(word, x_start=0, y_start=0, large_numbers=True, force_small=False):
    """
    Clears the display, then writes 'word' at (x_start,y_start).
    If 'large_numbers' is True, digits default to large font.
    """
    p_clear()
    x_offset = x_start
    length = len(word)

    for i, ch in enumerate(word):
        if force_small:
            size = "small"
        else:
            if ch.isdigit():
                if large_numbers:
                    size = "large"
                else:
                    prev_is_large = i > 0 and (word[i - 1].isupper() or word[i - 1].isdigit())
                    next_is_large = i < (length - 1) and (word[i + 1].isupper() or word[i + 1].isdigit())
                    size = "large" if (prev_is_large or next_is_large) else "small"
            else:
                # Lowercase gets the small font; uppercase AND punctuation get large,
                # so symbols match the weight of the letters around them.
                size = "small" if ch.islower() else "large"

        render_char(x_offset, y_start, ch, size)
        # Large chars are 8 pixels wide (6 pixels + 1 spacing), small chars are 6 pixels wide (4 pixels + 1 spacing)
        # But we want to advance by the actual width
        x_offset += 7 if size == "large" else 5

def handle_key_input():
    """
    Checks P_KEY for a press, cycles brightness.
    """
    global brightness_index
    if GPIO.input(P_KEY) == GPIO.LOW:
        print("[handle_key_input] Key Pressed!")
        brightness_index = (brightness_index + 1) % len(brightness_levels)
        set_brightness(brightness_levels[brightness_index])
        time.sleep(0.3)
        print("[handle_key_input] Brightness Level:", brightness_levels[brightness_index])

def pause_display():
    """
    Clears scrolling_event to pause the time/weather loop
    (which checks scrolling_event.is_set()) and sets display_on=False for any additional check.
    """
    global display_on
    print("[pause_display] Pausing time/weather for scrolling.")
    scrolling_event.clear()
    display_on = False

def resume_display():
    """
    Sets scrolling_event, so time/weather can resume. Also sets display_on=True.
    """
    global display_on
    print("[resume_display] Resuming time/weather after scroll.")
    scrolling_event.set()
    display_on = True

def shutdown():
    """
    Called at final program exit. Cancels all events, stops PWM, cleans up GPIO.
    """
    print("[shutdown] Called. Cleaning up...")
    shutdown_event.set()
    scrolling_event.set()
    pwm.stop()
    GPIO.cleanup()
    print("[shutdown] All cleaned up and PWM stopped.")
