import math
import os
import random
import threading
import time
import cv2
import pygame
from cvzone.HandTrackingModule import HandDetector

# ============================================================
# AIR TILES — Retro Synthwave Gesture Rhythm
# Fullscreen | 70-second challenge | Song selection
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "music")

SONGS = [
    {
        "title": "CHEAP THRILLS",
        "artist": "SIA",
        "file": "cheapthrills.mp3",
    },
    {
        "title": "BOY WITH LOVE FT.HALSEY",
        "artist": "BTS",
        "file": "boywithlove.mp3",
    },
    {
        "title": "DANCE MONKEYS",
        "artist": "TONES & I",
        "file": "dancemonkeys.mp3",
    },
    {
        "title": "CLOSER",
        "artist": "CHAINSMOKERS",
        "file": "closer.mp3",
    }
]

# Only show tracks whose audio files actually exist.
SONGS = [
    song for song in SONGS
    if os.path.isfile(os.path.join(MUSIC_DIR, song["file"]))
]

FPS = 60
GAME_DURATION = 70.0
RESULTS_SCREEN_DURATION = 4.0
LANES = 4

START_SPEED = 230
END_SPEED = 540
START_SPAWN = 1.20
END_SPAWN = 0.36

TILE_H = 52
BAR_HEIGHT = 20
BAR_LANE_RATIO = 0.92

MAX_BAR_SPEED = 2400.0

BG_DARK = (18, 2, 24)
SKY_MAGENTA = (215, 0, 180)
SKY_PURPLE = (95, 8, 90)
PANEL = (28, 6, 38)
PLAYFIELD = (20, 4, 28)
WHITE = (255, 250, 255)
MUTED = (185, 130, 195)
CYAN = (45, 225, 255)
PINK = (255, 20, 165)
PURPLE = (165, 65, 245)
YELLOW = (255, 215, 15)
ORANGE = (255, 120, 40)
GREEN = (55, 255, 165)
SIDEWALK_LIGHT = (235, 145, 175)
SIDEWALK_DARK = (120, 45, 95)

LANE_COLORS = [PINK, YELLOW, CYAN, ORANGE]

# ============================================================
# SMOOTH HAND TRACKING (threaded + One Euro filter)
# ============================================================

PLATE_SMOOTHING = 30.0   # higher = snappier, lower = smoother (try 20-40)


def _alpha(cutoff, dt):
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuro:
    def __init__(self, min_cutoff=1.5, beta=10.0, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    def __call__(self, x, t):
        if self.x_prev is None:
            self.x_prev, self.t_prev = x, t
            return x

        dt = max(1e-3, t - self.t_prev)
        dx = (x - self.x_prev) / dt
        a_d = _alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev

        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = _alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self.x_prev

        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat


class HandTracker:
    def __init__(self, cap, detector):
        self.cap = cap
        self.detector = detector
        self.filter = OneEuro()
        self.lock = threading.Lock()
        self.norm_x = None
        self.frame_rgb = None
        self.frame_id = 0
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.005)
                continue

            t = time.perf_counter()
            frame = cv2.flip(frame, 1)

            fh, fw = frame.shape[:2]
            frame = cv2.resize(
                frame, (640, int(640 * fh / fw)),
                interpolation=cv2.INTER_AREA
            )

            hands, frame = self.detector.findHands(
                frame, flipType=False, draw=True
            )

            nx = None
            if hands:
                x = hands[0]["lmList"][8][0] / frame.shape[1]
                nx = self.filter(max(0.0, min(1.0, x)), t)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb = cv2.flip(rgb, 1)   # same as the old draw_camera flip

            with self.lock:
                if nx is not None:
                    self.norm_x = nx
                self.frame_rgb = rgb
                self.frame_id += 1

    def get(self):
        with self.lock:
            return self.norm_x, self.frame_rgb, self.frame_id

    def stop(self):
        self.running = False
        self.thread.join(timeout=1.0)


# ============================================================
# INITIALIZATION
# ============================================================

pygame.init()

try:
    pygame.mixer.init()
except pygame.error as exc:
    print("Audio output unavailable:", exc)

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
WIDTH, HEIGHT = screen.get_size()

pygame.display.set_caption("AIR TILES | Retro Synthwave Edition")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("couriernew", 20, bold=True)
SMALL = pygame.font.SysFont("couriernew", 15, bold=True)
BIG = pygame.font.SysFont("couriernew", 38, bold=True)
TITLE = pygame.font.SysFont("couriernew", 44, bold=True)

MARGIN = max(24, int(WIDTH * 0.025))
HEADER_H = max(86, int(HEIGHT * 0.12))

CAM_W = min(360, max(280, int(WIDTH * 0.25)))
CAM_H = int(CAM_W * 9 / 16)
CAM_X = WIDTH - CAM_W - MARGIN
CAM_Y = HEADER_H + 40

GAME_LEFT = MARGIN + 125
GAME_RIGHT = CAM_X - 35

if GAME_RIGHT - GAME_LEFT < 4 * 100:
    GAME_LEFT = MARGIN + 80
    GAME_RIGHT = WIDTH - MARGIN - 30

GAME_TOP = HEADER_H + 55
HIT_Y = HEIGHT - max(115, int(HEIGHT * 0.17))
FIELD_BOTTOM = min(HEIGHT - 48, HIT_Y + 60)

LANE_WIDTH = (GAME_RIGHT - GAME_LEFT) / LANES
BAR_WIDTH = LANE_WIDTH * BAR_LANE_RATIO

detector = HandDetector(detectionCon=0.75, maxHands=2)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    pygame.quit()
    raise RuntimeError(
        "Webcam not detected. Check your Mac camera permissions."
    )

cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
tracker = HandTracker(cap, detector)
cam_surface = None
last_cam_id = -1

selected_song = 0
music_loaded = False


def load_selected_song():
    global music_loaded

    music_loaded = False

    if not SONGS:
        print("No playable songs found in:", MUSIC_DIR)
        return

    song_path = os.path.join(
        MUSIC_DIR, SONGS[selected_song]["file"]
    )

    try:
        pygame.mixer.music.load(song_path)
        music_loaded = True
        print("Selected song:", SONGS[selected_song]["title"])
    except pygame.error as exc:
        print("Could not load song:", exc)


if SONGS:
    load_selected_song()
else:
    print("Add your MP3 files to:", MUSIC_DIR)
    print(
        "Expected: cheapthrills.mp3, "
        "boywithlove.mp3, dancemonkeys.mp3"
    )

# ============================================================
# PIXEL ART FONT
# ============================================================

PIXEL_FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "?": ["01110", "10001", "00010", "00100", "00100", "00000", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def draw_pixel_block_text(
    surface, text, x, y, block_size=6,
    fg=WHITE, shadow=PINK, center=False
):
    text = text.upper()
    char_w = 5 * block_size
    spacing = block_size * 2
    total_w = len(text) * char_w + max(0, len(text) - 1) * spacing
    total_h = 7 * block_size

    start_x = int(x - total_w // 2) if center else int(x)
    start_y = int(y - total_h // 2) if center else int(y)
    depth = max(2, block_size // 2)

    for pass_shadow in (True, False):
        curr_x = start_x

        for ch in text:
            grid = PIXEL_FONT.get(ch, PIXEL_FONT[" "])

            for r, row in enumerate(grid):
                for c, val in enumerate(row):
                    if val == "1":
                        bx = curr_x + c * block_size
                        by = start_y + r * block_size

                        if pass_shadow:
                            bx += depth
                            by += depth

                        pygame.draw.rect(
                            surface,
                            shadow if pass_shadow else fg,
                            (bx, by, block_size - 1, block_size - 1)
                        )

            curr_x += char_w + spacing


def draw_pixel_cloud(surf, cx, cy, scale=6):
    pattern = [
        "    1111      ",
        "  112222111   ",
        " 122233322211 ",
        "13333444333321",
        "14444444444441"
    ]

    colors = {
        "1": (255, 200, 150),
        "2": (235, 120, 185),
        "3": (150, 75, 195),
        "4": (85, 50, 155)
    }

    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            if ch in colors:
                pygame.draw.rect(
                    surf, colors[ch],
                    (cx + c * scale, cy + r * scale, scale, scale)
                )


def draw_pixel_shop(surf, x, ground_y):
    w, h = 156, 118
    top_y = ground_y - h

    pygame.draw.rect(surf, (150, 45, 125), (x, top_y + 24, w, h - 24))
    pygame.draw.rect(surf, (235, 115, 175), (x, top_y + 24, w, h - 24), 3)
    pygame.draw.rect(surf, (245, 145, 185), (x - 6, top_y + 12, w + 12, 12))
    pygame.draw.rect(surf, (195, 75, 145), (x - 2, top_y + 4, w + 4, 8))

    pygame.draw.rect(surf, (255, 150, 195), (x + 38, top_y - 14, 80, 18))
    pygame.draw.rect(surf, (110, 25, 90), (x + 38, top_y - 14, 80, 18), 2)

    for sx in range(x + 46, x + 110, 10):
        pygame.draw.rect(surf, WHITE, (sx, top_y - 9, 6, 8))

    for i in range(0, w - 12, 16):
        col = (255, 165, 205) if (i // 16) % 2 == 0 else (210, 65, 145)
        pygame.draw.rect(surf, col, (x + 6 + i, top_y + 38, 16, 16))

    pygame.draw.rect(surf, (220, 115, 195), (x + 12, top_y + 58, 84, 46))
    pygame.draw.rect(surf, (90, 25, 85), (x + 12, top_y + 58, 84, 46), 3)
    pygame.draw.line(surf, (90, 25, 85), (x + 54, top_y + 58), (x + 54, top_y + 104), 3)
    pygame.draw.rect(surf, (185, 85, 170), (x + 106, top_y + 58, 38, 60))
    pygame.draw.rect(surf, (90, 25, 85), (x + 106, top_y + 58, 38, 60), 3)


def draw_vending_machine(surf, x, ground_y):
    w, h = 44, 68
    top_y = ground_y - h

    pygame.draw.rect(surf, (145, 75, 175), (x, top_y, w, h))
    pygame.draw.rect(surf, (220, 140, 235), (x, top_y, w, h), 2)
    pygame.draw.rect(surf, (35, 25, 65), (x + 6, top_y + 8, w - 12, 40))

    for ry in range(top_y + 12, top_y + 44, 8):
        for rx in range(x + 10, x + w - 10, 8):
            col = CYAN if (rx + ry) % 16 == 0 else PINK
            pygame.draw.rect(surf, col, (rx, ry, 5, 4))


def draw_bus_stop(surf, x, ground_y):
    w, h = 110, 72
    top_y = ground_y - h

    pygame.draw.rect(surf, (100, 28, 95), (x + 6, top_y + 10, w - 12, h - 10))
    pygame.draw.rect(surf, (215, 85, 165), (x, top_y, w, 10))
    pygame.draw.rect(surf, CYAN, (x + 35, top_y - 10, 40, 8))
    pygame.draw.rect(surf, (175, 55, 135), (x + 6, top_y + 10, w - 12, h - 10), 2)
    pygame.draw.rect(surf, (65, 15, 65), (x + 16, ground_y - 18, 42, 6))


def draw_street_lamp(surf, x, ground_y, direction=1):
    h = 96
    top_y = ground_y - h

    pygame.draw.rect(surf, (135, 45, 120), (x, top_y, 5, h))
    arm_x = x if direction > 0 else x - 34
    pygame.draw.rect(surf, (175, 65, 150), (arm_x, top_y + 4, 38, 4))

    lamp_x = x + 28 if direction > 0 else x - 36
    pygame.draw.rect(surf, (235, 95, 180), (lamp_x, top_y + 2, 14, 8))
    pygame.draw.rect(surf, CYAN, (lamp_x + 3, top_y + 10, 8, 3))


def create_synthwave_background():
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill(BG_DARK)

    bayer = [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
    ]

    px = 6
    sky_rows = int((HEIGHT * 0.58) // px)

    for r in range(sky_rows):
        ratio = r / max(1, sky_rows - 1)

        for c in range(0, WIDTH // px + 1):
            threshold = bayer[r % 4][c % 4]

            if ratio < 0.45:
                local_t = (ratio / 0.45) * 16.0
                col = SKY_PURPLE if threshold < local_t else SKY_MAGENTA
            else:
                local_t = ((ratio - 0.45) / 0.55) * 16.0
                col = BG_DARK if threshold < local_t else SKY_PURPLE

            pygame.draw.rect(surf, col, (c * px, r * px, px, px))

    sun_cx = (GAME_LEFT + GAME_RIGHT) // 2
    sun_cy = GAME_TOP + 95
    sun_r = 96

    for py in range(-sun_r, sun_r, px):
        norm_y = (py + sun_r) / (2 * sun_r)

        if norm_y > 0.52 and int(py // px) % 3 == 0:
            continue
        if norm_y > 0.72 and int(py // px) % 2 == 0:
            continue

        if norm_y < 0.5:
            t = norm_y / 0.5
            col = (
                int(YELLOW[0] + (ORANGE[0] - YELLOW[0]) * t),
                int(YELLOW[1] + (ORANGE[1] - YELLOW[1]) * t),
                int(YELLOW[2] + (ORANGE[2] - YELLOW[2]) * t),
            )
        else:
            t = (norm_y - 0.5) / 0.5
            col = (
                int(ORANGE[0] + (PINK[0] - ORANGE[0]) * t),
                int(ORANGE[1] + (PINK[1] - ORANGE[1]) * t),
                int(ORANGE[2] + (PINK[2] - ORANGE[2]) * t),
            )

        for p_x in range(-sun_r, sun_r, px):
            if p_x * p_x + py * py <= sun_r * sun_r:
                pygame.draw.rect(
                    surf, col,
                    (sun_cx + p_x, sun_cy + py, px, px)
                )

    draw_pixel_cloud(surf, int(WIDTH * 0.05), int(HEIGHT * 0.18), 5)
    draw_pixel_cloud(surf, int(WIDTH * 0.22), int(HEIGHT * 0.11), 4)
    draw_pixel_cloud(surf, int(WIDTH * 0.64), int(HEIGHT * 0.12), 4)
    draw_pixel_cloud(surf, int(WIDTH * 0.84), int(HEIGHT * 0.20), 5)
    draw_pixel_cloud(surf, int(WIDTH * 0.76), int(HEIGHT * 0.42), 4)

    sidewalk_h = 44
    ground_y = HEIGHT - sidewalk_h

    pygame.draw.rect(surf, SIDEWALK_DARK, (0, ground_y, WIDTH, sidewalk_h))
    pygame.draw.rect(surf, SIDEWALK_LIGHT, (0, ground_y, WIDTH, 6))

    brick_w, brick_h = 24, 10

    for row_idx, by in enumerate(range(ground_y + 6, HEIGHT, brick_h)):
        offset = brick_w // 2 if row_idx % 2 == 1 else 0
        pygame.draw.line(surf, (90, 25, 75), (0, by), (WIDTH, by), 2)

        for bx in range(-offset, WIDTH, brick_w):
            pygame.draw.line(surf, (90, 25, 75), (bx, by), (bx, by + brick_h), 2)
            pygame.draw.rect(
                surf, (210, 115, 155),
                (bx + 3, by + 2, brick_w - 6, brick_h - 4)
            )

    draw_pixel_shop(surf, 18, ground_y)
    draw_vending_machine(surf, 190, ground_y)
    draw_bus_stop(surf, 255, ground_y)
    draw_street_lamp(surf, 410, ground_y, direction=-1)
    draw_street_lamp(surf, WIDTH - 420, ground_y, direction=1)
    draw_bus_stop(surf, WIDTH - 365, ground_y)
    draw_vending_machine(surf, WIDTH - 235, ground_y)
    draw_pixel_shop(surf, WIDTH - 174, ground_y)

    return surf


BG_SURFACE = create_synthwave_background()

# ============================================================
# GAME STATE
# ============================================================

tiles = []
particles = []

score = 0
combo = 0
best_combo = 0
misses = 0

game_state = "ready"
game_start = 0.0
last_spawn = 0.0
finished_time = 0.0

plate_x = (GAME_LEFT + GAME_RIGHT) / 2
target_plate_x = plate_x
hit_flash = 0.0

_panel_cache = {}
_aura_cache = {}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def draw_text(
    text, font, color, x, y,
    center=False, shadow_color=(10, 0, 15)
):
    if shadow_color:
        shadow = font.render(str(text), False, shadow_color)
        shadow_rect = shadow.get_rect()

        if center:
            shadow_rect.center = (int(x) + 2, int(y) + 2)
        else:
            shadow_rect.topleft = (int(x) + 2, int(y) + 2)

        screen.blit(shadow, shadow_rect)

    surface = font.render(str(text), False, color)
    rect = surface.get_rect()

    if center:
        rect.center = (int(x), int(y))
    else:
        rect.topleft = (int(x), int(y))

    screen.blit(surface, rect)


def draw_pixel_panel(rect, bg_color=PANEL, border_color=PINK, alpha=230):
    key = (rect.width, rect.height, bg_color, alpha)
    panel_surf = _panel_cache.get(key)

    if panel_surf is None:
        panel_surf = pygame.Surface(
            (rect.width, rect.height), pygame.SRCALPHA
        )
        panel_surf.fill((*bg_color, alpha))
        _panel_cache[key] = panel_surf

    screen.blit(panel_surf, rect.topleft)

    pygame.draw.rect(screen, border_color, rect, 3)
    pygame.draw.rect(screen, (95, 30, 110), rect.inflate(-8, -8), 2)

    for cx, cy in [
        (rect.left + 4, rect.top + 4),
        (rect.right - 8, rect.top + 4),
        (rect.left + 4, rect.bottom - 8),
        (rect.right - 8, rect.bottom - 8),
    ]:
        pygame.draw.rect(screen, YELLOW, (cx, cy, 4, 4))


def lane_center(lane):
    return int(GAME_LEFT + (lane + 0.5) * LANE_WIDTH)


def difficulty(elapsed):
    progress = max(0.0, min(1.0, elapsed / GAME_DURATION))
    speed = START_SPEED + (END_SPEED - START_SPEED) * progress
    interval = START_SPAWN + (END_SPAWN - START_SPAWN) * progress
    return speed, interval


def reset_game():
    global tiles, particles, score, combo, best_combo
    global misses, game_state, game_start, last_spawn
    global plate_x, target_plate_x, hit_flash, finished_time

    tiles = []
    particles = []
    score = 0
    combo = 0
    best_combo = 0
    misses = 0
    hit_flash = 0.0
    finished_time = 0.0

    plate_x = (GAME_LEFT + GAME_RIGHT) / 2
    target_plate_x = plate_x

    game_start = time.perf_counter()
    last_spawn = 0.0
    game_state = "playing"

    if music_loaded:
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.play()
        except pygame.error as exc:
            print("Music playback error:", exc)


def add_particles(x, y, color):
    for _ in range(18):
        particles.append({
            "x": float(x),
            "y": float(y),
            "vx": random.uniform(-200, 200),
            "vy": random.uniform(-250, 60),
            "life": random.uniform(0.25, 0.55),
            "color": random.choice([color, WHITE, YELLOW])
        })


def draw_glow_rect(rect, color):
    pygame.draw.rect(screen, (12, 0, 18), rect.move(5, 5))

    key = (rect.width, rect.height, color)
    aura = _aura_cache.get(key)

    if aura is None:
        aura = pygame.Surface(
            (rect.width + 12, rect.height + 12), pygame.SRCALPHA
        )
        aura.fill((*color, 70))
        _aura_cache[key] = aura

    screen.blit(aura, (rect.x - 6, rect.y - 6))

    pygame.draw.rect(screen, color, rect)
    pygame.draw.rect(screen, WHITE, rect, 2)
    pygame.draw.rect(
        screen, WHITE,
        (rect.x + 5, rect.y + 5, max(4, rect.width - 10), 4)
    )


# ============================================================
# DRAWING
# ============================================================

def draw_background():
    screen.blit(BG_SURFACE, (0, 0))

    header = pygame.Rect(
        MARGIN, 16, WIDTH - MARGIN * 2, HEADER_H
    )
    draw_pixel_panel(header, PANEL, PINK, alpha=235)

    draw_pixel_block_text(
        screen, "AIR TILES",
        MARGIN + 24, 26,
        block_size=5, fg=WHITE, shadow=PINK
    )

    draw_text(
        "SYNTHWAVE GESTURE RHYTHM // 70 SEC ARCADE CHALLENGE",
        SMALL, YELLOW, MARGIN + 26, 68
    )

    field = pygame.Rect(
        GAME_LEFT, GAME_TOP,
        GAME_RIGHT - GAME_LEFT,
        FIELD_BOTTOM - GAME_TOP
    )
    draw_pixel_panel(field, PLAYFIELD, PINK, alpha=175)

    for lane in range(LANES):
        x = int(GAME_LEFT + lane * LANE_WIDTH)
        color = LANE_COLORS[lane]

        if lane > 0:
            for py in range(GAME_TOP + 6, FIELD_BOTTOM - 6, 14):
                pygame.draw.rect(
                    screen, (95, 35, 110), (x - 1, py, 3, 7)
                )

        badge = pygame.Rect(x + 12, GAME_TOP + 10, 28, 24)
        pygame.draw.rect(screen, (40, 10, 52), badge)
        pygame.draw.rect(screen, color, badge, 2)

        draw_text(
            str(lane + 1), SMALL, color,
            badge.centerx, badge.centery, center=True
        )

    pygame.draw.rect(
        screen, PINK,
        (GAME_LEFT + 3, HIT_Y - 3, GAME_RIGHT - GAME_LEFT - 6, 8)
    )
    pygame.draw.rect(
        screen, WHITE,
        (GAME_LEFT + 3, HIT_Y - 1, GAME_RIGHT - GAME_LEFT - 6, 4)
    )

    draw_text(
        "HIT ZONE", SMALL, YELLOW,
        GAME_RIGHT - 82, HIT_Y + 12
    )


def draw_hud(elapsed):
    panel = pygame.Rect(
        MARGIN, GAME_TOP, 110,
        min(340, HEIGHT - GAME_TOP - 80)
    )
    draw_pixel_panel(panel, PANEL, CYAN, alpha=235)

    draw_text("SCORE", SMALL, YELLOW, panel.x + 12, panel.y + 16)
    draw_text(f"{score:06d}", FONT, WHITE, panel.x + 12, panel.y + 38)

    draw_text("COMBO", SMALL, YELLOW, panel.x + 12, panel.y + 90)
    draw_text(f"x{combo}", BIG, PINK, panel.x + 12, panel.y + 112)

    draw_text("BEST", SMALL, MUTED, panel.x + 12, panel.y + 180)
    draw_text(best_combo, FONT, CYAN, panel.x + 12, panel.y + 202)

    draw_text("MISSES", SMALL, MUTED, panel.x + 12, panel.y + 245)
    draw_text(misses, FONT, ORANGE, panel.x + 12, panel.y + 268)

    remaining = max(0.0, GAME_DURATION - elapsed)

    draw_text(
        f"TIME {remaining:04.1f}s", FONT, YELLOW,
        GAME_RIGHT - 135, GAME_TOP - 32
    )

    progress = max(0.0, min(1.0, elapsed / GAME_DURATION))
    bar_w = GAME_RIGHT - GAME_LEFT - 150
    bar = pygame.Rect(GAME_LEFT, GAME_TOP - 26, bar_w, 12)

    pygame.draw.rect(screen, (35, 8, 45), bar)
    pygame.draw.rect(screen, PINK, bar, 2)

    segments = 28
    seg_w = (bar_w - 6) / segments
    filled = int(progress * segments)

    for i in range(filled):
        col = YELLOW if i > segments * 0.75 else CYAN
        pygame.draw.rect(
            screen, col,
            (
                int(bar.x + 3 + i * seg_w),
                bar.y + 3,
                max(2, int(seg_w - 2)),
                bar.height - 6
            )
        )


def draw_tiles():
    for tile in tiles:
        x = lane_center(tile["lane"])

        rect = pygame.Rect(
            int(x - LANE_WIDTH * 0.34),
            int(tile["y"]),
            int(LANE_WIDTH * 0.68),
            TILE_H
        )

        draw_glow_rect(rect, LANE_COLORS[tile["lane"]])
        pygame.draw.rect(
            screen, (25, 5, 35),
            rect.inflate(-14, -14), width=2
        )


def draw_plate(x):
    rect = pygame.Rect(
        int(x - BAR_WIDTH / 2),
        int(HIT_Y - BAR_HEIGHT / 2),
        int(BAR_WIDTH), BAR_HEIGHT
    )

    draw_glow_rect(rect, CYAN)
    pygame.draw.rect(screen, YELLOW, rect.inflate(-14, -8))


def draw_particles(dt):
    for particle in particles[:]:
        particle["x"] += particle["vx"] * dt
        particle["y"] += particle["vy"] * dt
        particle["vy"] += 380 * dt
        particle["life"] -= dt

        if particle["life"] <= 0:
            particles.remove(particle)
            continue

        size = max(3, int(9 * particle["life"] / 0.55))
        pygame.draw.rect(
            screen, particle["color"],
            (
                int(particle["x"] - size // 2),
                int(particle["y"] - size // 2),
                size, size
            )
        )


def draw_camera(surface):
    if surface is None:
        return

    panel = pygame.Rect(
        CAM_X - 10, CAM_Y - 36,
        CAM_W + 20, CAM_H + 62
    )
    draw_pixel_panel(panel, PANEL, CYAN, alpha=235)

    draw_text("HAND TRACKER [CAM]", SMALL, YELLOW, CAM_X, CAM_Y - 28)
    screen.blit(surface, (CAM_X, CAM_Y))

    for sy in range(CAM_Y, CAM_Y + CAM_H, 4):
        pygame.draw.line(
            screen, (18, 2, 24),
            (CAM_X, sy), (CAM_X + CAM_W, sy), 1
        )

    pygame.draw.rect(
        screen, PINK, (CAM_X, CAM_Y, CAM_W, CAM_H), 3
    )

    draw_text(
        "MOVE INDEX FINGER TO SLIDE BAR",
        SMALL, MUTED, CAM_X, CAM_Y + CAM_H + 8
    )


def draw_ready_screen():
    panel_w = min(620, GAME_RIGHT - GAME_LEFT - 24)
    panel_h = 280

    panel = pygame.Rect(
        GAME_LEFT + (GAME_RIGHT - GAME_LEFT - panel_w) // 2,
        GAME_TOP + (HIT_Y - GAME_TOP - panel_h) // 2,
        panel_w, panel_h
    )

    draw_pixel_panel(panel, PANEL, PINK, alpha=245)

    draw_pixel_block_text(
        screen, "GAME",
        panel.centerx, panel.y + 48,
        block_size=7, fg=WHITE, shadow=PINK, center=True
    )

    if SONGS:
        song = SONGS[selected_song]

        draw_text(
            "SELECT YOUR TRACK",
            FONT, YELLOW, panel.centerx, panel.y + 105, center=True
        )

        title = song["title"]
        title_font = FONT if len(title) <= 27 else SMALL

        draw_text(
            f"<  {title}  >",
            title_font, CYAN,
            panel.centerx, panel.y + 140, center=True
        )

        draw_text(
            f"ARTIST: {song['artist']}",
            SMALL, WHITE,
            panel.centerx, panel.y + 172, center=True
        )

        draw_text(
            "LEFT / RIGHT TO CHANGE TRACK",
            SMALL, MUTED, panel.centerx, panel.y + 207, center=True
        )

        draw_text(
            "PRESS SPACE TO PLAY",
            SMALL, YELLOW, panel.centerx, panel.y + 239, center=True
        )
    else:
        draw_text(
            "NO SONGS FOUND",
            FONT, YELLOW, panel.centerx, panel.y + 130, center=True
        )
        draw_text(
            "ADD MP3 FILES TO THE MUSIC FOLDER",
            SMALL, WHITE, panel.centerx, panel.y + 170, center=True
        )

    draw_text(
        "[Q / ESC] QUIT",
        SMALL, MUTED, panel.centerx, panel.bottom - 18, center=True
    )


def draw_finished_screen():
    panel_w = min(580, GAME_RIGHT - GAME_LEFT - 24)
    panel_h = 250

    panel = pygame.Rect(
        GAME_LEFT + (GAME_RIGHT - GAME_LEFT - panel_w) // 2,
        GAME_TOP + (HIT_Y - GAME_TOP - panel_h) // 2,
        panel_w, panel_h
    )

    draw_pixel_panel(panel, PANEL, YELLOW, alpha=245)

    draw_pixel_block_text(
        screen, "FINISH",
        panel.centerx, panel.y + 44,
        block_size=6, fg=WHITE, shadow=PINK, center=True
    )

    draw_text(
        f"FINAL SCORE  {score:06d}",
        FONT, YELLOW, panel.centerx, panel.y + 110, center=True
    )

    draw_text(
        f"BEST COMBO x{best_combo}   MISSES {misses}",
        SMALL, CYAN, panel.centerx, panel.y + 150, center=True
    )

    draw_text(
        "RETURNING TO SONG SELECT...",
        SMALL, WHITE, panel.centerx, panel.y + 188, center=True
    )

    draw_text(
        "LEFT / RIGHT: CHANGE SONG",
        SMALL, MUTED, panel.centerx, panel.y + 216, center=True
    )


# ============================================================
# MAIN LOOP
# ============================================================

running = True
previous_time = time.perf_counter()

try:
    while running:
        now = time.perf_counter()
        dt = min(now - previous_time, 0.05)
        previous_time = now

        # ---------------- HAND TRACKING (non-blocking) ----------------
        norm_x, cam_rgb, cam_id = tracker.get()

        if cam_rgb is not None and cam_id != last_cam_id:
            last_cam_id = cam_id
            small = cv2.resize(
                cam_rgb, (CAM_W, CAM_H),
                interpolation=cv2.INTER_LINEAR
            )
            cam_surface = pygame.surfarray.make_surface(
                small.swapaxes(0, 1)
            )

        if norm_x is not None:
            target_plate_x = (
                GAME_LEFT + norm_x * (GAME_RIGHT - GAME_LEFT)
            )

        target_plate_x = max(
            GAME_LEFT + BAR_WIDTH / 2,
            min(GAME_RIGHT - BAR_WIDTH / 2, target_plate_x)
        )

        # frame-rate independent glide toward the target
        plate_x += (target_plate_x - plate_x) * (
            1.0 - math.exp(-PLATE_SMOOTHING * dt)
        )

        # ---------------- INPUT ----------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False

                elif event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                    WIDTH, HEIGHT = screen.get_size()

                    MARGIN = max(24, int(WIDTH * 0.025))
                    HEADER_H = max(86, int(HEIGHT * 0.12))

                    CAM_W = min(360, max(280, int(WIDTH * 0.25)))
                    CAM_H = int(CAM_W * 9 / 16)
                    CAM_X = WIDTH - CAM_W - MARGIN
                    CAM_Y = HEADER_H + 40

                    GAME_LEFT = MARGIN + 125
                    GAME_RIGHT = CAM_X - 35

                    if GAME_RIGHT - GAME_LEFT < 4 * 100:
                        GAME_LEFT = MARGIN + 80
                        GAME_RIGHT = WIDTH - MARGIN - 30

                    GAME_TOP = HEADER_H + 55
                    HIT_Y = HEIGHT - max(115, int(HEIGHT * 0.17))
                    FIELD_BOTTOM = min(HEIGHT - 48, HIT_Y + 60)

                    LANE_WIDTH = (GAME_RIGHT - GAME_LEFT) / LANES
                    BAR_WIDTH = LANE_WIDTH * BAR_LANE_RATIO

                    plate_x = (GAME_LEFT + GAME_RIGHT) / 2
                    target_plate_x = plate_x
                    BG_SURFACE = create_synthwave_background()
                    _panel_cache.clear()
                    _aura_cache.clear()
                    last_cam_id = -1

                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    if game_state != "playing" and SONGS:
                        if event.key == pygame.K_LEFT:
                            selected_song = (
                                selected_song - 1
                            ) % len(SONGS)
                        else:
                            selected_song = (
                                selected_song + 1
                            ) % len(SONGS)

                        load_selected_song()

                elif event.key == pygame.K_SPACE:
                    if (
                        game_state != "playing"
                        and SONGS
                        and music_loaded
                    ):
                        reset_game()

                elif event.key == pygame.K_r:
                    if (
                        game_state != "playing"
                        and SONGS
                        and music_loaded
                    ):
                        reset_game()

        # ---------------- GAME LOGIC ----------------
        elapsed = 0.0

        if game_state == "playing":
            elapsed = now - game_start

            if elapsed >= GAME_DURATION:
                game_state = "finished"
                finished_time = now
                pygame.mixer.music.stop()
                tiles.clear()

            else:
                speed, spawn_interval = difficulty(elapsed)

                if elapsed - last_spawn >= spawn_interval:
                    lane = random.randrange(LANES)

                    tiles.append({
                        "lane": lane,
                        "y": float(GAME_TOP - TILE_H),
                        "previous_y": float(GAME_TOP - TILE_H),
                        "speed": speed,
                        "hit": False
                    })

                    last_spawn = elapsed

                for tile in tiles[:]:
                    tile["previous_y"] = tile["y"]
                    tile["y"] += tile["speed"] * dt

                    previous_center = tile["previous_y"] + TILE_H / 2
                    current_center = tile["y"] + TILE_H / 2

                    crossed_hit_line = (
                        previous_center <= HIT_Y
                        and current_center >= HIT_Y
                    )

                    if crossed_hit_line and not tile["hit"]:
                        tile_center = lane_center(tile["lane"])
                        bar_left = plate_x - BAR_WIDTH / 2
                        bar_right = plate_x + BAR_WIDTH / 2

                        if bar_left <= tile_center <= bar_right:
                            tile["hit"] = True

                            score += 100 + min(combo, 20) * 5
                            combo += 1
                            best_combo = max(best_combo, combo)
                            hit_flash = 0.15

                            add_particles(
                                tile_center, HIT_Y,
                                LANE_COLORS[tile["lane"]]
                            )

                            tiles.remove(tile)
                            continue

                    if tile["y"] > HIT_Y + TILE_H:
                        tiles.remove(tile)
                        misses += 1
                        combo = 0

        # Automatically return to song selection after results screen.
        if (
            game_state == "finished"
            and now - finished_time >= RESULTS_SCREEN_DURATION
        ):
            game_state = "ready"
            load_selected_song()

        # ---------------- RENDER ----------------
        draw_background()

        if game_state == "playing":
            draw_hud(elapsed)
            draw_tiles()
            draw_plate(plate_x)
            draw_particles(dt)

            if hit_flash > 0:
                pygame.draw.rect(
                    screen, YELLOW,
                    (
                        GAME_LEFT + 3, HIT_Y - 5,
                        GAME_RIGHT - GAME_LEFT - 6, 10
                    )
                )
                hit_flash = max(0.0, hit_flash - dt)

        elif game_state == "ready":
            draw_ready_screen()

        elif game_state == "finished":
            draw_finished_screen()

        draw_camera(cam_surface)

        pygame.display.flip()
        clock.tick(FPS)

finally:
    tracker.stop()
    cap.release()
    pygame.mixer.music.stop()
    pygame.quit()