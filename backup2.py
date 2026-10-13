
import cv2
import pygame
import math
import time
import numpy as np
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

# --- AIR DRUMS ---
drum_kick = pygame.mixer.Sound("sounds/Drum_Kick.wav")
drum_snare = pygame.mixer.Sound("sounds/Drum_Snare.wav")
drum_hihat = pygame.mixer.Sound("sounds/Drum_Hihat.wav")

drum_sounds = {
    "Kick": drum_kick,
    "Snare": drum_snare,
    "Hi-Hat": drum_hihat,
}

# Screen areas for the drum kit
DRUM_ZONE_HEIGHT = 0.48


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

# BGR colors for OpenCV
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

# ==================================================
# 2. CAMERA AND HAND TRACKING
# ==================================================
cap = cv2.VideoCapture(0)
detector = HandDetector(detectionCon=0.8)

prev_states = {
    hand: {finger: 0 for finger in finger_names}
    for hand in finger_notes
}

# Recently triggered notes stay highlighted briefly
note_flash_time = {}
FLASH_DURATION = 0.35

# ==================================================
# 3. DRAW LOTUS-INSPIRED DECORATION
# ==================================================
def draw_lotus(img, cx, cy, size, color):
    """Draw a small decorative lotus using OpenCV shapes."""
    for angle in [-60, -30, 0, 30, 60]:
        radians = math.radians(angle)
        px = int(cx + math.sin(radians) * size * 0.45)
        py = int(cy - math.cos(radians) * size * 0.45)

        cv2.ellipse(
            img,
            (px, py),
            (max(3, size // 5), max(5, size // 2)),
            angle,
            0, 360,
            color,
            1,
            cv2.LINE_AA
        )

    cv2.ellipse(
        img,
        (cx, cy + size // 3),
        (size // 2, max(3, size // 6)),
        0, 0, 180,
        color, 1, cv2.LINE_AA
    )


# ==================================================
# 4. FLOATING SARAGAM KEYBOARD
# ==================================================
def draw_floating_keys(img, active_notes):
    h, w = img.shape[:2]
    now = time.time()

    margin = int(w * 0.025)
    gap = max(3, int(w * 0.003))
    count = len(key_data)
    key_width = (w - 2 * margin - gap * (count - 1)) // count
    key_height = max(65, int(h * 0.19))

    y2 = h - int(h * 0.055)
    y1 = y2 - key_height

    # Dark translucent panel
    overlay = img.copy()
    cv2.rectangle(
        overlay,
        (margin - 12, y1 - 48),
        (w - margin + 12, y2 + 10),
        (35, 25, 43),
        -1
    )
    cv2.addWeighted(overlay, 0.78, img, 0.22, 0, img)

    # Header
    cv2.putText(
        img,
        "INDIAN CLASSICAL  |  SARAGAM",
        (margin, y1 - 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (225, 210, 245),
        1,
        cv2.LINE_AA
    )

    for i, (label, color) in enumerate(key_data):
        x1 = margin + i * (key_width + gap)
        x2 = x1 + key_width

        active = label in active_notes

        # Gentle continuous floating motion
        phase = now * 2.5 + i * 0.7
        float_offset = int(4 * (1 + math.sin(phase)))

        # Brief highlight after a note is triggered
        flashed = now - note_flash_time.get(label, 0) < FLASH_DURATION
        illuminated = active or flashed

        lift = float_offset + (12 if illuminated else 0)
        top = y1 - lift
        bottom = y2 - lift

        # Soft glow around active keys
        if illuminated:
            glow = img.copy()

            for thickness in (18, 12, 6):
                cv2.rectangle(
                    glow,
                    (x1 - 2, top - 2),
                    (x2 + 2, bottom + 2),
                    color,
                    thickness
                )

            cv2.addWeighted(glow, 0.30, img, 0.70, 0, img)

        # Ivory keys when idle; rich color when playing
        body_color = color if illuminated else (225, 216, 202)
        cv2.rectangle(img, (x1, top), (x2, bottom), body_color, -1)

        # Colored key border
        cv2.rectangle(
            img,
            (x1, top),
            (x2, bottom),
            color,
            3 if illuminated else 2,
            cv2.LINE_AA
        )

        # Decorative highlight
        cv2.line(
            img,
            (x1 + 6, top + 6),
            (x2 - 6, top + 6),
            (255, 245, 225),
            2,
            cv2.LINE_AA
        )

        # Small lotus emblem
        draw_lotus(
            img,
            (x1 + x2) // 2,
            top + 24,
            max(10, min(17, key_width // 5)),
            (255, 245, 225) if illuminated else color
        )

        # Sargam label
        font_scale = 0.55 if key_width < 90 else 0.7
        text_size = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_DUPLEX, font_scale, 2
        )[0]

        tx = x1 + (key_width - text_size[0]) // 2
        ty = top + (bottom - top + text_size[1]) // 2 + 10

        text_color = (255, 255, 255) if illuminated else (55, 42, 53)

        cv2.putText(
            img,
            label,
            (tx, ty),
            cv2.FONT_HERSHEY_DUPLEX,
            font_scale,
            text_color,
            2,
            cv2.LINE_AA
        )

    # Live status panel
    if active_notes:
        status = "PLAYING  |  " + "  ".join(sorted(active_notes))
        status_color = (140, 255, 190)
    else:
        status = "READY  |  Raise a finger to play"
        status_color = (230, 215, 245)

    cv2.putText(
        img,
        status,
        (margin, max(25, y1 - 57)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        status_color,
        2,
        cv2.LINE_AA
    )


# ==================================================
# 5. MAIN LOOP
# ==================================================
try:
    while True:
        success, img = cap.read()

        if not success:
            print("Camera not capturing frames.")
            break

        # Mirror the webcam for natural interaction
        img = cv2.flip(img, 1)

        hands, img = detector.findHands(img, draw=True)

        current_hands = set()
        active_notes = set()

        for hand in hands:
            hand_type = hand["type"]
            current_hands.add(hand_type)

            fingers = detector.fingersUp(hand)

            for i, finger in enumerate(finger_names):
                raised = fingers[i]
                note_name = finger_notes[hand_type][finger]

                if raised:
                    active_notes.add(note_name)

                # Play once when finger transitions from down to up
                if raised == 1 and prev_states[hand_type][finger] == 0:
                    sound_map[note_name].play()
                    note_flash_time[note_name] = time.time()

                    print(f"{hand_type} {finger} -> {note_name}")

                prev_states[hand_type][finger] = raised

        # Reset states when a hand disappears
        for hand_type in finger_notes:
            if hand_type not in current_hands:
                for finger in finger_names:
                    prev_states[hand_type][finger] = 0

        draw_floating_keys(img, active_notes)

        cv2.imshow("Air Piano | Indian Classical Mode", img)

        # Press Q to exit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    pygame.mixer.quit()
