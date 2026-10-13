
import cv2
import pygame
import math
import time
from cvzone.HandTrackingModule import HandDetector

# ==================================================
# 1. AUDIO SETUP
# ==================================================
pygame.mixer.init()

sound_map = {
    "Sa": pygame.mixer.Sound("sounds/Sa_C4.wav"),
    "Re": pygame.mixer.Sound("sounds/Re_D4.wav"),
    "Ga": pygame.mixer.Sound("sounds/Ga_E4.wav"),
    "Ma": pygame.mixer.Sound("sounds/Ma_F4.wav"),
    "Pa": pygame.mixer.Sound("sounds/Pa_G4.wav"),
    "Dha": pygame.mixer.Sound("sounds/Dha_A4.wav"),
    "Ni": pygame.mixer.Sound("sounds/Ni_B4.wav"),
    "Sa'": pygame.mixer.Sound("sounds/Sa2_C5.wav"),
    "Re'": pygame.mixer.Sound("sounds/Re2_D5.wav"),
    "Ga'": pygame.mixer.Sound("sounds/Ga2_E5.wav"),
}

drum_sounds = {
    "KICK": pygame.mixer.Sound("sounds/Drum_Kick.wav"),
    "SNARE": pygame.mixer.Sound("sounds/Drum_Snare.wav"),
    "HI-HAT": pygame.mixer.Sound("sounds/Drum_Hihat.wav"),
}

# Separate piano and drum audio channels so they can overlap.
for sound in sound_map.values():
    sound.set_volume(0.45)

for sound in drum_sounds.values():
    sound.set_volume(0.65)

# ==================================================
# 2. SETTINGS
# ==================================================
cap = cv2.VideoCapture(0)
detector = HandDetector(detectionCon=0.8, maxHands=2)

finger_names = ["thumb", "index", "middle", "ring", "pinky"]

finger_notes = {
    "Left": {
        "thumb": "Sa",
        "index": "Re",
        "middle": "Ga",
        "ring": "Ma",
        "pinky": "Pa",
    },
    "Right": {
        "thumb": "Dha",
        "index": "Ni",
        "middle": "Sa'",
        "ring": "Re'",
        "pinky": "Ga'",
    },
}

key_data = [
    ("Sa",  (190, 115, 35)),
    ("Re",  (75, 165, 65)),
    ("Ga",  (20, 165, 225)),
    ("Ma",  (35, 105, 235)),
    ("Pa",  (185, 70, 175)),
    ("Dha", (205, 90, 125)),
    ("Ni",  (175, 100, 220)),
    ("Sa'", (210, 160, 70)),
    ("Re'", (90, 190, 240)),
    ("Ga'", (150, 200, 245)),
]

prev_states = {
    hand: {finger: 0 for finger in finger_names}
    for hand in finger_notes
}

note_flash_time = {}
drum_flash_time = {}
previous_index_y = {}
last_drum_hit = {}

FLASH_DURATION = 0.35
DRUM_COOLDOWN = 0.35

# ==================================================
# 3. DRAW DRUM KIT
# ==================================================
def draw_drum_kit(img):
    h, w = img.shape[:2]
    now = time.time()

    # Keep the drums well above the piano.
    panel_y1 = int(h * 0.055)
    panel_y2 = int(h * 0.43)

    overlay = img.copy()
    cv2.rectangle(
        overlay,
        (int(w * 0.06), panel_y1),
        (int(w * 0.94), panel_y2),
        (28, 23, 43),
        -1
    )
    cv2.addWeighted(overlay, 0.72, img, 0.28, 0, img)

    cv2.putText(
        img,
        "AIR ORCHESTRA  |  DRUM ZONE",
        (int(w * 0.08), int(h * 0.10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (235, 225, 255),
        2,
        cv2.LINE_AA
    )

    pad_info = [
        ("KICK", 0.25, (220, 125, 75)),
        ("SNARE", 0.50, (100, 175, 255)),
        ("HI-HAT", 0.75, (160, 235, 190)),
    ]

    for name, fraction, color in pad_info:
        cx = int(w * fraction)
        cy = int(h * 0.265)
        radius = max(28, int(min(w, h) * 0.075))

        flashed = now - drum_flash_time.get(name, 0) < FLASH_DURATION

        # Outer glow on impact.
        if flashed:
            glow = img.copy()
            cv2.circle(glow, (cx, cy), radius + 18, color, 12, cv2.LINE_AA)
            cv2.addWeighted(glow, 0.35, img, 0.65, 0, img)

        # Layered circular drum pad.
        fill = color if flashed else (65, 54, 78)
        cv2.circle(img, (cx, cy), radius, fill, -1, cv2.LINE_AA)
        cv2.circle(
            img, (cx, cy), radius,
            color, 4 if flashed else 2, cv2.LINE_AA
        )
        cv2.circle(
            img, (cx, cy), int(radius * 0.68),
            (235, 235, 245) if flashed else color,
            2, cv2.LINE_AA
        )

        label_size = cv2.getTextSize(
            name, cv2.FONT_HERSHEY_DUPLEX, 0.65, 2
        )[0]

        cv2.putText(
            img, name,
            (cx - label_size[0] // 2, cy + radius + 30),
            cv2.FONT_HERSHEY_DUPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

    cv2.putText(
        img,
        "Move your index fingertip DOWN to strike a pad",
        (int(w * 0.08), int(h * 0.405)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (220, 210, 235),
        1,
        cv2.LINE_AA
    )


# ==================================================
# 4. DRAW FLOATING SARAGAM KEYBOARD
# ==================================================
def draw_floating_keys(img, active_notes):
    h, w = img.shape[:2]
    now = time.time()

    margin = int(w * 0.025)
    gap = max(3, int(w * 0.003))
    count = len(key_data)
    key_width = (w - 2 * margin - gap * (count - 1)) // count
    key_height = max(65, int(h * 0.19))

    y2 = h - int(h * 0.035)
    y1 = y2 - key_height

    overlay = img.copy()
    cv2.rectangle(
        overlay,
        (margin - 8, y1 - 42),
        (w - margin + 8, y2 + 5),
        (35, 25, 43),
        -1
    )
    cv2.addWeighted(overlay, 0.78, img, 0.22, 0, img)

    cv2.putText(
        img,
        "INDIAN CLASSICAL  |  SARAGAM",
        (margin, y1 - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (225, 210, 245),
        1,
        cv2.LINE_AA
    )

    for i, (label, color) in enumerate(key_data):
        x1 = margin + i * (key_width + gap)
        x2 = x1 + key_width

        flashed = now - note_flash_time.get(label, 0) < FLASH_DURATION
        illuminated = label in active_notes or flashed

        phase = now * 2.5 + i * 0.7
        float_offset = int(3 * (1 + math.sin(phase)))
        lift = float_offset + (8 if illuminated else 0)

        top = y1 - lift
        bottom = y2 - lift

        if illuminated:
            glow = img.copy()
            cv2.rectangle(
                glow, (x1 - 2, top - 2), (x2 + 2, bottom + 2),
                color, 10
            )
            cv2.addWeighted(glow, 0.25, img, 0.75, 0, img)

        body_color = color if illuminated else (225, 216, 202)
        cv2.rectangle(img, (x1, top), (x2, bottom), body_color, -1)
        cv2.rectangle(
            img, (x1, top), (x2, bottom),
            color, 3 if illuminated else 2, cv2.LINE_AA
        )

        font_scale = 0.48 if key_width < 65 else 0.65
        text_size = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_DUPLEX, font_scale, 2
        )[0]
        tx = x1 + (key_width - text_size[0]) // 2
        ty = top + (bottom - top + text_size[1]) // 2

        cv2.putText(
            img, label, (tx, ty),
            cv2.FONT_HERSHEY_DUPLEX,
            font_scale,
            (255, 255, 255) if illuminated else (55, 42, 53),
            2, cv2.LINE_AA
        )

    status = (
        "PLAYING: " + "  ".join(sorted(active_notes))
        if active_notes else "PIANO ZONE  |  Raise fingers to play"
    )
    cv2.putText(
        img, status,
        (margin, max(22, y1 - 48)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.48,
        (140, 255, 190) if active_notes else (230, 215, 245),
        1, cv2.LINE_AA
    )


# ==================================================
# 5. MAIN LOOP
# ==================================================
try:
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Check camera permissions.")

    while True:
        success, img = cap.read()

        if not success:
            print("Camera not capturing frames.")
            break

        img = cv2.flip(img, 1)
        h, w = img.shape[:2]

        hands, img = detector.findHands(img, draw=True)

        active_notes = set()
        current_hands = set()

        # Draw both instrument zones.
        draw_drum_kit(img)

        for hand in hands:
            hand_type = hand["type"]
            current_hands.add(hand_type)

            # Index fingertip landmark.
            index_tip = hand["lmList"][8]
            tip_x, tip_y = int(index_tip[0]), int(index_tip[1])

            # ------------------------------------------
            # DRUM GESTURE: downward index-finger strike
            # ------------------------------------------
            previous_y = previous_index_y.get(hand_type)

            if previous_y is not None:
                moving_down = tip_y - previous_y > 12
                in_drum_zone = tip_y < int(h * 0.43)

                if moving_down and in_drum_zone:
                    now = time.time()

                    if now - last_drum_hit.get(hand_type, 0) > DRUM_COOLDOWN:
                        if tip_x < w / 3:
                            drum_name = "KICK"
                        elif tip_x < 2 * w / 3:
                            drum_name = "SNARE"
                        else:
                            drum_name = "HI-HAT"

                        drum_sounds[drum_name].play()
                        drum_flash_time[drum_name] = now
                        last_drum_hit[hand_type] = now

                        print(f"DRUM HIT -> {drum_name}")

            previous_index_y[hand_type] = tip_y

            # ------------------------------------------
            # PIANO GESTURE: only in lower screen zone
            # ------------------------------------------
            center_y = hand["center"][1]
            in_piano_zone = center_y > int(h * 0.52)

            fingers = detector.fingersUp(hand)

            for i, finger in enumerate(finger_names):
                note_name = finger_notes[hand_type][finger]

                # Ignore raised fingers when the hand is in drum zone.
                raised = fingers[i] if in_piano_zone else 0

                if raised:
                    active_notes.add(note_name)

                if raised == 1 and prev_states[hand_type][finger] == 0:
                    sound_map[note_name].play()
                    note_flash_time[note_name] = time.time()
                    print(f"PIANO -> {hand_type} {finger} -> {note_name}")

                prev_states[hand_type][finger] = raised

        # Reset tracking when a hand disappears.
        for hand_type in finger_notes:
            if hand_type not in current_hands:
                previous_index_y.pop(hand_type, None)

                for finger in finger_names:
                    prev_states[hand_type][finger] = 0

        draw_floating_keys(img, active_notes)

        cv2.imshow("Air Orchestra | Piano + Drums", img)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    pygame.mixer.quit()
