"""Smoke tests for the Flask controls without requiring Raspberry Pi hardware."""
import sys
import unittest
from unittest.mock import MagicMock


sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = MagicMock()

import config
from flask import render_template
from flask_server import app, stop_active_modes


class WebInterfaceTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        stop_active_modes()
        config.brightness_index = 0
        config.transitions_enabled = False
        with config.display_lock:
            config.p_buf_prev = [0] * 256
        self.headers = {
            "Accept": "application/json",
            "X-Requested-With": "fetch",
        }

    def post(self, path, data=None):
        return self.client.post(path, data=data or {}, headers=self.headers)

    def test_page_and_status_render(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"OBEGR", page.data)

        status = self.client.get("/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["mode"], "clock")
        self.assertEqual(len(status.get_json()["framebuffer"]), 256)

    def test_status_maps_latched_hardware_buffer_to_screen_order(self):
        with config.display_lock:
            config.p_buf_prev = [0] * 256
            config.p_buf_prev[config.lut[3][7]] = 1
            config.p_buf_prev[config.lut[12][14]] = 1

        framebuffer = self.client.get("/status").get_json()["framebuffer"]
        self.assertEqual(framebuffer[(3 * 16) + 7], 1)
        self.assertEqual(framebuffer[(12 * 16) + 14], 1)
        self.assertEqual(sum(framebuffer), 2)

    def test_legacy_template_context_does_not_fail_during_restart(self):
        with app.test_request_context("/"):
            html = render_template(
                "index.html",
                current_brightness=64,
                settings={
                    "scroll_direction": -1,
                    "transitions_enabled": True,
                    "weather_city": "New York",
                },
            )
        self.assertIn("const INITIAL_STATE = {", html)

    def test_device_commands_return_updated_state(self):
        response = self.post("/turn_on")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["state"]["powered"])

        response = self.post("/set_brightness", {"brightness": "128"})
        self.assertEqual(response.get_json()["state"]["brightness"], 128)

        response = self.post("/scroll_text", {"text": "Hello", "speed": "0.15"})
        self.assertEqual(response.get_json()["state"]["mode"], "message")

        response = self.post("/set_animation", {"name": "wave", "speed": "0.08"})
        self.assertEqual(response.get_json()["state"]["mode"], "animation")
        self.assertFalse(config.scrolling_event.is_set())

        response = self.post("/start_countdown", {"minutes": "5", "seconds": "0"})
        self.assertEqual(response.get_json()["state"]["mode"], "countdown")
        self.assertFalse(config.animation_event.is_set())

        response = self.post("/show_clock")
        self.assertEqual(response.get_json()["state"]["mode"], "clock")
        self.assertTrue(any(response.get_json()["state"]["framebuffer"]))

    def test_invalid_commands_return_400(self):
        self.assertEqual(self.post("/set_brightness", {"brightness": "12"}).status_code, 400)
        self.assertEqual(self.post("/scroll_text", {"text": "", "speed": "0.15"}).status_code, 400)
        self.assertEqual(self.post("/set_animation", {"name": "unknown"}).status_code, 400)
        self.assertEqual(self.post("/start_countdown", {"minutes": "0", "seconds": "0"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
