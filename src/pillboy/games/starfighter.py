import math
import random
import time

from gettext import gettext as _

from pillboy.games.base import GameView
from pillboy.gui.components import Fonts, GUIConstants
from pillboy.gui.screens.screen import ButtonOption, LargeIconStatusScreen
from pillboy.hardware.buttons import HardwareButtonsConstants
from pillboy.views.view import BackStackView, Destination


SHIP_COLOR = "#5ac8ff"
SHIP_TRIM = "#ffffff"
BULLET_COLOR = "#ffe14a"
ENEMY_BULLET_COLOR = "#ff6a6a"
ALIEN_COLORS = ["#ff5ad2", "#8cff5a", "#ffb400"]
ASTEROID_COLOR = "#9a8b7a"
ASTEROID_EDGE = "#5f564c"
BOSS_BODY = "#7a4aff"
BOSS_EDGE = "#c0a8ff"
WEAKPOINT_COLOR = "#ff3232"
WEAKPOINT_DEAD = "#404040"
HUD_COLOR = "#aaaaaa"


class StarFighterGameView(GameView):
    """
        Three-level shooter.

        Level 1 — aliens fly in on curved paths and take formation (Galaga style),
                  then peel off to dive and shoot.
        Level 2 — no aliens: an asteroid field falling from the top. Survive it.
        Level 3 — a wide boss with a laser cannon at each end plus one in the
                  middle; each cannon has a single weak point. Health bar on top.
    """
    FPS = 20

    W = 240
    H = 240
    PLAYER_Y = 214
    PLAYER_HALF = 8
    PLAYER_SPEED = 5
    BULLET_SPEED = 10
    SHOT_COOLDOWN = 0.18
    ENEMY_BULLET_SPEED = 4
    START_LIVES = 3
    INVULN_TIME = 1.5

    HUD_H = 14

    CONTROLS = [
        ("Joystick left/right", "A/D", "move"),
        ("Press stick", "Space", "fire"),
        ("Top button", "U", "fire"),
    ]

    @classmethod
    def render_thumbnail(cls, draw, x, y, w, h):
        cx = x + w // 2
        cy = y + h // 2
        # little ship
        draw.polygon([(cx, cy + 6), (cx - 12, cy + 22), (cx + 12, cy + 22)], fill=SHIP_COLOR)
        draw.rectangle((cx - 2, cy - 10, cx + 2, cy + 2), fill=BULLET_COLOR)
        # two aliens above
        for dx in (-20, 20):
            draw.rectangle((cx + dx - 8, cy - 26, cx + dx + 8, cy - 16), fill=ALIEN_COLORS[0])
            draw.rectangle((cx + dx - 10, cy - 22, cx + dx + 10, cy - 20), fill=ALIEN_COLORS[0])

    # ------------------------------------------------------------------ entry
    def run(self):
        self.wait_for_release()
        while True:
            result = self._play_game()
            if result is not None:
                return result


    def _play_game(self):
        self.score = 0
        self.lives = self.START_LIVES
        self.player_x = self.W // 2

        for level in (1, 2, 3):
            dest = self._banner(_("Level {}").format(level), self._level_subtitle(level))
            if dest:
                return dest
            outcome = self._run_level(level)
            if isinstance(outcome, Destination):
                return outcome            # paused -> quit
            if outcome == "dead":
                return self._end_screen(won=False)

        return self._end_screen(won=True)


    def _level_subtitle(self, level):
        return {
            1: _("Enemy squadron"),
            2: _("Asteroid field"),
            3: _("Battleship"),
        }[level]


    # ------------------------------------------------------------------ level
    def _run_level(self, level):
        """Returns "clear", "dead", or a Destination if the player quit."""
        self.bullets = []          # [x, y]
        self.enemy_bullets = []    # [x, y]
        self.explosions = []       # [x, y, frame]
        self.aliens = []
        self.asteroids = []
        self.boss = None
        self.last_shot = 0.0
        self.invuln_until = time.time() + 1.0
        self.level = level
        self.frame = 0
        self.level_start = time.time()

        if level == 1:
            self._spawn_squadron()
        elif level == 3:
            self._spawn_boss()

        frame_duration = 1.0 / self.FPS

        while True:
            frame_start = time.time()
            self.frame += 1

            dest = self.check_pause_menu()
            if dest:
                return dest

            self._read_input()
            self._update_bullets()

            if level == 1:
                self._update_level1()
            elif level == 2:
                self._update_level2()
            else:
                self._update_level3()

            if self._check_player_hit():
                self.lives -= 1
                self.invuln_until = time.time() + self.INVULN_TIME
                self._boom(self.player_x, self.PLAYER_Y)
                if self.lives <= 0:
                    self._render()
                    time.sleep(0.6)
                    return "dead"

            if self._level_complete(level):
                self._render()
                time.sleep(0.5)
                return "clear"

            with self.renderer.lock:
                self._render()
                self.renderer.show_image()

            elapsed = time.time() - frame_start
            if elapsed < frame_duration:
                time.sleep(frame_duration - elapsed)


    def _level_complete(self, level):
        if level == 1:
            return not self.aliens
        if level == 2:
            return time.time() - self.level_start > 32.0
        return self.boss is not None and all(w["hp"] <= 0 for w in self.boss["weakpoints"])


    # ------------------------------------------------------------------ input
    def _read_input(self):
        K = HardwareButtonsConstants
        if self.buttons.check_for_low(K.KEY_LEFT):
            self.player_x = max(self.PLAYER_HALF + 2, self.player_x - self.PLAYER_SPEED)
        if self.buttons.check_for_low(K.KEY_RIGHT):
            self.player_x = min(self.W - self.PLAYER_HALF - 2, self.player_x + self.PLAYER_SPEED)

        firing = self.buttons.check_for_low(keys=[K.KEY_PRESS, K.KEY1])
        now = time.time()
        if firing and now - self.last_shot >= self.SHOT_COOLDOWN:
            self.last_shot = now
            self.bullets.append([self.player_x, self.PLAYER_Y - 10])


    def _update_bullets(self):
        for b in self.bullets:
            b[1] -= self.BULLET_SPEED
        self.bullets = [b for b in self.bullets if b[1] > self.HUD_H]

        for b in self.enemy_bullets:
            b[1] += self.ENEMY_BULLET_SPEED
        self.enemy_bullets = [b for b in self.enemy_bullets if b[1] < self.H]

        self.explosions = [[x, y, f + 1] for (x, y, f) in self.explosions if f < 6]


    def _boom(self, x, y):
        self.explosions.append([x, y, 0])


    # ------------------------------------------- level 1: galaga-style squadron
    def _spawn_squadron(self):
        cols, rows = 6, 3
        margin = 26
        spacing = (self.W - 2 * margin) / (cols - 1)
        now = time.time()

        for row in range(rows):
            for col in range(cols):
                slot_x = margin + col * spacing
                slot_y = 40 + row * 24
                # Alternate entry side; stagger arrival so they trickle in
                from_left = (row + col) % 2 == 0
                start_x = -20 if from_left else self.W + 20
                start_y = 30 + 18 * (col % 3)
                ctrl_x = 40 if from_left else self.W - 40
                ctrl_y = self.H * 0.75
                delay = 0.25 * (row * cols + col) + random.uniform(0, 0.12)

                self.aliens.append({
                    "state": "entering",
                    "t": 0.0,
                    "delay": now + delay,
                    "start": (start_x, start_y),
                    "ctrl": (ctrl_x, ctrl_y),
                    "slot": (slot_x, slot_y),
                    "x": start_x,
                    "y": start_y,
                    "color": ALIEN_COLORS[row % len(ALIEN_COLORS)],
                    "dive_t": 0.0,
                    "dive_from": (0, 0),
                })


    def _update_level1(self):
        now = time.time()
        sway = math.sin(now * 1.1) * 12

        for a in self.aliens:
            if a["state"] == "entering":
                if now < a["delay"]:
                    continue
                a["t"] = min(1.0, a["t"] + 0.022)
                # Quadratic bezier from off-screen, through a control point, to the slot
                t = a["t"]
                sx, sy = a["start"]
                cx, cy = a["ctrl"]
                gx, gy = a["slot"]
                inv = 1 - t
                a["x"] = inv * inv * sx + 2 * inv * t * cx + t * t * gx
                a["y"] = inv * inv * sy + 2 * inv * t * cy + t * t * gy
                if t >= 1.0:
                    a["state"] = "formation"

            elif a["state"] == "formation":
                a["x"] = a["slot"][0] + sway
                a["y"] = a["slot"][1]

            elif a["state"] == "diving":
                a["dive_t"] += 0.028
                t = a["dive_t"]
                fx, fy = a["dive_from"]
                # Swoop down in a sine weave, then wrap around to the top
                a["x"] = fx + math.sin(t * 6.0) * 55
                a["y"] = fy + t * 240
                if random.random() < 0.03:
                    self.enemy_bullets.append([a["x"], a["y"] + 8])
                if a["y"] > self.H + 10:
                    a["state"] = "formation"
                    a["dive_t"] = 0.0

        # Occasionally send a formation alien on a dive
        settled = [a for a in self.aliens if a["state"] == "formation"]
        if settled and random.random() < 0.02:
            a = random.choice(settled)
            a["state"] = "diving"
            a["dive_t"] = 0.0
            a["dive_from"] = (a["x"], a["y"])

        # Formation aliens take pot shots
        if settled and random.random() < 0.04:
            shooter = random.choice(settled)
            self.enemy_bullets.append([shooter["x"], shooter["y"] + 8])

        # Player bullets vs aliens
        for b in self.bullets[:]:
            for a in self.aliens:
                if abs(b[0] - a["x"]) < 10 and abs(b[1] - a["y"]) < 9:
                    self.bullets.remove(b)
                    self.aliens.remove(a)
                    self._boom(a["x"], a["y"])
                    self.score += 100 if a["state"] == "diving" else 50
                    break


    # ------------------------------------------------ level 2: asteroid field
    def _update_level2(self):
        # Spawn rate ramps up over the level. Kept deliberately sparse early on:
        # at ~0.2/frame the field becomes an unavoidable wall rather than a
        # dodging challenge (a stationary ship died within seconds in testing).
        elapsed = time.time() - self.level_start
        spawn_chance = 0.045 + min(0.075, elapsed * 0.0032)
        if random.random() < spawn_chance:
            big = random.random() < 0.45
            r = random.randint(9, 13) if big else random.randint(5, 7)
            self.asteroids.append({
                "x": random.randint(r + 2, self.W - r - 2),
                "y": self.HUD_H - r,
                "vx": random.uniform(-0.8, 0.8),
                "vy": random.uniform(1.6, 3.0) + min(1.5, elapsed * 0.05),
                "r": r,
                "hp": 2 if big else 1,
                "spin": random.uniform(-0.15, 0.15),
                "angle": random.uniform(0, 6.28),
            })

        for a in self.asteroids:
            a["x"] += a["vx"]
            a["y"] += a["vy"]
            a["angle"] += a["spin"]
            if a["x"] < a["r"] or a["x"] > self.W - a["r"]:
                a["vx"] *= -1
        self.asteroids = [a for a in self.asteroids if a["y"] < self.H + 20]

        # Bullets chip away at asteroids; big ones split
        for b in self.bullets[:]:
            for a in self.asteroids[:]:
                if (b[0] - a["x"]) ** 2 + (b[1] - a["y"]) ** 2 < (a["r"] + 3) ** 2:
                    if b in self.bullets:
                        self.bullets.remove(b)
                    a["hp"] -= 1
                    if a["hp"] <= 0:
                        self.asteroids.remove(a)
                        self._boom(a["x"], a["y"])
                        self.score += 25
                        if a["r"] >= 9:
                            for direction in (-1, 1):
                                self.asteroids.append({
                                    "x": a["x"], "y": a["y"],
                                    "vx": direction * random.uniform(0.8, 1.6),
                                    "vy": a["vy"] * 0.9,
                                    "r": 6, "hp": 1,
                                    "spin": random.uniform(-0.2, 0.2),
                                    "angle": 0.0,
                                })
                    break


    # ---------------------------------------------------------- level 3: boss
    def _spawn_boss(self):
        self.boss = {
            "x": self.W // 2,
            "y": -30,
            "w": 132,
            "h": 34,
            "entering": True,
            "weakpoints": [
                # dx is offset from boss centre; each cannon has one weak spot
                {"dx": -52, "hp": 6, "max": 6, "cooldown": 0.0},
                {"dx": 0, "hp": 8, "max": 8, "cooldown": 0.0},
                {"dx": 52, "hp": 6, "max": 6, "cooldown": 0.0},
            ],
        }

    def _update_level3(self):
        boss = self.boss
        now = time.time()

        if boss["entering"]:
            boss["y"] += 2
            if boss["y"] >= 48:
                boss["y"] = 48
                boss["entering"] = False
        else:
            boss["x"] = self.W // 2 + math.sin(now * 0.7) * 46

        alive = [w for w in boss["weakpoints"] if w["hp"] > 0]

        # Each surviving cannon fires on its own cadence; fewer left = angrier
        for w in alive:
            if now >= w["cooldown"]:
                w["cooldown"] = now + random.uniform(0.7, 1.8) * (0.6 + 0.2 * len(alive))
                gx = boss["x"] + w["dx"]
                gy = boss["y"] + boss["h"] // 2
                self.enemy_bullets.append([gx, gy])

        # Bullets only hurt the weak points; the hull shrugs them off
        for b in self.bullets[:]:
            hit_hull = (abs(b[0] - boss["x"]) < boss["w"] // 2
                        and abs(b[1] - boss["y"]) < boss["h"] // 2)
            for w in boss["weakpoints"]:
                if w["hp"] <= 0:
                    continue
                wx = boss["x"] + w["dx"]
                wy = boss["y"] + boss["h"] // 2 - 2
                if (b[0] - wx) ** 2 + (b[1] - wy) ** 2 < 64:
                    if b in self.bullets:
                        self.bullets.remove(b)
                    w["hp"] -= 1
                    self._boom(wx, wy)
                    self.score += 50
                    if w["hp"] <= 0:
                        self.score += 250
                    hit_hull = False
                    break
            if hit_hull and b in self.bullets:
                self.bullets.remove(b)
                self._boom(b[0], b[1])


    # ------------------------------------------------------------ collisions
    def _check_player_hit(self) -> bool:
        if time.time() < self.invuln_until:
            return False

        px, py = self.player_x, self.PLAYER_Y
        for b in self.enemy_bullets:
            if abs(b[0] - px) < 8 and abs(b[1] - py) < 9:
                self.enemy_bullets.remove(b)
                return True

        for a in self.aliens:
            if abs(a["x"] - px) < 12 and abs(a["y"] - py) < 11:
                self._boom(a["x"], a["y"])
                self.aliens.remove(a)
                return True

        for a in self.asteroids:
            if (a["x"] - px) ** 2 + (a["y"] - py) ** 2 < (a["r"] + 8) ** 2:
                self.asteroids.remove(a)
                return True

        return False


    # ---------------------------------------------------------------- render
    def _render(self):
        draw = self.renderer.draw
        draw.rectangle((0, 0, self.W, self.H), fill="black")

        # Starfield: cheap parallax from a deterministic pattern
        for i in range(18):
            sx = (i * 53) % self.W
            sy = (i * 37 + self.frame * (1 + i % 3)) % (self.H - self.HUD_H) + self.HUD_H
            draw.point((sx, sy), fill="#404040" if i % 3 else "#707070")

        for (x, y, f) in self.explosions:
            r = 3 + f * 2
            color = "#ffdd55" if f < 3 else "#ff7733"
            draw.ellipse((x - r, y - r, x + r, y + r), outline=color)

        if self.level == 1:
            for a in self.aliens:
                self._draw_alien(draw, a)
        elif self.level == 2:
            for a in self.asteroids:
                self._draw_asteroid(draw, a)
        elif self.boss:
            self._draw_boss(draw)

        for b in self.bullets:
            draw.rectangle((b[0] - 1, b[1] - 5, b[0] + 1, b[1] + 1), fill=BULLET_COLOR)
        for b in self.enemy_bullets:
            draw.rectangle((b[0] - 1, b[1] - 1, b[0] + 1, b[1] + 5), fill=ENEMY_BULLET_COLOR)

        # Player (blinks while invulnerable)
        if time.time() >= self.invuln_until or self.frame % 4 < 2:
            self._draw_ship(draw, self.player_x, self.PLAYER_Y)

        self._draw_hud(draw)


    def _draw_ship(self, draw, x, y):
        h = self.PLAYER_HALF
        draw.polygon([(x, y - 10), (x - h, y + 6), (x + h, y + 6)], fill=SHIP_COLOR)
        draw.polygon([(x, y - 4), (x - 3, y + 4), (x + 3, y + 4)], fill=SHIP_TRIM)
        draw.rectangle((x - h - 2, y + 2, x - h + 1, y + 7), fill=SHIP_COLOR)
        draw.rectangle((x + h - 1, y + 2, x + h + 2, y + 7), fill=SHIP_COLOR)


    def _draw_alien(self, draw, a):
        x, y, color = a["x"], a["y"], a["color"]
        draw.rectangle((x - 7, y - 4, x + 7, y + 4), fill=color)
        draw.rectangle((x - 9, y - 1, x + 9, y + 1), fill=color)
        draw.rectangle((x - 3, y - 6, x + 3, y - 4), fill=color)
        draw.point((x - 3, y - 1), fill="black")
        draw.point((x + 3, y - 1), fill="black")


    def _draw_asteroid(self, draw, a):
        r = a["r"]
        pts = []
        for i in range(7):
            ang = a["angle"] + i * (6.283 / 7)
            rr = r * (0.78 if i % 2 else 1.0)
            pts.append((a["x"] + math.cos(ang) * rr, a["y"] + math.sin(ang) * rr))
        draw.polygon(pts, fill=ASTEROID_COLOR, outline=ASTEROID_EDGE)


    def _draw_boss(self, draw):
        boss = self.boss
        x, y = boss["x"], boss["y"]
        hw, hh = boss["w"] // 2, boss["h"] // 2

        draw.polygon([(x - hw, y), (x - hw + 18, y - hh), (x + hw - 18, y - hh),
                      (x + hw, y), (x + hw - 10, y + hh), (x - hw + 10, y + hh)],
                     fill=BOSS_BODY, outline=BOSS_EDGE)
        draw.rectangle((x - 26, y - hh + 4, x + 26, y - 2), fill="#1a1030", outline=BOSS_EDGE)

        for w in boss["weakpoints"]:
            wx = x + w["dx"]
            wy = y + hh - 2
            # cannon barrel
            draw.rectangle((wx - 5, wy - 2, wx + 5, wy + 8),
                           fill=BOSS_BODY if w["hp"] > 0 else "#2a2a2a", outline=BOSS_EDGE)
            # the weak point itself
            color = WEAKPOINT_COLOR if w["hp"] > 0 else WEAKPOINT_DEAD
            r = 5 if w["hp"] > 0 else 3
            draw.ellipse((wx - r, wy - r, wx + r, wy + r), fill=color)
            if w["hp"] > 0 and self.frame % 8 < 4:
                draw.ellipse((wx - r - 2, wy - r - 2, wx + r + 2, wy + r + 2), outline="#ffaaaa")

        # Boss health bar under the HUD
        total = sum(w["max"] for w in boss["weakpoints"])
        left = sum(max(0, w["hp"]) for w in boss["weakpoints"])
        bar_w = self.W - 20
        draw.rectangle((10, self.HUD_H + 3, 10 + bar_w, self.HUD_H + 9),
                       outline="#666666", fill="#1a1a1a")
        if left:
            draw.rectangle((10, self.HUD_H + 3, 10 + int(bar_w * left / total), self.HUD_H + 9),
                           fill=WEAKPOINT_COLOR)


    def _draw_hud(self, draw):
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 12)
        draw.rectangle((0, 0, self.W, self.HUD_H), fill="black")
        draw.text((4, self.HUD_H // 2), _("Score {}").format(self.score),
                  font=font, fill=HUD_COLOR, anchor="lm")
        draw.text((self.W // 2, self.HUD_H // 2), _("L{}").format(self.level),
                  font=font, fill=HUD_COLOR, anchor="mm")
        for i in range(self.lives):
            lx = self.W - 8 - i * 12
            draw.polygon([(lx, 3), (lx - 4, 11), (lx + 4, 11)], fill=SHIP_COLOR)

        if self.level == 2:
            remaining = max(0, 32.0 - (time.time() - self.level_start))
            draw.text((self.W - 60, self.HUD_H // 2), _("{}s").format(int(remaining)),
                      font=font, fill=HUD_COLOR, anchor="rm")


    # ---------------------------------------------------------------- screens
    def _banner(self, title, subtitle):
        """Brief level card. Returns a Destination if the player quit."""
        title_font = Fonts.get_font(GUIConstants.get_top_nav_title_font_name(), 24)
        sub_font = Fonts.get_font(GUIConstants.get_body_font_name(), 15)
        until = time.time() + 1.6

        while time.time() < until:
            dest = self.check_pause_menu()
            if dest:
                return dest
            with self.renderer.lock:
                draw = self.renderer.draw
                draw.rectangle((0, 0, self.W, self.H), fill="black")
                draw.text((self.W // 2, self.H // 2 - 16), title,
                          font=title_font, fill=GUIConstants.ACCENT_COLOR, anchor="mm")
                draw.text((self.W // 2, self.H // 2 + 14), subtitle,
                          font=sub_font, fill="#aaaaaa", anchor="mm")
                self.renderer.show_image()
            time.sleep(0.05)
        return None


    def _end_screen(self, won: bool):
        self.wait_for_release()
        AGAIN = ButtonOption("Play again")
        QUIT = ButtonOption("Quit")
        button_data = [AGAIN, QUIT]
        selected = self.run_screen(
            LargeIconStatusScreen,
            title=_("Victory!") if won else _("Game Over"),
            status_headline=_("Score: {}").format(self.score),
            text=_("The galaxy is safe.") if won else _("Your ship was destroyed."),
            button_data=button_data,
            show_back_button=False,
        )
        if button_data[selected] == AGAIN:
            self.wait_for_release()
            return None
        return Destination(BackStackView)
