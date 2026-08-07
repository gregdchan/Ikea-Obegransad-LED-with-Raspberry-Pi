import time
from datetime import datetime
from config import P_DI, P_CLK, P_CLA, lut, p_scan, p_clear, render_char
from fonts import System6x7, SmallFont4x5, char_map, small_char_map

# Cache last displayed time to avoid unnecessary redraws
_last_time = ""
_clock_cache = None

# Function to display the current time in HH:MM format
def display_time():
    global _last_time
    now = datetime.now()
    hour_str = now.strftime("%H")
    minute_str = now.strftime("%M")
    current_time = hour_str + minute_str
    
    # Only clear and redraw if time has changed
    if current_time != _last_time:
        p_clear()
        # Center large digits horizontally: 2 digits per row, each advances 7px = 14px total
        # Horizontal center offset = (16 - 14) // 2 = 1
        x0 = 1
        render_char(x0 + 0, 0, hour_str[0], size="large")
        render_char(x0 + 8, 0, hour_str[1], size="large")
        render_char(x0 + 0, 8, minute_str[0], size="large")
        render_char(x0 + 8, 8, minute_str[1], size="large")
        _last_time = current_time
