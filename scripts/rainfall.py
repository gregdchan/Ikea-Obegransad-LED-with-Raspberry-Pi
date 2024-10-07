import time
import random
from config import p_clear, p_scan, p_drawPixel

def rainfall_animation(speed=0.1, drops=50):
    while True:
        raindrops = []

        for _ in range(drops):
            p_clear()

            # Create new raindrops
            raindrops.append([random.randint(0, 15), 0])  # Random x position, starting at the top (y=0)

            # Move raindrops
            for drop in raindrops:
                x, y = drop
                p_drawPixel(x, y, 1)  # Light up the pixel
                drop[1] += 1  # Move the drop down

            # Remove raindrops that reach the bottom
            raindrops = [drop for drop in raindrops if drop[1] < 16]

            p_scan()  # Update the display
            time.sleep(speed)

# Example usage
rainfall_animation(speed=0.1, drops=100)
