"""F1 Pygame sidecar — live visualization of car position during evaluation.

DISABLED: Buggy on macOS Apple Silicon — SDL2 joystick subsystem segfaults
during Python teardown (IOKit/CoreFoundation accesses freed memory). The
entire pygame sidecar is disabled until this is resolved upstream. All live
telemetry still flows through the TUI widgets (LiveRunMonitor, etc.).

Runs as a separate process (not thread) because Pygame needs its own
main thread on macOS. Reads LiveStepUpdate from a multiprocessing.Queue.
"""

# from __future__ import annotations
#
# import multiprocessing as mp
# import os
# import sys
# from typing import Any
#
#
# class LiveF1ViewerProcess:
#     """Manages a subprocess running Pygame visualization of live evaluation steps."""
#
#     def __init__(self, track_csv_path: str, repo_root: str) -> None:
#         self._track_csv_path = track_csv_path
#         self._repo_root = repo_root
#         self._queue: mp.Queue = mp.Queue(maxsize=200)
#         self._shutdown = mp.Event()
#         self._process: mp.Process | None = None
#
#     def start(self) -> None:
#         """Spawn the viewer subprocess."""
#         self._process = mp.Process(
#             target=_viewer_main,
#             args=(self._track_csv_path, self._repo_root, self._queue, self._shutdown),
#             daemon=True,
#         )
#         self._process.start()
#
#     def send_update(self, update: Any) -> None:
#         """Send a LiveStepUpdate to the viewer. Drops oldest if queue is full."""
#         try:
#             self._queue.put_nowait(update)
#         except Exception:
#             try:
#                 self._queue.get_nowait()
#             except Exception:
#                 pass
#             try:
#                 self._queue.put_nowait(update)
#             except Exception:
#                 pass
#
#     def stop(self) -> None:
#         """Signal shutdown and wait for process to exit."""
#         self._shutdown.set()
#         if self._process is not None:
#             self._process.join(timeout=3)
#             if self._process.is_alive():
#                 self._process.terminate()
#             self._process = None
#
#     def is_alive(self) -> bool:
#         """Check if the viewer process is still running."""
#         return self._process is not None and self._process.is_alive()
#
#
# def _viewer_main(
#     track_csv_path: str,
#     repo_root: str,
#     queue: mp.Queue,
#     shutdown: mp.Event,
# ) -> None:
#     """Entry point for the viewer subprocess."""
#     # Add repo root to sys.path so env/viz imports work
#     if repo_root not in sys.path:
#         sys.path.insert(0, repo_root)
#
#     try:
#         import pygame
#         from env.track import Track
#         from viz.renderer import Visualizer
#     except ImportError:
#         return  # pygame or f1worldmodel not available
#
#     try:
#         track = Track.load(track_csv_path)
#     except Exception:
#         return
#
#     try:
#         viz = Visualizer(track)
#     except Exception:
#         return
#
#     clock = pygame.time.Clock()
#
#     while not shutdown.is_set():
#         # Pump pygame events (required to keep window responsive)
#         for event in pygame.event.get():
#             if event.type == pygame.QUIT:
#                 shutdown.set()
#                 break
#
#         if shutdown.is_set():
#             break
#
#         # Drain queue to latest update (newest-frame-wins)
#         latest = None
#         while True:
#             try:
#                 latest = queue.get_nowait()
#             except Exception:
#                 break
#
#         if latest is not None:
#             try:
#                 # Handle LivePairFrame (4C) or legacy LiveStepUpdate
#                 if hasattr(latest, "a") and hasattr(latest, "b"):
#                     # LivePairFrame — render both cars
#                     frame = latest
#                     car_state_a = frame.a.state if frame.a else {}
#                     car_state_b = frame.b.state if frame.b else {}
#                     action_a = frame.a.action if frame.a else []
#                     info_a = frame.a.info if frame.a else {}
#                     if hasattr(viz, "render_race"):
#                         viz.render_race(car_state_a, car_state_b, action_a, info_a)
#                     else:
#                         viz.render_frame(car_state_a, action_a, info_a)
#                 else:
#                     car_state = latest.state if hasattr(latest, "state") else {}
#                     action = latest.action if hasattr(latest, "action") else []
#                     info = latest.info if hasattr(latest, "info") else {}
#                     viz.render_frame(car_state, action, info)
#             except Exception:
#                 pass  # visualization errors are non-fatal
#
#         clock.tick(30)  # cap at 30fps
#
#     try:
#         pygame.quit()
#     except Exception:
#         pass
#     os._exit(0)
