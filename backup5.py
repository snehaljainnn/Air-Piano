
import os
import random
import time

import cv2
import pygame
from cvzone.HandTrackingModule import HandDetector


# =========================================================
# CONFIGURATION
# =========================================================

WIDTH, HEIGHT = 1100, 700
FPS = 60
GAME_DURATION = 50.0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_FILE = os.path.join(BASE_DIR, "music", "cheapthrills.mp3")

LANES = 4
GAME_LEFT = 150
GAME_RIGHT = 950
GAME_TOP = 150
HIT_Y = 565

TILE_H = 52
LANE_WIDTH = (GAME_RIGHT - GAME_LEFT) / LANES

BAR_WIDTH = LANE_WIDTH * 0.92
BAR_HEIGHT = 20

START_SPEED = 230
END_SPEED = 540
START_SPAWN = 1.20
END_SPAWN = 0.36

CAMERA_WIDTH = 320
CAMERA_HEIGHT = 180

# =========================================================
# INITIALIZATION
# =========================================================

pygame.init()
pygame.mixer.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AIR TILES | Gesture Rhythm")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("menlo", 20, bold=True)
SMALL = pygame.font.SysFont("menlo", 15)
BIG = pygame.font.SysFont("menlo", 42, bold=True)

BG = (15, 8, 20)
PANEL = (31, 15, 29)
WHITE = (250, 242, 255)
MUTED = (164, 139, 160)
CYAN = (30, 220, 255)
PINK = (255, 55, 180)
GREEN = (70, 255, 170)

LANE_COLORS = [
    PINK,
    CYAN,
    (255, 90, 125),
    GREEN
]

detector = HandDetector(detectionCon=0.75, maxHands=2)
cap = cv2.VideoCapture(0)

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
    print("Expected location:", MUSIC_FILE)
    print("Update MUSIC_FILE to match your audio filename.")

# =========================================================
# GAME STATE
# =========================================================

tiles = []
particles = []

score = 0
combo = 0
best_combo = 0
misses = 0

game_state = "ready"
game_start = 0.0
last_spawn = 0.0

plate_x = (GAME_LEFT + GAME_RIGHT) // 2
hit_flash = 0.0


# =========================================================
# HELPER FUNCTIONS
# =========================================================

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

    speed = START_SPEED + (
        END_SPEED - START_SPEED
    ) * progress

    spawn_interval = START_SPAWN + (
        END_SPAWN - START_SPAWN
    ) * progress

    return speed, spawn_interval


def reset_game():
    global tiles, particles
    global score, combo, best_combo, misses
    global game_state, game_start, last_spawn
    global hit_flash, plate_x

    tiles = []
    particles = []

    score = 0
    combo = 0
    best_combo = 0
    misses = 0

    hit_flash = 0.0
    plate_x = (GAME_LEFT + GAME_RIGHT) // 2

    # Start the game timer and music together as closely as possible.
    if music_loaded:
        pygame.mixer.music.stop()
        pygame.mixer.music.play(-1)

    game_start = time.perf_counter()
    last_spawn = 0.0
    game_state = "playing"


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
    # Lightweight neon outline effect.
    pygame.draw.rect(
        screen,
        color,
        rect.inflate(8, 8),
        width=2,
        border_radius=radius + 4
    )

    pygame.draw.rect(
        screen,
        color,
        rect,
        border_radius=radius
    )


# =========================================================
# BACKGROUND AND PLAYFIELD
# =========================================================

def draw_background():
    screen.fill(BG)

    # Header
    pygame.draw.rect(
        screen,
        PANEL,
        (25, 20, WIDTH - 50, 88),
        border_radius=14
    )

    draw_text("AIR TILES", BIG, WHITE, 48, 30)

    draw_text(
        "GESTURE RHYTHM  /  50 SEC CHALLENGE",
        SMALL, MUTED, 51, 78
    )

    # Playfield
    pygame.draw.rect(
        screen,
        (24, 12, 24),
        (
            GAME_LEFT,
            GAME_TOP,
            GAME_RIGHT - GAME_LEFT,
            HIT_Y + 55 - GAME_TOP
        ),
        border_radius=12
    )

    # Lane dividers are drawn before UI text.
    for lane in range(LANES):
        x = int(GAME_LEFT + lane * LANE_WIDTH)
        color = LANE_COLORS[lane]

        pygame.draw.line(
            screen,
            color,
            (x, GAME_TOP),
            (x, HIT_Y + 55),
            2
        )

        draw_text(
            str(lane + 1),
            FONT,
            color,
            x + 14,
            GAME_TOP + 10
        )

    pygame.draw.line(
        screen,
        (70, 40, 67),
        (GAME_RIGHT, GAME_TOP),
        (GAME_RIGHT, HIT_Y + 55),
        2
    )

    pygame.draw.line(
        screen,
        WHITE,
        (GAME_LEFT, HIT_Y),
        (GAME_RIGHT, HIT_Y),
        3
    )

    draw_text(
        "HIT ZONE",
        SMALL,
        WHITE,
        GAME_RIGHT + 12,
        HIT_Y - 9
    )


# =========================================================
# SCORE AND TIMER HUD
# =========================================================

def draw_hud(elapsed):
    panel_rect = pygame.Rect(25, 145, 108, 300)

    pygame.draw.rect(
        screen, PANEL, panel_rect, border_radius=12
    )

    draw_text("SCORE", SMALL, MUTED, 40, 165)
    draw_text(f"{score:06d}", FONT, WHITE, 40, 192)

    draw_text("COMBO", SMALL, MUTED, 40, 245)
    draw_text(f"x{combo}", BIG, PINK, 40, 268)

    draw_text("BEST", SMALL, MUTED, 40, 335)
    draw_text(best_combo, FONT, WHITE, 40, 362)

    draw_text("MISSES", SMALL, MUTED, 40, 405)
    draw_text(misses, FONT, WHITE, 40, 426)

    remaining = max(0.0, GAME_DURATION - elapsed)

    draw_text(
        f"{remaining:04.1f}s",
        FONT,
        WHITE,
        WIDTH - 145,
        125
    )

    progress = max(
        0.0,
        min(1.0, elapsed / GAME_DURATION)
    )

    progress_rect = pygame.Rect(
        GAME_LEFT, 120, GAME_RIGHT - GAME_LEFT, 8
    )

    pygame.draw.rect(
        screen, (55, 35, 55),
        progress_rect, border_radius=4
    )

    pygame.draw.rect(
        screen,
        CYAN,
        (
            progress_rect.x,
            progress_rect.y,
            int(progress_rect.width * progress),
            progress_rect.height
        ),
        border_radius=4
    )


# =========================================================
# TILES AND PARTICLES
# =========================================================

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

        pygame.draw.rect(
            screen,
            WHITE,
            rect.inflate(-10, -10),
            width=1,
            border_radius=5
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

        radius = max(
            1,
            int(5 * particle["life"] / 0.55)
        )

        pygame.draw.circle(
            screen,
            particle["color"],
            (
                int(particle["x"]),
                int(particle["y"])
            ),
            radius
        )


# =========================================================
# PLAYER PLATE
# =========================================================

def draw_plate(x):
    rect = pygame.Rect(
        int(x - BAR_WIDTH / 2),
        HIT_Y - BAR_HEIGHT // 2,
        int(BAR_WIDTH),
        BAR_HEIGHT
    )

    draw_glow_rect(rect, CYAN, 10)

    pygame.draw.rect(
        screen,
        WHITE,
        rect.inflate(-12, -8),
        border_radius=5
    )


# =========================================================
# WEBCAM PREVIEW
# =========================================================

def draw_camera(frame):
    if frame is None:
        return

    preview = cv2.resize(
        frame,
        (CAMERA_WIDTH, CAMERA_HEIGHT),
        interpolation=cv2.INTER_LINEAR
    )

    preview = cv2.cvtColor(
        preview, cv2.COLOR_BGR2RGB
    )

    # Frame is already mirrored before hand detection.
    surface = pygame.surfarray.make_surface(
        preview.swapaxes(0, 1)
    )

    x = WIDTH - CAMERA_WIDTH - 25
    y = HEIGHT - CAMERA_HEIGHT - 25

    label_rect = pygame.Rect(
        x, y - 28, CAMERA_WIDTH, 25
    )

    pygame.draw.rect(screen, PANEL, label_rect)

    draw_text(
        "HAND TRACKING",
        SMALL,
        CYAN,
        x + 5,
        y - 25
    )

    screen.blit(surface, (x, y))

    pygame.draw.rect(
        screen,
        CYAN,
        (x, y, CAMERA_WIDTH, CAMERA_HEIGHT),
        2
    )


# =========================================================
# MAIN LOOP
# =========================================================

running = True
previous_time = time.perf_counter()

while running:
    now = time.perf_counter()

    dt = min(now - previous_time, 0.05)
    previous_time = now

    # Read webcam
    frame_ok, frame = cap.read()

    if not frame_ok:
        frame = None

    detected_hands = []

    if frame is not None:
        # Mirror the frame once for natural controls.
        frame = cv2.flip(frame, 1)

        detected_hands, frame = detector.findHands(
            frame,
            flipType=False,
            draw=True
        )

    # -----------------------------------------------------
    # INDEX FINGER CONTROLS THE PLATE
    # -----------------------------------------------------

    if detected_hands:
        # Use either detected hand.
        hand = detected_hands[0]
        index_tip = hand["lmList"][8]

        cam_width = frame.shape[1]

        normalized_x = max(
            0.0,
            min(1.0, index_tip[0] / cam_width)
        )

        plate_x = (
            GAME_LEFT
            + normalized_x * (GAME_RIGHT - GAME_LEFT)
        )

    plate_x = max(
        GAME_LEFT + BAR_WIDTH / 2,
        min(
            GAME_RIGHT - BAR_WIDTH / 2,
            plate_x
        )
    )

    # -----------------------------------------------------
    # EVENTS
    # -----------------------------------------------------

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key in (
                pygame.K_q,
                pygame.K_ESCAPE
            ):
                running = False

            elif event.key == pygame.K_SPACE:
                if game_state != "playing":
                    reset_game()

            elif event.key == pygame.K_r:
                if game_state != "playing":
                    reset_game()

    # -----------------------------------------------------
    # GAME LOGIC
    # -----------------------------------------------------

    elapsed = (
        now - game_start
        if game_state == "playing"
        else 0.0
    )

    if game_state == "playing":
        elapsed = now - game_start

        if elapsed >= GAME_DURATION:
            game_state = "finished"
            pygame.mixer.music.stop()

        else:
            speed, spawn_interval = difficulty(elapsed)

            # Generate new tiles continuously.
            if elapsed - last_spawn >= spawn_interval:
                lane = random.randrange(LANES)

                tiles.append({
                    "lane": lane,
                    "y": float(GAME_TOP - TILE_H),
                    "speed": speed
                })

                last_spawn = elapsed

            # Move tiles and detect collisions.
            for tile in tiles[:]:
                previous_y = tile["y"]
                tile["y"] += tile["speed"] * dt

                previous_bottom = previous_y + TILE_H
                current_bottom = tile["y"] + TILE_H

                # Detect the tile crossing the hit line,
                # even when it moves quickly between frames.
                crossed_hit_line = (
                    previous_bottom < HIT_Y
                    and current_bottom >= HIT_Y
                )

                if crossed_hit_line:
                    tile_center_x = lane_center(tile["lane"])

                    tile_left = (
                        tile_center_x - LANE_WIDTH * 0.34
                    )

                    tile_right = (
                        tile_center_x + LANE_WIDTH * 0.34
                    )

                    bar_left = plate_x - BAR_WIDTH / 2
                    bar_right = plate_x + BAR_WIDTH / 2

                    # Collision uses actual horizontal overlap.
                    overlaps_bar = (
                        tile_right >= bar_left
                        and tile_left <= bar_right
                    )

                    if overlaps_bar:
                        score += 100 + min(combo, 20) * 5

                        combo += 1
                        best_combo = max(best_combo, combo)

                        hit_flash = 0.15

                        add_particles(
                            tile_center_x,
                            HIT_Y,
                            LANE_COLORS[tile["lane"]]
                        )

                        tiles.remove(tile)
                        continue

                # Miss a tile after it has passed the hit line.
                if tile["y"] > HIT_Y:
                    tiles.remove(tile)
                    misses += 1
                    combo = 0

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    draw_background()

    if game_state == "playing":
        draw_tiles()
        draw_plate(plate_x)
        draw_hud(elapsed)
        draw_particles(dt)

        if hit_flash > 0:
            pygame.draw.line(
                screen,
                PINK,
                (GAME_LEFT, HIT_Y),
                (GAME_RIGHT, HIT_Y),
                5
            )

            hit_flash = max(0.0, hit_flash - dt)

    elif game_state == "ready":
        panel = pygame.Rect(250, 310, 600, 190)

        pygame.draw.rect(
            screen, PANEL, panel, border_radius=18
        )

        pygame.draw.rect(
            screen, (80, 45, 75),
            panel, 2, border_radius=18
        )

        draw_text(
            "READY TO PLAY?",
            BIG, WHITE,
            WIDTH // 2, 350, center=True
        )

        draw_text(
            "Press SPACE to start your song",
            FONT, CYAN,
            WIDTH // 2, 400, center=True
        )

        draw_text(
            "Slide either index finger to move the neon bar",
            SMALL, MUTED,
            WIDTH // 2, 440, center=True
        )

        draw_text(
            "Q / ESC = quit",
            SMALL, MUTED,
            WIDTH // 2, 470, center=True
        )

    elif game_state == "finished":
        panel = pygame.Rect(250, 310, 600, 210)

        pygame.draw.rect(
            screen, PANEL, panel, border_radius=18
        )

        pygame.draw.rect(
            screen, (80, 45, 75),
            panel, 2, border_radius=18
        )

        draw_text(
            "RUN COMPLETE",
            BIG, WHITE,
            WIDTH // 2, 350, center=True
        )

        draw_text(
            f"FINAL SCORE  {score:06d}",
            FONT, CYAN,
            WIDTH // 2, 400, center=True
        )

        draw_text(
            f"BEST COMBO  x{best_combo}     MISSES  {misses}",
            FONT, PINK,
            WIDTH // 2, 440, center=True
        )

        draw_text(
            "Press SPACE or R to play again",
            SMALL, MUTED,
            WIDTH // 2, 480, center=True
        )

    # Keep webcam preview on top of the game UI.
    draw_camera(frame)

    pygame.display.flip()
    clock.tick(FPS)


# =========================================================
# CLEANUP
# =========================================================

cap.release()
pygame.mixer.music.stop()
pygame.quit()
