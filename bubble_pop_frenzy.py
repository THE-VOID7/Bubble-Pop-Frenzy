"""
╔══════════════════════════════════════════════════════╗
║         🫧  BUBBLE POP FRENZY  🫧                    ║
║         Python + Pygame + OpenCV                     ║
# ╠══════════════════════════════════════════════════════╣
# ║  Install once:                                       ║
# ║    pip install pygame-ce opencv-python             ║
# ║                                                      ║
# ║  Run:                                                ║
║    python bubble_pop_frenzy.py                       ║
║                                                      ║
║  Controls:                                           ║
║   CAMERA  → move head left/right to aim              ║
║           → nod DOWN to shoot                        ║
║   KEYBOARD → ← → Arrow keys to aim                  ║
║           → SPACE to shoot                           ║
║   MOUSE   → move to aim, click to shoot              ║
╚══════════════════════════════════════════════════════╝
"""

import sys, math, random, time
import pygame
import cv2
import numpy as np

# ── Try to import mediapipe (optional – falls back to motion tracking) ──────
try:
    import mediapipe as mp
    MEDIAPIPE = True
except ImportError:
    MEDIAPIPE = False

# ════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════════════
W, H         = 700, 580
CAM_W, CAM_H = 200, 150
FPS          = 60
BUBBLE_R     = 22
BULLET_SPEED = 9
SHOOT_CD     = 0.38   # seconds

COLORS = [
    (255, 111, 216),  # pink
    (255, 219, 109),  # yellow
    (109, 255, 245),  # cyan
    (167, 139, 250),  # purple
    (255, 140, 109),  # orange
    (109, 255, 179),  # green
]


BG_DARK  = (13, 1, 32)
BG_MID   = (26, 5, 51)
RED_LINE = H - 70

# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════
def lerp(a, b, t): return a + (b - a) * t

def circle_surf(radius, color, alpha=255, glow=False):
    """Return a surface with a glossy bubble."""
    size = radius * 2 + 4
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    # base fill
    pygame.draw.circle(s, (*color, min(alpha, 200)), (cx, cy), radius)
    # rim
    pygame.draw.circle(s, (*color, 180), (cx, cy), radius, 3)
    # shine
    shine_r = max(4, radius // 4)
    shine_x = cx - radius // 3
    shine_y = cy - radius // 3
    pygame.draw.circle(s, (255, 255, 255, 180), (shine_x, shine_y), shine_r)
    pygame.draw.circle(s, (255, 255, 255, 80),  (shine_x, shine_y), shine_r + 3)
    return s

# ════════════════════════════════════════════════════════════════════════════
#  PARTICLE
# ════════════════════════════════════════════════════════════════════════════
class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(2, 7)
        self.x, self.y   = float(x), float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color        = color
        self.life         = 1.0
        self.decay        = random.uniform(0.025, 0.05)
        self.r            = random.randint(3, 7)

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.18
        self.life -= self.decay

    def draw(self, screen):
        if self.life <= 0: return
        alpha = int(self.life * 220)
        r     = max(1, int(self.r * self.life))
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (r, r), r)
        screen.blit(s, (int(self.x)-r, int(self.y)-r))

# ════════════════════════════════════════════════════════════════════════════
#  FLOATY TEXT
# ════════════════════════════════════════════════════════════════════════════
class Floaty:
    def __init__(self, x, y, text, color, font):
        self.x, self.y = float(x), float(y)
        self.text  = text
        self.color = color
        self.font  = font
        self.life  = 1.0

    def update(self): self.y -= 1.4; self.life -= 0.022

    def draw(self, screen):
        if self.life <= 0: return
        alpha = int(self.life * 255)
        surf  = self.font.render(self.text, True, self.color)
        surf.set_alpha(alpha)
        screen.blit(surf, (int(self.x) - surf.get_width()//2, int(self.y)))

# ════════════════════════════════════════════════════════════════════════════
#  BUBBLE
# ════════════════════════════════════════════════════════════════════════════
class Bubble:
    def __init__(self, level):
        self.x     = random.randint(BUBBLE_R + 20, W - 220 - BUBBLE_R - 10)
        self.y     = -BUBBLE_R
        self.color = random.choice(COLORS)
        self.r     = BUBBLE_R
        self.vy    = 0.75 + level * 0.2
        self.phase = random.uniform(0, math.tau)
        self.wx    = self.x
        self._surf = circle_surf(self.r, self.color)

    def update(self, t):
        self.y  += self.vy
        self.wx  = self.x + math.sin(self.phase + t * 2) * 4

    def draw(self, screen):
        sx = int(self.wx) - self.r - 2
        sy = int(self.y)  - self.r - 2
        screen.blit(self._surf, (sx, sy))

# ════════════════════════════════════════════════════════════════════════════
#  BULLET
# ════════════════════════════════════════════════════════════════════════════
class Bullet:
    R = 9
    def __init__(self, x, y, color):
        self.x, self.y = float(x), float(y)
        self.color = color
        self._surf = circle_surf(self.R, color)

    def update(self): self.y -= BULLET_SPEED

    def draw(self, screen):
        screen.blit(self._surf, (int(self.x)-self.R-2, int(self.y)-self.R-2))

# ════════════════════════════════════════════════════════════════════════════
#  SHOOTER
# ════════════════════════════════════════════════════════════════════════════
class Shooter:
    WIDTH, HEIGHT = 60, 30

    def __init__(self):
        self.x  = (W - 220) / 2
        self.tx = self.x

    def move_toward(self, tx):
        self.tx = max(self.WIDTH//2 + 5, min(W - 220 - self.WIDTH//2 - 5, tx))

    def update(self):
        self.x = lerp(self.x, self.tx, 0.18)

    def draw(self, screen, shoot_color, next_color):
        x, y = int(self.x), H - 45
        # base
        body = pygame.Rect(x - self.WIDTH//2, y, self.WIDTH, self.HEIGHT)
        pygame.draw.rect(screen, (42, 10, 74), body, border_radius=10)
        pygame.draw.rect(screen, (80, 40, 120), body, width=2, border_radius=10)
        # barrel
        pygame.draw.line(screen, shoot_color, (x, y-2), (x, y-20), 6)
        pygame.draw.line(screen, (255,255,255), (x, y-2), (x, y-20), 2)
        # current color orb
        pygame.draw.circle(screen, shoot_color, (x-12, y+15), 11)
        pygame.draw.circle(screen, (255,255,255), (x-12, y+15), 5)
        # next color dot
        pygame.draw.circle(screen, next_color,   (x+18, y+15), 7)
        pygame.draw.circle(screen, (200,200,200),(x+18, y+15), 7, 2)

# ════════════════════════════════════════════════════════════════════════════
#  CAMERA TRACKER  (works with or without MediaPipe)
# ════════════════════════════════════════════════════════════════════════════
class CameraTracker:
    def __init__(self):
        self.cap       = None
        self.active    = False
        self.nose_x    = 0.5      # 0..1 normalised, mirrored
        self.nod       = False    # True when downward nod detected
        self.prev_nose_y   = None
        self.nod_cooldown  = 0.0
        self.frame_rgb     = None  # latest frame for display (RGB, 200x150)

        # MediaPipe setup
        self.mp_face = None
        self.mp_mesh = None
        if MEDIAPIPE:
            try:
                mp_fm = mp.solutions.face_mesh
                self.mp_mesh = mp_fm.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self.mp_face = True
            except Exception:
                self.mp_face = False
        else:
            self.mp_face = False

        # Motion-based fallback
        self.prev_gray  = None
        self.motion_cx  = 0.5
        self.motion_cy  = 0.5
        self.prev_cy    = 0.5

    def start(self):
        """Try to open webcam."""
        # Extend range and try both default and macOS specific backend
        for idx in range(8):
            for api in (cv2.CAP_AVFOUNDATION, cv2.CAP_ANY):
                cap = cv2.VideoCapture(idx, api)
                if cap.isOpened():
                    # Some cameras (like Continuity Camera) return True for isOpened
                    # but fail to produce valid frames. Check for actual frames.
                    ret = False
                    for _ in range(5):
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            break
                        time.sleep(0.1)
                        
                    if ret:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        self.cap    = cap
                        self.active = True
                        return True
                    else:
                        cap.release()
        return False

    def stop(self):
        if self.cap:
            self.cap.release()
        self.active = False

    def update(self, dt):
        """Read one frame, update nose_x and nod."""
        if not self.active or not self.cap: return

        ret, frame = self.cap.read()
        if not ret: return

        frame = cv2.flip(frame, 1)   # mirror so left=left
        small = cv2.resize(frame, (200, 150))
        self.frame_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        if self.mp_face:
            self._update_mediapipe(frame)
        else:
            self._update_motion(frame, dt)

        # nod cooldown
        if self.nod_cooldown > 0:
            self.nod_cooldown -= dt

    def _update_mediapipe(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.mp_mesh.process(rgb)
        if not result.multi_face_landmarks:
            self.nod = False
            return
        lm = result.multi_face_landmarks[0].landmark
        h, w = frame.shape[:2]
        # Nose tip = landmark 1
        nx = lm[1].x   # already 0..1, already mirrored (we flipped frame)
        ny = lm[1].y
        self.nose_x = nx

        # Nod detection: downward movement of nose
        if self.prev_nose_y is not None:
            delta_y = ny - self.prev_nose_y
            if delta_y > 0.018 and self.nod_cooldown <= 0:
                self.nod = True
                self.nod_cooldown = 0.5
            else:
                self.nod = False
        self.prev_nose_y = ny

        # Mouth open fallback shoot: upper/lower inner lip
        upper = lm[13]; lower = lm[14]
        face_h = abs(lm[152].y - lm[10].y)   # chin to forehead
        lip_dist = abs(lower.y - upper.y)
        if face_h > 0 and (lip_dist / face_h) > 0.08:
            if self.nod_cooldown <= 0:
                self.nod = True
                self.nod_cooldown = 0.5

    def _update_motion(self, frame, dt):
        """Simple optical-flow centroid for position; motion burst for nod."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (15, 15), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return

        diff = cv2.absdiff(gray, self.prev_gray)
        _, mask = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
        # morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7,7))
        mask   = cv2.dilate(mask, kernel, iterations=2)

        M = cv2.moments(mask)
        if M["m00"] > 500:
            cx = M["m10"] / M["m00"] / frame.shape[1]   # 0..1
            cy = M["m01"] / M["m00"] / frame.shape[0]

            self.motion_cx = lerp(self.motion_cx, cx, 0.25)
            self.nose_x    = self.motion_cx

            # downward motion burst → nod/shoot
            delta_y = cy - self.prev_cy
            if delta_y > 0.04 and self.nod_cooldown <= 0:
                self.nod = True
                self.nod_cooldown = 0.5
            else:
                self.nod = False
            self.prev_cy = cy
        else:
            self.nod = False

        self.prev_gray = gray

    def get_pygame_surface(self):
        """Return a pygame surface (200×150) of latest camera frame."""
        if self.frame_rgb is None:
            s = pygame.Surface((CAM_W, CAM_H))
            s.fill((20, 5, 40))
            return s
        # numpy RGB → pygame surface
        surf = pygame.surfarray.make_surface(
            np.transpose(self.frame_rgb, (1, 0, 2))
        )
        return pygame.transform.scale(surf, (CAM_W, CAM_H))


# ════════════════════════════════════════════════════════════════════════════
#  GAME
# ════════════════════════════════════════════════════════════════════════════
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("🫧 Bubble Pop Frenzy")
        self.screen = pygame.display.set_mode((W, H))
        self.clock  = pygame.time.Clock()

        # Fonts
        self.font_big   = pygame.font.SysFont("Arial Rounded MT Bold", 52, bold=True)
        self.font_med   = pygame.font.SysFont("Arial Rounded MT Bold", 30, bold=True)
        self.font_small = pygame.font.SysFont("Arial Rounded MT Bold", 18)
        self.font_tiny  = pygame.font.SysFont("Arial", 14)

        self.tracker = CameraTracker()
        self.cam_on  = False
        self.cam_msg = "Press C to enable camera"

        self.score = 0
        self.level = 1
        self.lives = 3
        self.bubbles = []
        self.bullets = []
        self.particles = []
        self.floaties = []
        self.shooter = None
        self.spawn_t = 0.0
        self.spawn_int = 1.5
        self.last_shot = 0.0
        self.shoot_color = (0, 0, 0)
        self.next_color = (0, 0, 0)
        self.t = 0.0
        self._btn_play = pygame.Rect(0, 0, 0, 0)

        self.state   = "menu"   # menu | playing | dead
        self.reset()

        # Dot grid cache
        self._dot_surf = pygame.Surface((W - 220, H), pygame.SRCALPHA)
        self._dot_surf.fill((0,0,0,0))
        for gx in range(24, W-220, 30):
            for gy in range(24, H, 30):
                pygame.draw.circle(self._dot_surf, (167,139,250,16), (gx,gy), 2)

    def reset(self):
        self.score      = 0
        self.level      = 1
        self.lives      = 3
        self.bubbles    = []
        self.bullets    = []
        self.particles  = []
        self.floaties   = []
        self.shooter    = Shooter()
        self.spawn_t    = 0.0
        self.spawn_int  = 1.5
        self.last_shot  = 0.0
        self.shoot_color = random.choice(COLORS)
        self.next_color  = random.choice(COLORS)
        self.t           = 0.0   # game time

    # ── CAMERA ──────────────────────────────────────────────────────────────
    def toggle_camera(self):
        if self.cam_on:
            self.tracker.stop()
            self.cam_on  = False
            self.cam_msg = "Press C to enable camera"
        else:
            self.cam_msg = "Opening camera…"
            ok = self.tracker.start()
            if ok:
                self.cam_on  = True
                mode = "MediaPipe" if self.tracker.mp_face else "Motion tracking"
                self.cam_msg = f"Camera ON ({mode})"
            else:
                self.cam_msg = "No camera found – using keyboard/mouse"

    # ── SHOOT ────────────────────────────────────────────────────────────────
    def try_shoot(self):
        now = time.time()
        if now - self.last_shot >= SHOOT_CD:
            self.bullets.append(Bullet(self.shooter.x, H-55, self.shoot_color))
            self.shoot_color = self.next_color
            self.next_color  = random.choice(COLORS)
            self.last_shot   = now

    # ── UPDATE ───────────────────────────────────────────────────────────────
    def update(self, dt):
        if self.state != "playing": return
        self.t += dt

        # camera
        if self.cam_on:
            self.tracker.update(dt)
            tx = self.tracker.nose_x * (W - 220)
            self.shooter.move_toward(tx)
            if self.tracker.nod:
                self.try_shoot()

        # keyboard
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:  self.shooter.move_toward(self.shooter.tx - 6)
        if keys[pygame.K_RIGHT]: self.shooter.move_toward(self.shooter.tx + 6)
        if keys[pygame.K_SPACE]: self.try_shoot()

        self.shooter.update()

        # spawn bubbles
        self.spawn_t += dt
        if self.spawn_t >= self.spawn_int:
            self.bubbles.append(Bubble(self.level))
            self.spawn_t = 0.0

        # update bubbles
        for b in self.bubbles[:]:
            b.update(self.t)
            if b.y - b.r > RED_LINE:
                self.bubbles.remove(b)
                self.lives -= 1
                self._boom(b.wx, RED_LINE, (255, 80, 80))
                if self.lives <= 0:
                    self.state = "dead"

        # update bullets
        for b in self.bullets[:]:
            b.update()
            if b.y < -20:
                self.bullets.remove(b)

        # collision
        for bullet in self.bullets[:]:
            for bubble in self.bubbles[:]:
                dx = bullet.x - bubble.wx
                dy = bullet.y - bubble.y
                if math.sqrt(dx*dx + dy*dy) < bullet.R + bubble.r:
                    self._boom(bubble.wx, bubble.y, bubble.color)
                    match = (bullet.color == bubble.color)
                    if match:
                        pts = 10 * self.level
                        self.score += pts
                        self.floaties.append(Floaty(bubble.wx, bubble.y-10,
                            f"+{pts}", bubble.color, self.font_small))
                    else:
                        self.score = max(0, self.score - 5)
                        self.floaties.append(Floaty(bubble.wx, bubble.y-10,
                            "-5", (255,80,80), self.font_small))
                    self.bubbles.remove(bubble)
                    if bullet in self.bullets: self.bullets.remove(bullet)
                    break

        # particles & floaties
        for p in self.particles[:]:
            p.update()
            if p.life <= 0: self.particles.remove(p)
        for f in self.floaties[:]:
            f.update()
            if f.life <= 0: self.floaties.remove(f)

        # level up
        new_level = self.score // 150 + 1
        if new_level > self.level:
            self.level     = new_level
            self.spawn_int = max(0.45, 1.5 - self.level * 0.11)

    def _boom(self, x, y, color):
        for _ in range(18):
            self.particles.append(Particle(x, y, color))

    # ── DRAW ─────────────────────────────────────────────────────────────────
    def draw(self):
        self.screen.fill(BG_DARK)
        self._draw_game_area()
        self._draw_sidebar()
        if self.state == "menu": self._draw_menu()
        if self.state == "dead": self._draw_dead()
        pygame.display.flip()

    def _draw_game_area(self):
        gw = W - 220
        # dot grid
        self.screen.blit(self._dot_surf, (0, 0))
        # danger zone
        danger = pygame.Surface((gw, 70), pygame.SRCALPHA)
        for i in range(70):
            alpha = int((i/70) * 35)
            pygame.draw.line(danger, (255,70,70,alpha), (0,i), (gw,i))
        self.screen.blit(danger, (0, RED_LINE))
        # dashed red line
        for dx in range(0, gw, 14):
            pygame.draw.line(self.screen, (180,60,60), (dx, RED_LINE), (min(dx+8, gw), RED_LINE), 2)

        # game objects
        for b in self.bubbles:   b.draw(self.screen)
        for b in self.bullets:   b.draw(self.screen)
        for p in self.particles: p.draw(self.screen)
        for f in self.floaties:  f.draw(self.screen)
        self.shooter.draw(self.screen, self.shoot_color, self.next_color)

    def _draw_sidebar(self):
        gw  = W - 220
        sw  = 220
        sx  = gw
        # sidebar bg
        sb  = pygame.Surface((sw, H), pygame.SRCALPHA)
        sb.fill((20, 5, 45, 220))
        self.screen.blit(sb, (sx, 0))
        pygame.draw.line(self.screen, (80,40,120), (sx,0), (sx,H), 2)

        y = 14
        # Title
        t = self.font_med.render("🫧 Bubble Pop", True, (220,180,255))
        self.screen.blit(t, (sx + sw//2 - t.get_width()//2, y)); y += 34

        # HUD boxes
        for label, val, col in [
            ("SCORE", str(self.score),  (255,219,109)),
            ("LEVEL", str(self.level),  (167,139,250)),
            ("LIVES", "♥"*max(0,self.lives), (255,111,216)),
        ]:
            box = pygame.Rect(sx+10, y, sw-20, 44)
            pygame.draw.rect(self.screen, (40,15,70), box, border_radius=10)
            pygame.draw.rect(self.screen, (80,40,120), box, width=2, border_radius=10)
            lbl = self.font_tiny.render(label, True, (150,120,200))
            self.screen.blit(lbl, (sx+18, y+5))
            vt  = self.font_small.render(val, True, col)
            self.screen.blit(vt, (sx+18, y+20))
            y += 52

        # Next color
        y += 4
        pygame.draw.rect(self.screen, (40,15,70), (sx+10,y,sw-20,52), border_radius=10)
        pygame.draw.rect(self.screen, (80,40,120), (sx+10,y,sw-20,52), width=2, border_radius=10)
        nl = self.font_tiny.render("NEXT COLOR", True, (150,120,200))
        self.screen.blit(nl, (sx+18, y+5))
        pygame.draw.circle(self.screen, self.next_color,  (sx+50, y+34), 13)
        pygame.draw.circle(self.screen, (200,200,200), (sx+50, y+34), 13, 2)
        y += 62

        # Camera preview
        y += 6
        cam_surf = self.tracker.get_pygame_surface()
        cam_rect = pygame.Rect(sx+10, y, CAM_W, CAM_H)
        pygame.draw.rect(self.screen, (80,40,120), cam_rect.inflate(4,4), border_radius=10)
        self.screen.blit(cam_surf, (sx+10, y))
        # live dot
        dot_col = (80,255,130) if self.cam_on else (255,80,80)
        pygame.draw.circle(self.screen, dot_col, (sx+sw-20, y+10), 6)
        y += CAM_H + 6

        # cam status msg
        msg = self.font_tiny.render(self.cam_msg[:26], True, (109,255,245))
        self.screen.blit(msg, (sx+10, y)); y+=18

        # controls hint
        hints = [
            "[ C ] Toggle camera",
            "[ ← → ] Move",
            "[ SPACE ] Shoot",
            "[ R ] Restart",
        ]
        for h in hints:
            ht = self.font_tiny.render(h, True, (130,100,180))
            self.screen.blit(ht, (sx+10, y)); y += 17

    def _overlay_box(self, title, lines, btn_text):
        gw = W - 220
        box_w, box_h = 360, 240
        bx = (gw - box_w) // 2
        by = (H  - box_h) // 2
        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill((10, 3, 25, 220))
        self.screen.blit(box, (bx, by))
        pygame.draw.rect(self.screen, (130,80,200), (bx,by,box_w,box_h), width=3, border_radius=16)

        t = self.font_big.render(title, True, (255,111,216))
        self.screen.blit(t, (bx + box_w//2 - t.get_width()//2, by+20))

        for i, line in enumerate(lines):
            lt = self.font_small.render(line, True, (196,181,253))
            self.screen.blit(lt, (bx + box_w//2 - lt.get_width()//2, by + 90 + i*26))

        # button
        btn_rect = pygame.Rect(bx + box_w//2 - 90, by + box_h - 52, 180, 38)
        pygame.draw.rect(self.screen, (130,80,220), btn_rect, border_radius=20)
        bt = self.font_small.render(btn_text, True, (255,255,255))
        self.screen.blit(bt, (btn_rect.centerx - bt.get_width()//2,
                               btn_rect.centery - bt.get_height()//2))
        return btn_rect

    def _draw_menu(self):
        self._btn_play = self._overlay_box(
            "Bubble Pop 🫧",
            ["Match bullet color to bubble!",
             "Wrong color = -5 pts",
             "Press C to enable camera"],
            "▶  Play!"
        )

    def _draw_dead(self):
        self._btn_play = self._overlay_box(
            "Game Over 💥",
            [f"Score: {self.score}   Level: {self.level}",
             "Press R or click Play Again"],
            "🔄  Play Again"
        )

    # ── MAIN LOOP ────────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.tracker.stop(); pygame.quit(); sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_c:
                        self.toggle_camera()
                    if event.key == pygame.K_r and self.state in ("dead","menu"):
                        self.reset(); self.state = "playing"
                    if event.key == pygame.K_ESCAPE:
                        self.tracker.stop(); pygame.quit(); sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.state in ("menu","dead"):
                        if self._btn_play.collidepoint(event.pos):
                            self.reset(); self.state = "playing"
                    elif self.state == "playing":
                        mx, _ = pygame.mouse.get_pos()
                        if mx < W - 220:
                            self.try_shoot()

                if event.type == pygame.MOUSEMOTION:
                    if self.state == "playing" and not self.cam_on:
                        mx, _ = pygame.mouse.get_pos()
                        if mx < W - 220:
                            self.shooter.move_toward(mx)

            self.update(dt)
            self.draw()


# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 52)
    print("  🫧  Bubble Pop Frenzy")
    print("=" * 52)
    print(f"  MediaPipe available : {MEDIAPIPE}")
    print()
    print("  Install deps if needed:")
    print("    pip install pygame-ce opencv-python")
    print("    pip install mediapipe          # optional, better tracking")
    print()
    print("  Controls:")
    print("    C          – toggle camera")
    print("    ← →        – move shooter")
    print("    SPACE      – shoot")
    print("    Mouse      – aim & click to shoot")
    print("    R          – restart")
    print("    ESC        – quit")
    print("=" * 52)
    Game().run()
