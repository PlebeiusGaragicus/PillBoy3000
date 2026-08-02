"""
    Star Saver — ported from the 2023 PillBoy card
    (`modules/games/star_saver/`), including its original PNG artwork.

    A power-economy shooter: everything you do costs power, and power is also
    your health. Shooting spends it, dashing sideways spends it, enemy hits
    take a chunk, and pink gems drifting down are the only way to get it back.
    Run the bar to zero and it's over.

    Two shots: a cheap pink pellet (middle button) and an expensive gold slug
    (bottom button) that does more damage per hit.

    Deviations from the 2023 original, all deliberate:

      * Asteroids graze the ship for 3 power. In the original they were drawn
        and fell but never collided with anything, leaving the rare enemies as
        the only threat. Their 1-5px size and fall speed are unchanged.
      * Enemy collision uses a proper box overlap. The original tested whether
        either of the ship's side edges sat inside the enemy's width, which
        misses entirely when the enemy is narrower than the ship — a bug its
        author had already flagged with a TODO.
      * Enemies spawn fully on-screen (the original could spawn one mostly off
        the right edge).
      * Lists are copied before removal; the original mutated while iterating,
        which silently skipped entries.

    Gem pickup and bomb-vs-enemy hit boxes are bit-for-bit the original's.
"""
import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.games.palette import (BRIGHT_GOLD, BRIGHT_PINK, DARK_BROWN,
                                   DARK_DEEP_PINK, DEEP_PINK, LIGHT_GOLD,
                                   lerp, load_sprite)
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.gui.screens.screen import ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination


SCREEN = 240
SLOW_MOVE = 6
FAST_MOVE = 14
SHOT_COOLDOWN = 0.18
SHOT_SPEED = 14
LITTLE_SHOT_POWER = 2
BIG_SHOT_POWER = 5


class Asteroid:
    # Original sizing: 1-5px specks that fall at `size` px per frame.
    def __init__(self):
        self.size = random.randint(1, 5)
        self.x = random.randint(0, SCREEN - self.size)
        self.y = 0
        self.speed = self.size

    def draw(self, draw):
        draw.ellipse((self.x, self.y, self.x + self.size, self.y + self.size),
                     fill=DARK_BROWN)

    def update(self) -> bool:
        self.y += self.speed
        return self.y > SCREEN


class Bomb:
    def __init__(self, x, y, power):
        self.x = x
        self.y = y
        self.power = power
        self.width, self.height = (2, 10) if power == LITTLE_SHOT_POWER else (4, 11)

    def draw(self, draw):
        draw.rectangle((self.x, self.y, self.x + self.width, self.y + self.height),
                       fill=DEEP_PINK if self.power == LITTLE_SHOT_POWER else BRIGHT_GOLD)

    def update(self) -> bool:
        self.y -= SHOT_SPEED
        return self.y < -10


class PowerGem:
    def __init__(self):
        self.x = random.randint(0, SCREEN - 6)
        self.y = -6

    def draw(self, draw):
        draw.ellipse((self.x, self.y, self.x + 4, self.y + 4), fill=BRIGHT_PINK)

    def update(self) -> bool:
        self.y += 5
        return self.y > SCREEN


class Enemy:
    def __init__(self, sprite):
        self.image = sprite
        self.x = random.randint(0, SCREEN - sprite.width)
        self.y = -sprite.height
        self.health = LITTLE_SHOT_POWER * 3.1

    def draw(self, canvas):
        canvas.paste(self.image, (int(self.x), int(self.y)), self.image)

    def update(self) -> bool:
        self.y += 5
        return self.y > SCREEN


class PowerBar:
    """Doubles as the health bar; colour lerps pink (empty) to gold (full)."""
    def __init__(self, x, y, width, height, max_power=100):
        self.x, self.y = x, y
        self.width, self.height = width, height
        self.max_power = max_power
        self._power = 98

    @property
    def power(self):
        return self._power

    @power.setter
    def power(self, value):
        self._power = max(0, min(self.max_power, value))

    def change(self, delta):
        self.power = self.power + delta

    def draw(self, draw):
        t = self.power / self.max_power
        color = lerp(DEEP_PINK, BRIGHT_GOLD, t)
        outline = lerp(DARK_DEEP_PINK, LIGHT_GOLD, t)
        draw.rectangle((self.x, self.y, self.x + self.width, self.y + self.height),
                       fill=color, outline=outline)
        draw.rectangle((self.x + 2, self.y + 2,
                        self.x + self.width - 2, self.y + self.height - 2),
                       fill=(0, 0, 0), outline=(0, 0, 0))
        draw.rectangle((self.x + 2, self.y + 2,
                        self.x + 2 + (self.width - 4) * t, self.y + self.height - 2),
                       fill=color, outline=BRIGHT_GOLD)


class StarSaverGameView(GameView):
    FPS = 20

    CONTROLS = [
        ("Joystick", "WASD", "fly"),
        ("Press stick + L/R", "Space+A/D", "dash (costs power)"),
        ("Middle button", "J", "small shot"),
        ("Bottom button", "M", "big shot"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        # Drawn rather than blitted: thumbnails only get a `draw` handle
        cx = x + w // 2
        cy = y + h // 2
        draw.polygon([(cx, cy - 16), (cx - 12, cy + 12), (cx + 12, cy + 12)],
                     fill="#8fa9c8")
        draw.rectangle((cx - 3, cy - 26, cx + 3, cy - 14), fill=DEEP_PINK)
        draw.ellipse((cx - 26, cy + 2, cx - 14, cy + 14), fill=DARK_BROWN)
        draw.ellipse((cx + 16, cy - 12, cx + 26, cy - 2), fill=DARK_BROWN)

    def run(self):
        self.wait_for_release()
        self.ship = load_sprite("ship_tiny.png")
        # Full size, as the original used it: a 55x72 enemy is deliberately
        # imposing on a 240x240 screen.
        self.enemy_sprite = load_sprite("enemy.png")

        while True:
            result = self._play_round()
            if result is not None:
                return result

    def _play_round(self):
        self.power_bar = PowerBar(2, SCREEN - 14, 236, 10)
        self.hero_x = SCREEN // 2 - self.ship.width // 2
        self.hero_y = int(SCREEN * 0.80 - self.ship.height / 2)
        self.bombs = []
        self.asteroids = []
        self.gems = []
        self.enemies = []
        self.last_shot = None
        self.score = 0

        frame_duration = 1.0 / self.FPS
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 13)

        while True:
            frame_start = time.time()

            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()
            self._update()

            if self.power_bar.power <= 0:
                return self._game_over_screen()

            with self.renderer.lock:
                self._render(font)
                self.renderer.show_image()

            elapsed = time.time() - frame_start
            if elapsed < frame_duration:
                time.sleep(frame_duration - elapsed)

    def _update(self):
        if random.randint(0, 100) < 10:
            self.asteroids.append(Asteroid())
        if random.randint(0, 100) < 2:
            self.gems.append(PowerGem())
        if len(self.enemies) < 2 and random.randint(0, 100) < 2:
            self.enemies.append(Enemy(self.enemy_sprite))

        hero_w, hero_h = self.ship.width, self.ship.height

        for g in self.gems[:]:
            if (self.hero_x < g.x < self.hero_x + hero_w
                    and self.hero_y < g.y < self.hero_y + hero_h):
                self.power_bar.change(10)
                self.gems.remove(g)

        for e in self.enemies[:]:
            overlap_x = (e.x < self.hero_x + hero_w and self.hero_x < e.x + e.image.width)
            overlap_y = (e.y < self.hero_y + hero_h and self.hero_y < e.y + e.image.height)
            if overlap_x and overlap_y:
                self.power_bar.change(-25)
                self.enemies.remove(e)

        # Asteroid grazes (see module docstring: not in the 2023 original)
        for a in self.asteroids[:]:
            overlap_x = (a.x < self.hero_x + hero_w and self.hero_x < a.x + a.size)
            overlap_y = (a.y < self.hero_y + hero_h and self.hero_y < a.y + a.size)
            if overlap_x and overlap_y:
                self.power_bar.change(-3)
                self.asteroids.remove(a)

        for e in self.enemies[:]:
            for b in self.bombs[:]:
                if (e.x <= b.x <= e.x + e.image.width
                        and e.y <= b.y <= e.y + e.image.height):
                    e.health -= b.power
                    self.bombs.remove(b)
                    if e.health <= 0:
                        self.enemies.remove(e)
                        self.score += 10
                        break

    def _read_input(self):
        K = HardwareButtonsConstants
        dashing = self.buttons.check_for_low(K.KEY_PRESS)

        if self.buttons.check_for_low(K.KEY_DOWN):
            self.hero_y += SLOW_MOVE
        if self.buttons.check_for_low(K.KEY_UP):
            self.hero_y -= SLOW_MOVE
        if self.buttons.check_for_low(K.KEY_LEFT):
            self.hero_x -= FAST_MOVE if dashing else SLOW_MOVE
            if dashing:
                self.power_bar.change(-1)
        if self.buttons.check_for_low(K.KEY_RIGHT):
            self.hero_x += FAST_MOVE if dashing else SLOW_MOVE
            if dashing:
                self.power_bar.change(-1)

        self.hero_x = max(0, min(SCREEN - self.ship.width, self.hero_x))
        self.hero_y = max(0, min(SCREEN - self.ship.height - self.power_bar.height - 4,
                                 self.hero_y))

        now = time.monotonic()
        ready = self.last_shot is None or now - self.last_shot > SHOT_COOLDOWN
        if ready:
            if self.buttons.check_for_low(K.KEY2) and self.power_bar.power > LITTLE_SHOT_POWER:
                self._fire(LITTLE_SHOT_POWER, now, points=1)
            elif self.buttons.check_for_low(K.KEY3) and self.power_bar.power > BIG_SHOT_POWER:
                self._fire(BIG_SHOT_POWER, now, points=3)

    def _fire(self, power, now, points):
        self.last_shot = now
        self.score += points
        self.bombs.append(Bomb(self.hero_x + self.ship.width / 2 + 1, self.hero_y, power))
        self.power_bar.change(-power)

    def _render(self, font):
        canvas = self.renderer.canvas
        draw = self.renderer.draw
        draw.rectangle((0, 0, SCREEN, SCREEN), fill="black")

        for group in (self.asteroids, self.gems, self.bombs):
            for obj in group[:]:
                obj.draw(draw)
                if obj.update():
                    group.remove(obj)

        for e in self.enemies[:]:
            e.draw(canvas)
            if e.update():
                self.enemies.remove(e)

        canvas.paste(self.ship, (int(self.hero_x), int(self.hero_y)), self.ship)
        self.power_bar.draw(draw)
        draw.text((4, 4), str(self.score), font=font, fill="white", anchor="lt")

    def _game_over_screen(self):
        self.wait_for_release()
        AGAIN = ButtonOption("Play again")
        QUIT = ButtonOption("Quit")
        button_data = [AGAIN, QUIT]
        selected = self.run_screen(
            LargeIconStatusScreen,
            title=_("Out of power"),
            status_headline=_("Score: {}").format(self.score),
            text=_("Collect pink gems to stay alive."),
            button_data=button_data,
            show_back_button=False,
        )
        if button_data[selected] == AGAIN:
            self.wait_for_release()
            return None
        return Destination(BackStackView)
