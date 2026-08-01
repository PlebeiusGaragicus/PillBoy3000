import time

from pillboy.games.base import GameView
from pillboy.hardware.buttons import HardwareButtonsConstants


class BounceGameView(GameView):
    """
        Minimal proof-of-life "game": a ball bounces around the screen; steer it with
        the joystick. Press all three side buttons together to pause / quit.
    """
    FPS = 30
    BALL_RADIUS = 10
    STEER_ACCEL = 1.5

    CONTROLS = [
        ("Joystick", "WASD", "steer the ball"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        r = min(w, h) // 4
        cx = x + w // 2
        cy = y + h // 2
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill="orange")

    def run(self):
        # The button press that launched the game is likely still held down; wait for
        # a clean release so it isn't misread as gameplay input.
        self.wait_for_release()

        x = self.canvas_width / 2
        y = self.canvas_height / 2
        dx, dy = 3.0, 2.0

        frame_duration = 1.0 / self.FPS

        while True:
            frame_start = time.time()

            dest = self.check_pause_menu()
            if dest:
                return dest

            if self.buttons.check_for_low(HardwareButtonsConstants.KEY_LEFT):
                dx -= self.STEER_ACCEL
            if self.buttons.check_for_low(HardwareButtonsConstants.KEY_RIGHT):
                dx += self.STEER_ACCEL
            if self.buttons.check_for_low(HardwareButtonsConstants.KEY_UP):
                dy -= self.STEER_ACCEL
            if self.buttons.check_for_low(HardwareButtonsConstants.KEY_DOWN):
                dy += self.STEER_ACCEL

            # Clamp speed so steering can't run away
            dx = max(-8.0, min(8.0, dx))
            dy = max(-8.0, min(8.0, dy))

            x += dx
            y += dy

            if x - self.BALL_RADIUS < 0:
                x = self.BALL_RADIUS
                dx = abs(dx)
            elif x + self.BALL_RADIUS > self.canvas_width:
                x = self.canvas_width - self.BALL_RADIUS
                dx = -abs(dx)

            if y - self.BALL_RADIUS < 0:
                y = self.BALL_RADIUS
                dy = abs(dy)
            elif y + self.BALL_RADIUS > self.canvas_height:
                y = self.canvas_height - self.BALL_RADIUS
                dy = -abs(dy)

            with self.renderer.lock:
                self.renderer.draw.rectangle(
                    (0, 0, self.canvas_width, self.canvas_height), fill="black")
                self.renderer.draw.ellipse(
                    (x - self.BALL_RADIUS, y - self.BALL_RADIUS,
                     x + self.BALL_RADIUS, y + self.BALL_RADIUS),
                    fill="orange")
                self.renderer.show_image()

            elapsed = time.time() - frame_start
            if elapsed < frame_duration:
                time.sleep(frame_duration - elapsed)
