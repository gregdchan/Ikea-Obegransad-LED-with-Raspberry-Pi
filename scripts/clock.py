import time
from datetime import datetime
from config import P_DI, P_CLK, P_CLA, lut, System6x7, p_scan, p_clear, render_char

# Function to display the current time in HH:MM format
def display_time():
    p_clear()

    now = datetime.now()
    hour_str = now.strftime("%H")
    minute_str = now.strftime("%M")

    render_char(0, 0, hour_str[0], size="large")  # First digit of hours
    render_char(8, 0, hour_str[1], size="large")  # Second digit of hours

    render_char(0, 8, minute_str[0], size="large")  # First digit of minutes
    render_char(8, 8, minute_str[1], size="large")  # Second digit of minutes
