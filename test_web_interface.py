"""Smoke tests for the Flask controls without requiring Raspberry Pi hardware."""
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch


sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = MagicMock()

import config
import main
import scripts.animations as animations
import scripts.clock as clock
import scripts.scrolling_text as scrolling_text
import scripts.weather as weather
import scripts.weather_animations as weather_animations
from scripts.countdown import advance_pomodoro_phase
from flask import render_template
from flask_server import app, stop_active_modes


class WebInterfaceTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        stop_active_modes()
        config.brightness_value = 0
        config.brightness_index = 0
        config.last_nonzero_brightness = config.DEFAULT_BRIGHTNESS
        config.scroll_direction = -1
        config.transitions_enabled = False
        config.current_default_view = "clock"
        config.current_weather_condition = None
        config.current_weather_scene = None
        config.default_cycle_reset_event.clear()
        weather.invalidate_weather_cache()
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

    def test_active_low_brightness_mapping_and_default(self):
        self.assertEqual(config.DEFAULT_BRIGHTNESS, 128)
        self.assertEqual(config.brightness_to_duty_cycle(0), 100)
        self.assertEqual(config.brightness_to_duty_cycle(255), 0)
        config.pwm.start.assert_called_once_with(0)

    def test_physical_button_updates_shared_brightness_once_per_press(self):
        config.brightness_value = 64
        config.brightness_index = 1
        with (
            patch.object(config.GPIO, "LOW", 0),
            patch.object(config.GPIO, "HIGH", 1),
            patch.object(config.GPIO, "input", side_effect=[0, 0, 1, 0]),
        ):
            config._last_key_state = 1
            config.handle_key_input()
            self.assertEqual(config.brightness_value, 128)
            config.handle_key_input()
            self.assertEqual(config.brightness_value, 128)
            config.handle_key_input()
            config.handle_key_input()
            self.assertEqual(config.brightness_value, 192)

        self.assertEqual(self.client.get("/status").get_json()["brightness"], 192)

    def test_status_maps_latched_hardware_buffer_to_screen_order(self):
        with config.display_lock:
            config.p_buf_prev = [0] * 256
            config.p_buf_prev[config.lut[3][7]] = 1
            config.p_buf_prev[config.lut[12][14]] = 1

        framebuffer = self.client.get("/status").get_json()["framebuffer"]
        self.assertEqual(framebuffer[(3 * 16) + 7], 1)
        self.assertEqual(framebuffer[(12 * 16) + 14], 1)
        self.assertEqual(sum(framebuffer), 2)

    def test_renderers_can_force_a_cached_frame(self):
        clock._last_time = datetime.now().strftime("%H%M")
        with patch.object(clock, "p_clear") as clear, patch.object(clock, "render_char"):
            clock.display_time()
            clear.assert_not_called()
            clock.display_time(force=True)
            clear.assert_called_once()

        weather._last_temp_display = "72"
        weather._has_drawn_once = True
        with (
            patch.object(weather, "get_weather", return_value=72),
            patch.object(weather, "p_clear") as clear,
            patch.object(weather, "render_char"),
        ):
            weather.display_temperature()
            clear.assert_not_called()
            weather.display_temperature(force=True)
            clear.assert_called_once()
            weather.render_char.assert_any_call(5, 8, "F", size="large")

    def test_weather_snapshot_keeps_condition_and_day_night_icon(self):
        response = MagicMock()
        response.json.return_value = {
            "main": {"temp": 71.8},
            "weather": [{
                "id": 801,
                "main": "Clouds",
                "description": "few clouds",
                "icon": "02n",
            }],
        }
        weather.last_request_time = 0
        weather.cached_temperature = None
        weather.cached_weather_snapshot = None

        with (
            patch.object(config, "weather_api_key", "test-key"),
            patch.object(weather.requests, "get", return_value=response) as request,
        ):
            snapshot = weather.get_weather_snapshot()
            cached_snapshot = weather.get_weather_snapshot()

        self.assertEqual(snapshot, cached_snapshot)
        self.assertEqual(snapshot["temperature"], 71.8)
        self.assertEqual(snapshot["condition_id"], 801)
        self.assertEqual(snapshot["description"], "few clouds")
        self.assertEqual(snapshot["icon"], "02n")
        request.assert_called_once()

    def test_weather_conditions_render_animated_matrix_frames(self):
        cases = (
            (800, "01d", "clear_day"),
            (800, "01n", "clear_night"),
            (801, "02d", "partly_cloudy_day"),
            (802, "03n", "partly_cloudy_night"),
            (804, "04d", "clouds"),
            (500, "10d", "rain"),
            (211, "11d", "thunderstorm"),
            (601, "13d", "snow"),
            (741, "50d", "fog"),
        )
        full_moon = (
            weather_animations.NEW_MOON_EPOCH
            + weather_animations.SYNODIC_MONTH_SECONDS / 2
        )

        for condition_id, icon, expected_scene in cases:
            with self.subTest(scene=expected_scene):
                with (
                    patch.object(weather_animations, "p_clear") as clear,
                    patch.object(weather_animations, "p_drawPixel") as draw,
                ):
                    scene = weather_animations.render_weather_frame(
                        {"condition_id": condition_id, "icon": icon},
                        t=2.3,
                        timestamp=full_moon,
                    )

                pixels = {
                    (call.args[0], call.args[1])
                    for call in draw.call_args_list
                    if len(call.args) < 3 or call.args[2] != 0
                }
                self.assertEqual(scene, expected_scene)
                self.assertGreater(len(pixels), 5)
                self.assertTrue(all(0 <= x < 16 and 0 <= y < 16 for x, y in pixels))
                clear.assert_called_once()

    def test_weather_segments_bookend_animation_with_condition_labels(self):
        labels = {
            "clear_day": "SUN",
            "clear_night": "MOON",
            "partly_cloudy_day": "PCLD",
            "clouds": "CLDS",
            "rain": "RAIN",
            "thunderstorm": "THDR",
            "snow": "SNOW",
            "fog": "FOG",
        }
        for scene, label in labels.items():
            with self.subTest(scene=scene):
                self.assertEqual(weather_animations.weather_label_for_scene(scene), label)

        snapshot = {"condition_id": 500, "icon": "10d"}
        frames = []
        for frame_time in (0.5, 3.0, 6.2):
            with (
                patch.object(weather_animations, "p_clear"),
                patch.object(weather_animations, "p_drawPixel") as draw,
            ):
                weather_animations.render_weather_frame(snapshot, frame_time)
            frames.append({(call.args[0], call.args[1]) for call in draw.call_args_list})

        self.assertEqual(frames[0], frames[2])
        self.assertNotEqual(frames[0], frames[1])

    def test_default_display_cycle_omits_animated_weather(self):
        self.assertEqual(
            main.DEFAULT_DISPLAY_STAGES,
            (("clock", 15.0), ("temperature", 15.0)),
        )
        config.current_default_view = "weather"
        config.current_weather_condition = "Clear Sky"
        config.current_weather_scene = "clear_day"
        status = self.client.get("/status").get_json()
        self.assertEqual(status["mode"], "weather")
        self.assertEqual(status["weather"]["condition"], "Clear Sky")
        self.assertEqual(status["weather"]["scene"], "clear_day")

    def test_diamond_animation_expands_as_concentric_ripples(self):
        with (
            patch.object(animations, "p_clear") as clear,
            patch.object(animations, "p_drawPixel") as draw,
            patch.object(animations, "p_scan") as scan,
        ):
            animations.anim_diamond(0)
            first_frame = {(call.args[0], call.args[1]) for call in draw.call_args_list}

            draw.reset_mock()
            animations.anim_diamond(0.21)
            second_frame = {(call.args[0], call.args[1]) for call in draw.call_args_list}

        self.assertIn((7, 7), first_frame)
        self.assertIn((7, 6), second_frame)
        self.assertNotIn((7, 7), second_frame)
        self.assertGreater(len(first_frame), 4)
        self.assertEqual(clear.call_count, 2)
        self.assertEqual(scan.call_count, 2)

    def test_new_math_scenes_draw_valid_matrix_frames(self):
        scene_names = ("rose", "spirograph", "chladni", "lemniscate", "harmonograph")
        page = self.client.get("/").get_data(as_text=True)

        for name in scene_names:
            with self.subTest(scene=name):
                self.assertIn(f'data-animation="{name}"', page)
                self.assertIn(name, animations.ANIMATIONS)

                with (
                    patch.object(animations, "p_clear") as clear,
                    patch.object(animations, "p_drawPixel") as draw,
                    patch.object(animations, "p_scan") as scan,
                ):
                    animations.ANIMATIONS[name](0.73)

                pixels = {(call.args[0], call.args[1]) for call in draw.call_args_list}
                self.assertGreater(len(pixels), 8)
                self.assertTrue(all(0 <= x < 16 and 0 <= y < 16 for x, y in pixels))
                clear.assert_called_once()
                scan.assert_called_once()

    def test_rightward_scroll_enters_and_wraps_from_the_left(self):
        positions = []
        config.scroll_direction = 1
        config.current_scrolling_text = "ABC"
        config.scrolling_event.set()

        def capture_position(_, x_start, **__):
            positions.append(x_start)
            if len(positions) == 42:
                config.current_scrolling_text = ""

        with (
            patch.object(scrolling_text, "render_word", side_effect=capture_position),
            patch.object(scrolling_text, "p_scan"),
            patch.object(scrolling_text.time, "sleep"),
        ):
            scrolling_text.scroll_text("ABC", delay=0, repeat=True)

        self.assertEqual(positions[0], -21)
        self.assertIn(-21, positions[1:])

    def test_transition_toggle_applies_to_short_messages(self):
        config.current_scrolling_text = "OK"
        config.scrolling_event.set()
        config.transitions_enabled = False

        def stop_message(_):
            config.current_scrolling_text = ""

        with (
            patch.object(config, "transition_to_text_with_randomize") as transition,
            patch.object(scrolling_text, "render_word") as render_word,
            patch.object(scrolling_text, "p_scan"),
            patch.object(scrolling_text.time, "sleep", side_effect=stop_message),
        ):
            scrolling_text.scroll_text("OK", delay=0)

        transition.assert_not_called()
        render_word.assert_called_once()

    def test_direction_change_applies_to_an_active_message(self):
        positions = []
        config.scroll_direction = -1
        config.current_scrolling_text = "ABC"
        config.scrolling_event.set()

        def capture_position(_, x_start, **__):
            positions.append(x_start)
            if len(positions) == 4:
                config.scroll_direction = 1
            elif len(positions) == 8:
                config.current_scrolling_text = ""

        with (
            patch.object(scrolling_text, "render_word", side_effect=capture_position),
            patch.object(scrolling_text, "p_scan"),
            patch.object(scrolling_text.time, "sleep"),
        ):
            scrolling_text.scroll_text("ABC", delay=0, repeat=True)

        self.assertEqual(positions[:4], [16, 15, 14, 13])
        self.assertEqual(positions[4], 14)

    def test_pomodoro_phase_progression(self):
        config.timer_mode = "pomodoro"
        config.pomodoro_phase = "work"
        config.pomodoro_session = 1
        config.pomodoro_sessions = 2
        config.pomodoro_work_seconds = 25 * 60
        config.pomodoro_short_break_seconds = 5 * 60
        config.pomodoro_long_break_seconds = 15 * 60

        self.assertTrue(advance_pomodoro_phase(now=100))
        self.assertEqual(config.pomodoro_phase, "short_break")
        self.assertEqual(config.countdown_target_epoch, 400)
        self.assertTrue(advance_pomodoro_phase(now=400))
        self.assertEqual(config.pomodoro_phase, "work")
        self.assertEqual(config.pomodoro_session, 2)
        self.assertTrue(advance_pomodoro_phase(now=500))
        self.assertEqual(config.pomodoro_phase, "long_break")
        self.assertFalse(advance_pomodoro_phase(now=1400))

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

        response = self.post("/set_brightness", {"brightness": "137"})
        self.assertEqual(response.get_json()["state"]["brightness"], 137)

        response = self.post("/turn_off")
        self.assertFalse(response.get_json()["state"]["powered"])
        self.assertEqual(response.get_json()["state"]["brightness"], 0)

        response = self.post("/turn_on")
        self.assertTrue(response.get_json()["state"]["powered"])
        self.assertEqual(response.get_json()["state"]["brightness"], 137)

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

        response = self.post(
            "/update_settings",
            {"scroll_direction": "1", "transitions_enabled": "false"},
        )
        self.assertEqual(response.get_json()["state"]["settings"]["scroll_direction"], 1)
        self.assertFalse(response.get_json()["state"]["settings"]["transitions_enabled"])

        response = self.post(
            "/start_pomodoro",
            {
                "work_minutes": "25",
                "short_break_minutes": "5",
                "long_break_minutes": "15",
                "sessions": "4",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["state"]["mode"], "pomodoro")
        self.assertEqual(response.get_json()["state"]["pomodoro"]["phase"], "work")

    def test_invalid_commands_return_400(self):
        self.assertEqual(self.post("/set_brightness", {"brightness": "256"}).status_code, 400)
        self.assertEqual(self.post("/scroll_text", {"text": "", "speed": "0.15"}).status_code, 400)
        self.assertEqual(self.post("/set_animation", {"name": "unknown"}).status_code, 400)
        self.assertEqual(self.post("/start_countdown", {"minutes": "0", "seconds": "0"}).status_code, 400)
        self.assertEqual(self.post("/start_pomodoro", {"work_minutes": "0"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
