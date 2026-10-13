
import os
import random
import time
import cv2
import pygame
from cvzone.HandTrackingModule import HandDetector

# ============================================================
# AIR TILES — Gesture Rhythm
# Fullscreen | 50 seconds | Smooth hand tracking | Neon tiles
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_FILE = os.path.join(BASE_DIR, "music", "cheapthrills.mp3")

FPS = 60
GAME_DURATION = 50.0
LANES = 4

# Gradual difficulty increase
START_SPEED = 230
END_SPEED = 540
START_SPAWN = 1.20
END_SPAWN = 0.36

TILE_H = 52
BAR_HEIGHT = 20
BAR_LANE_RATIO = 0.92

# Hand tracking tuning
MAX_BAR_SPEED = 2400.0
HAND_SMOOTHING = 0.72

# Colours
BG = (15, 8, 20)
PANEL = (31, 15, 29)
PLAYFIELD = (24, 12, 24)
WHITE = (250, 242, 255)
MUTED = (164, 139, 160)
CYAN = (30, 220, 255)
PINK = (255, 55, 180)
PURPLE = (165, 90, 255)
GREEN = (70, 255, 170)
LANE_COLORS = [PINK, CYAN, (255, 90, 125), GREEN]

# ============================================================
# INITIALIZATION
# ============================================================

pygame.init()

try:
    pygame.mixer.init()
except pygame.error as exc:
    print("Audio output unavailable:", exc)

# Actual monitor dimensions, rather than a fixed 1100 x 700 window
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
WIDTH, HEIGHT = screen.get_size()

pygame.display.set_caption("AIR TILES | Gesture Rhythm")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("menlo", 20, bold=True)
SMALL = pygame.font.SysFont("menlo", 15)
BIG = pygame.font.SysFont("menlo", 42, bold=True)
TITLE = pygame.font.SysFont("menlo", 48, bold=True)

# Responsive layout: game field on the left, webcam in its own
# right-side panel so it never covers the green lane.
MARGIN = max(24, int(WIDTH * 0.025))
HEADER_H = max(82, int(HEIGHT * 0.12))

CAM_W = min(360, max(280, int(WIDTH * 0.25)))
CAM_H = int(CAM_W * 9 / 16)
CAM_X = WIDTH - CAM_W - MARGIN
CAM_Y = HEADER_H + 35

GAME_LEFT = MARGIN + 115
GAME_RIGHT = CAM_X - 35

# Keep the playfield usable on smaller screens too.
if GAME_RIGHT - GAME_LEFT < 4 * 100:
    GAME_LEFT = MARGIN + 75
    GAME_RIGHT = WIDTH - MARGIN - 30

GAME_TOP = HEADER_H + 65
HIT_Y = HEIGHT - max(105, int(HEIGHT * 0.16))
FIELD_BOTTOM = min(HEIGHT - 45, HIT_Y + 65)

LANE_WIDTH = (GAME_RIGHT - GAME_LEFT) / LANES
BAR_WIDTH = LANE_WIDTH * BAR_LANE_RATIO

detector = HandDetector(detectionCon=0.75, maxHands=2)

# Use a higher camera resolution for more reliable tracking.
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    pygame.quit()
    raise RuntimeError(
        "Webcam not detected. Check your Mac camera permissions."
    )

music_loaded = False
if os.path.isfile(MUSIC_FILE):
    try:
        pygame.mixer.music.load(MUSIC_FILE)
        music_loaded = True
    except pygame.error as exc:
        print("Could not load music:", exc)
else:
    print("Music file not found:", MUSIC_FILE)
    print("Expected file:", MUSIC_FILE)

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

plate_x = (GAME_LEFT + GAME_RIGHT) / 2
target_plate_x = plate_x
hit_flash = 0.0
hit_label_timer = 0.0

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def draw_text(text, font, color, x, y, center=False):
    surface = font.render(str(text), True, color)
    rect = surface.get_rect()

    if center:
        rect.center = (int(x), int(y))
    else:
        rect.topleft = (int(x), int(y))

    screen.blit(surface, rect)


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
    global plate_x, target_plate_x, hit_flash, hit_label_timer

    tiles = []
    particles = []
    score = 0
    combo = 0
    best_combo = 0
    misses = 0
    hit_flash = 0.0
    hit_label_timer = 0.0

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
    for _ in range(16):
        particles.append({
            "x": float(x),
            "y": float(y),
            "vx": random.uniform(-180, 180),
            "vy": random.uniform(-230, 70),
            "life": random.uniform(0.25, 0.55),
            "color": color
        })


def draw_glow_rect(rect, color, radius=9):
    # Small local glow surfaces are much lighter than full-screen
    # transparent surfaces, improving performance at high speeds.
    padding = 12
    glow_rect = rect.inflate(padding * 2, padding * 2)

    glow = pygame.Surface(
        (glow_rect.width, glow_rect.height), pygame.SRCALPHA
    )

    local_rect = pygame.Rect(
        padding, padding, rect.width, rect.height
    )

    pygame.draw.rect(
        glow, (*color, 45),
        local_rect.inflate(12, 12),
        border_radius=radius + 6
    )
    pygame.draw.rect(
        glow, (*color, 85),
        local_rect.inflate(6, 6),
        border_radius=radius + 3
    )

    screen.blit(glow, glow_rect.topleft)
    pygame.draw.rect(screen, color, rect, border_radius=radius)


# ============================================================
# DRAWING
# ============================================================

def draw_background():
    screen.fill(BG)

    # Header
    header = pygame.Rect(
        MARGIN, 20, WIDTH - MARGIN * 2, HEADER_H
    )
    pygame.draw.rect(screen, PANEL, header, border_radius=15)

    draw_text("AIR TILES", TITLE, WHITE, MARGIN + 25, 25)
    draw_text(
        "GESTURE RHYTHM  /  50 SEC CHALLENGE",
        SMALL, MUTED, MARGIN + 28, 25 + TITLE.get_height()
    )

    # Playfield
    field = pygame.Rect(
        GAME_LEFT, GAME_TOP,
        GAME_RIGHT - GAME_LEFT,
        FIELD_BOTTOM - GAME_TOP
    )
    pygame.draw.rect(screen, PLAYFIELD, field, border_radius=12)

    # Lane lines and labels
    for lane in range(LANES):
        x = int(GAME_LEFT + lane * LANE_WIDTH)
        color = LANE_COLORS[lane]

        pygame.draw.line(
            screen, color,
            (x, GAME_TOP), (x, FIELD_BOTTOM), 2
        )

        draw_text(
            str(lane + 1), FONT, color,
            x + 14, GAME_TOP + 10
        )

    pygame.draw.line(
        screen, (80, 45, 75),
        (GAME_RIGHT, GAME_TOP), (GAME_RIGHT, FIELD_BOTTOM), 2
    )

    # Hit line
    pygame.draw.line(
        screen, WHITE,
        (GAME_LEFT, HIT_Y), (GAME_RIGHT, HIT_Y), 3
    )

    draw_text(
        "HIT", SMALL, WHITE,
        GAME_RIGHT - 35, HIT_Y + 12
    )


def draw_hud(elapsed):
    # Compact statistics panel, separate from the lanes.
    panel = pygame.Rect(
        MARGIN, GAME_TOP, 100, min(330, HEIGHT - GAME_TOP - 80)
    )
    pygame.draw.rect(screen, PANEL, panel, border_radius=12)

    draw_text("SCORE", SMALL, MUTED, panel.x + 12, panel.y + 15)
    draw_text(f"{score:06d}", FONT, WHITE, panel.x + 12, panel.y + 40)

    draw_text("COMBO", SMALL, MUTED, panel.x + 12, panel.y + 90)
    draw_text(f"x{combo}", BIG, PINK, panel.x + 12, panel.y + 112)

    draw_text("BEST", SMALL, MUTED, panel.x + 12, panel.y + 180)
    draw_text(best_combo, FONT, WHITE, panel.x + 12, panel.y + 205)

    draw_text("MISSES", SMALL, MUTED, panel.x + 12, panel.y + 245)
    draw_text(misses, FONT, WHITE, panel.x + 12, panel.y + 270)

    remaining = max(0.0, GAME_DURATION - elapsed)
    draw_text(
        f"{remaining:04.1f}s", FONT, WHITE,
        GAME_RIGHT - 90, GAME_TOP - 35
    )

    # Progress bar
    progress = max(0.0, min(1.0, elapsed / GAME_DURATION))
    bar = pygame.Rect(
        GAME_LEFT, GAME_TOP - 25,
        GAME_RIGHT - GAME_LEFT, 7
    )

    pygame.draw.rect(screen, (55, 35, 55), bar, border_radius=4)
    pygame.draw.rect(
        screen, CYAN,
        (bar.x, bar.y, int(bar.width * progress), bar.height),
        border_radius=4
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

        color = LANE_COLORS[tile["lane"]]
        draw_glow_rect(rect, color, 9)

        inner = rect.inflate(-10, -10)
        pygame.draw.rect(
            screen, WHITE, inner,
            width=1, border_radius=5
        )


def draw_plate(x):
    rect = pygame.Rect(
        int(x - BAR_WIDTH / 2),
        int(HIT_Y - BAR_HEIGHT / 2),
        int(BAR_WIDTH),
        BAR_HEIGHT
    )

    draw_glow_rect(rect, CYAN, 8)

    inner = rect.inflate(-12, -8)
    pygame.draw.rect(
        screen, WHITE, inner, border_radius=5
    )


def draw_particles(dt):
    for particle in particles[:]:
        particle["x"] += particle["vx"] * dt
        particle["y"] += particle["vy"] * dt
        particle["vy"] += 350 * dt
        particle["life"] -= dt

        if particle["life"] <= 0:
            particles.remove(particle)
            continue

        radius = max(1, int(5 * particle["life"] / 0.55))
        pygame.draw.circle(
            screen, particle["color"],
            (int(particle["x"]), int(particle["y"])), radius
        )


def draw_camera(frame):
    if frame is None:
        return

    preview = cv2.resize(
        frame, (CAM_W, CAM_H), interpolation=cv2.INTER_LINEAR
    )
    preview = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)

    # frame was already mirrored before hand tracking.
    # Mirror preview too so it behaves like a selfie view.
    preview = cv2.flip(preview, 1)

    surface = pygame.surfarray.make_surface(preview.swapaxes(0, 1))

    # Dedicated webcam panel on the right; it doesn't overlap lanes.
    panel = pygame.Rect(
        CAM_X - 8, CAM_Y - 34, CAM_W + 16, CAM_H + 48
    )
    pygame.draw.rect(screen, PANEL, panel, border_radius=10)

    draw_text("HAND TRACKING", SMALL, CYAN, CAM_X, CAM_Y - 28)
    screen.blit(surface, (CAM_X, CAM_Y))

    pygame.draw.rect(
        screen, CYAN,
        (CAM_X, CAM_Y, CAM_W, CAM_H), 2
    )

    draw_text(
        "Slide your index finger to move the bar",
        SMALL, MUTED, CAM_X, CAM_Y + CAM_H + 14
    )


def draw_ready_screen():
    # Opaque panel ensures lane lines never cross the text.
    panel_w = min(600, GAME_RIGHT - GAME_LEFT - 30)
    panel_h = 220

    panel = pygame.Rect(
        GAME_LEFT + (GAME_RIGHT - GAME_LEFT - panel_w) // 2,
        GAME_TOP + (HIT_Y - GAME_TOP - panel_h) // 2,
        panel_w, panel_h
    )

    pygame.draw.rect(screen, PANEL, panel, border_radius=18)
    pygame.draw.rect(
        screen, (80, 45, 75), panel, 2, border_radius=18
    )

    draw_text(
        "READY TO PLAY?", BIG, WHITE,
        panel.centerx, panel.y + 55, center=True
    )
    draw_text(
        "Press SPACE to start your song",
        FONT, CYAN, panel.centerx, panel.y + 112, center=True
    )
    draw_text(
        "Slide either index finger to move the neon bar",
        SMALL, MUTED, panel.centerx, panel.y + 155, center=True
    )
    draw_text(
        "Q / ESC = quit",
        SMALL, MUTED, panel.centerx, panel.y + 188, center=True
    )


def draw_finished_screen():
    # Result text gets its own opaque panel.
    panel_w = min(560, GAME_RIGHT - GAME_LEFT - 30)
    panel_h = 225

    panel = pygame.Rect(
        GAME_LEFT + (GAME_RIGHT - GAME_LEFT - panel_w) // 2,
        GAME_TOP + (HIT_Y - GAME_TOP - panel_h) // 2,
        panel_w, panel_h
    )

    pygame.draw.rect(screen, PANEL, panel, border_radius=18)
    pygame.draw.rect(
        screen, (80, 45, 75), panel, 2, border_radius=18
    )

    draw_text(
        "RUN COMPLETE", BIG, WHITE,
        panel.centerx, panel.y + 48, center=True
    )
    draw_text(
        f"FINAL SCORE  {score:06d}",
        FONT, CYAN, panel.centerx, panel.y + 105, center=True
    )
    draw_text(
        f"BEST COMBO  x{best_combo}    MISSES  {misses}",
        FONT, PINK, panel.centerx, panel.y + 150, center=True
    )
    draw_text(
        "Press SPACE or R to play again",
        SMALL, MUTED, panel.centerx, panel.y + 190, center=True
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

        # ---------------- CAMERA / HAND TRACKING ----------------
        frame_ok, frame = cap.read()

        if not frame_ok:
            frame = None

        detected_hands = []

        if frame is not None:
            frame = cv2.flip(frame, 1)

            detected_hands, frame = detector.findHands(
                frame, flipType=False, draw=True
            )

        # Use the first detected hand. Either hand is accepted.
        if detected_hands and frame is not None:
            hand = detected_hands[0]
            index_tip = hand["lmList"][8]

            cam_width = frame.shape[1]
            normalized_x = max(
                0.0, min(1.0, index_tip[0] / cam_width)
            )

            target_plate_x = (
                GAME_LEFT + normalized_x * (GAME_RIGHT - GAME_LEFT)
            )

        target_plate_x = max(
            GAME_LEFT + BAR_WIDTH / 2,
            min(GAME_RIGHT - BAR_WIDTH / 2, target_plate_x)
        )

        # Smooth tracking with a maximum movement speed.
        # The bar can catch up even during the faster stages.
        difference = target_plate_x - plate_x
        max_step = MAX_BAR_SPEED * dt
        step = max(-max_step, min(max_step, difference))

        plate_x += step

        # ---------------- INPUT ----------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False

                elif event.key == pygame.K_F11:
                    # Toggle between fullscreen and a regular window.
                    pygame.display.toggle_fullscreen()
                    WIDTH, HEIGHT = screen.get_size()

                elif event.key == pygame.K_SPACE:
                    if game_state != "playing":
                        reset_game()

                elif event.key == pygame.K_r:
                    if game_state != "playing":
                        reset_game()

        # ---------------- GAME LOGIC ----------------
        elapsed = 0.0

        if game_state == "playing":
            elapsed = now - game_start

            if elapsed >= GAME_DURATION:
                game_state = "finished"
                pygame.mixer.music.stop()
                tiles.clear()

            else:
                speed, spawn_interval = difficulty(elapsed)

                # Spawn tiles continuously. A small random offset avoids
                # the same predictable lane sequence.
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

                # Move tiles and test line crossing. Checking previous
                # and current positions prevents fast tiles skipping hits.
                for tile in tiles[:]:
                    tile["previous_y"] = tile["y"]
                    tile["y"] += tile["speed"] * dt

                    previous_center = (
                        tile["previous_y"] + TILE_H / 2
                    )
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

                    # Miss only when the entire tile has passed the line.
                    if tile["y"] > HIT_Y + TILE_H:
                        tiles.remove(tile)
                        misses += 1
                        combo = 0

        # ---------------- RENDER ----------------
        draw_background()

        if game_state == "playing":
            draw_hud(elapsed)
            draw_tiles()
            draw_plate(plate_x)
            draw_particles(dt)

            if hit_flash > 0:
                pygame.draw.line(
                    screen, PINK,
                    (GAME_LEFT, HIT_Y),
                    (GAME_RIGHT, HIT_Y), 5
                )
                hit_flash = max(0.0, hit_flash - dt)

        elif game_state == "ready":
            draw_ready_screen()

        elif game_state == "finished":
            draw_finished_screen()

        draw_camera(frame)

        pygame.display.flip()
        clock.tick(FPS)

finally:
    cap.release()
    pygame.mixer.music.stop()
    pygame.quit()
