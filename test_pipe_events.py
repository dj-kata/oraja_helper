import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from pipe_events import accepts_pipe_event


class PipeEventsTest(unittest.TestCase):
    def test_routes_player_sources(self):
        for event in ("song_select", "song_play", "song_play_end", "song_result"):
            bmz = {"event": event, "source": "bmz-player"}
            legacy = {"event": event}
            self.assertTrue(accepts_pipe_event(bmz, "bmz"))
            self.assertFalse(accepts_pipe_event(bmz, "beatoraja"))
            self.assertTrue(accepts_pipe_event(legacy, "beatoraja"))
            self.assertFalse(accepts_pipe_event(legacy, "bmz"))
        self.assertFalse(accepts_pipe_event([], "bmz"))
        self.assertFalse(accepts_pipe_event({"source": "unknown"}, "beatoraja"))
        self.assertFalse(accepts_pipe_event({}, "unknown"))

    def test_quick_retry_resets_attempt_metrics_without_scene_change(self):
        # Execute the real method without importing GUI/OBS/database dependencies.
        source = Path(__file__).with_name("oraja_helper.pyw").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "handle_oraja_helper_event")
        namespace = {"datetime": datetime}
        exec(compile(ast.Module(body=[method], type_ignores=[]), source, "exec"), namespace)
        calls = []
        app = SimpleNamespace(
            play_end_metrics_received_for_current_play=True,
            play_st=None,
            apply_game_state=lambda *args: calls.append(args),
            write_current_song_history=lambda data: None,
        )
        namespace[method.name](app, {"event": "song_play", "scene": "play"})
        self.assertFalse(app.play_end_metrics_received_for_current_play)
        self.assertIsInstance(app.play_st, datetime.datetime)
        self.assertEqual(calls, [("play", "named pipe")])


if __name__ == "__main__":
    unittest.main()
