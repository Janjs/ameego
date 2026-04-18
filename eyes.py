from __future__ import annotations

import logging
import math
import random
import threading
import time
from dataclasses import dataclass

from config import Config


logger = logging.getLogger(__name__)


EYE_STATES = {
    "idle",
    "wake_detected",
    "listening",
    "thinking",
    "speaking",
    "error",
    "sleeping",
}


@dataclass
class EyePose:
    openness: float = 1.0
    stretch_x: float = 1.0
    stretch_y: float = 1.0
    pupil_scale: float = 1.0
    glow: float = 0.0


class BaseEyesRenderer:
    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def set_state(self, state: str) -> None:
        return


class EyesRenderer(BaseEyesRenderer):
    def __init__(self, config: Config, enabled: bool = True, windowed: bool = False) -> None:
        self.config = config
        self.enabled = enabled
        self.windowed = windowed
        self._state = "idle"
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        if not self.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="eyes-renderer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def set_state(self, state: str) -> None:
        if state not in EYE_STATES:
            logger.warning("Ignoring unknown eyes state: %s", state)
            return
        with self._lock:
            self._state = state

    def _run(self) -> None:
        import pygame

        pygame.init()
        pygame.display.set_caption("Ameego Eyes")
        flags = pygame.FULLSCREEN if self.config.eyes_fullscreen and not self.windowed else 0
        screen = pygame.display.set_mode((self.config.eyes_width, self.config.eyes_height), flags)
        clock = pygame.time.Clock()

        start_time = time.monotonic()
        blink_until = 0.0
        next_blink_at = start_time + random.uniform(2.5, 5.5)
        look_target = [0.0, 0.0]
        next_look_shift = start_time + 1.2

        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self._stop_event.set()

                with self._lock:
                    state = self._state

                if now >= next_blink_at:
                    blink_until = now + 0.18
                    next_blink_at = now + random.uniform(2.5, 6.0)

                if now >= next_look_shift:
                    look_target = [random.uniform(-0.4, 0.4), random.uniform(-0.18, 0.18)]
                    next_look_shift = now + random.uniform(0.8, 2.2)

                blink = max(0.0, 1.0 - abs((blink_until - now) / 0.09)) if now < blink_until else 0.0
                self._draw(screen, now - start_time, state, blink, look_target)
                pygame.display.flip()
                clock.tick(self.config.eyes_fps)
        finally:
            pygame.quit()

    def _draw(self, screen, elapsed: float, state: str, blink: float, look_target: list[float]) -> None:
        import pygame

        width, height = screen.get_size()
        bg_top = (8, 14, 20)
        bg_bottom = (18, 28, 36)
        self._draw_gradient(screen, bg_top, bg_bottom)

        pose = self._pose_for_state(state, elapsed)
        open_factor = max(0.03, pose.openness * (1.0 - 0.96 * blink))
        micro_x = math.sin(elapsed * 0.7) * 0.02
        micro_y = math.cos(elapsed * 0.9) * 0.015
        target_x = look_target[0] + micro_x
        target_y = look_target[1] + micro_y

        eye_width = width * 0.24 * pose.stretch_x
        eye_height = height * 0.28 * pose.stretch_y * open_factor
        eye_spacing = width * 0.12
        center_y = height * 0.48
        radius = int(min(eye_width, max(eye_height, 8)) * 0.35)
        glow_alpha = min(180, int(70 + 120 * pose.glow))

        centers = [
            (width * 0.5 - eye_spacing, center_y),
            (width * 0.5 + eye_spacing, center_y),
        ]

        for center_x, center_y in centers:
            glow_rect = pygame.Rect(0, 0, int(eye_width * 1.3), int(max(eye_height, 10) * 1.8))
            glow_rect.center = (int(center_x), int(center_y))
            glow_surface = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(glow_surface, (80, 255, 220, glow_alpha), glow_surface.get_rect())
            screen.blit(glow_surface, glow_rect.topleft)

            eye_rect = pygame.Rect(0, 0, int(eye_width), int(max(eye_height, 10)))
            eye_rect.center = (int(center_x), int(center_y))
            pygame.draw.rect(
                screen,
                (210, 255, 248),
                eye_rect,
                border_radius=max(6, radius),
            )

            pupil_offset_x = eye_width * 0.18 * target_x
            pupil_offset_y = eye_height * 0.2 * target_y
            pupil_radius = max(4, int(min(eye_width, max(eye_height, 10)) * 0.12 * pose.pupil_scale))
            pygame.draw.circle(
                screen,
                (6, 18, 26),
                (int(center_x + pupil_offset_x), int(center_y + pupil_offset_y)),
                pupil_radius,
            )

        if state == "error":
            eyebrow_color = (255, 160, 120)
            pygame.draw.line(
                screen,
                eyebrow_color,
                (int(width * 0.22), int(height * 0.28)),
                (int(width * 0.38), int(height * 0.38)),
                8,
            )
            pygame.draw.line(
                screen,
                eyebrow_color,
                (int(width * 0.78), int(height * 0.28)),
                (int(width * 0.62), int(height * 0.38)),
                8,
            )

    def _draw_gradient(self, screen, top_color: tuple[int, int, int], bottom_color: tuple[int, int, int]) -> None:
        import pygame

        width, height = screen.get_size()
        for y in range(height):
            blend = y / max(1, height - 1)
            color = tuple(
                int(top_color[idx] * (1.0 - blend) + bottom_color[idx] * blend)
                for idx in range(3)
            )
            pygame.draw.line(screen, color, (0, y), (width, y))

    def _pose_for_state(self, state: str, elapsed: float) -> EyePose:
        if state == "wake_detected":
            return EyePose(openness=1.18, stretch_x=1.02, stretch_y=1.08, pupil_scale=0.88, glow=0.8)
        if state == "listening":
            return EyePose(openness=1.08, stretch_x=0.98, stretch_y=1.04, pupil_scale=0.92, glow=0.7)
        if state == "thinking":
            sway = 0.05 * math.sin(elapsed * 3.0)
            return EyePose(openness=0.92, stretch_x=1.02 + sway, stretch_y=0.96, pupil_scale=0.95, glow=0.55)
        if state == "speaking":
            bounce = 0.08 * (0.5 + 0.5 * math.sin(elapsed * 9.0))
            return EyePose(openness=0.95 + bounce, stretch_x=1.03, stretch_y=1.0, pupil_scale=0.9, glow=0.9)
        if state == "error":
            return EyePose(openness=0.52, stretch_x=1.08, stretch_y=0.85, pupil_scale=1.1, glow=0.2)
        if state == "sleeping":
            return EyePose(openness=0.25, stretch_x=1.18, stretch_y=0.55, pupil_scale=0.7, glow=0.15)
        return EyePose(openness=1.0, stretch_x=1.0, stretch_y=1.0, pupil_scale=1.0, glow=0.4)
