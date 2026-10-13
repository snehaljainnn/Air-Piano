
import cv2
import pygame
from cvzone.HandTrackingModule import HandDetector

# Initialize audio
pygame.mixer.init()

# Load harmonium samples
sound_map = {
    "Sa": pygame.mixer.Sound("sounds/Sa_C4.wav"),
    "Re": pygame.mixer.Sound("sounds/Re_D4.wav"),
    "Ga": pygame.mixer.Sound("sounds/Ga_E4.wav"),
    "Ma": pygame.mixer.Sound("sounds/Ma_F4.wav"),
    "Pa": pygame.mixer.Sound("sounds/Pa_G4.wav"),
    "Dha": pygame.mixer.Sound("sounds/Dha_A4.wav"),
    "Ni": pygame.mixer.Sound("sounds/Ni_B4.wav"),
    "Sa_high": pygame.mixer.Sound("sounds/Sa2_C5.wav"),
    "Re_high": pygame.mixer.Sound("sounds/Re2_D5.wav"),
    "Ga_high": pygame.mixer.Sound("sounds/Ga2_E5.wav"),
}

# Assign a different note to each finger
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
        "middle": "Sa_high",
        "ring": "Re_high",
        "pinky": "Ga_high",
    },
}

finger_names = ["thumb", "index", "middle", "ring", "pinky"]

# Initialize webcam and hand detector
cap = cv2.VideoCapture(0)
detector = HandDetector(detectionCon=0.8)

# Remember which fingers were raised in the previous frame
prev_states = {
    hand: {finger: 0 for finger in finger_names}
    for hand in finger_notes
}

try:
    while True:
        success, img = cap.read()

        if not success:
            print("Camera not capturing frames.")
            break

        hands, img = detector.findHands(img, draw=True)
        current_hands = set()

        for hand in hands:
            hand_type = hand["type"]
            current_hands.add(hand_type)

            fingers = detector.fingersUp(hand)

            for i, finger in enumerate(finger_names):
                raised = fingers[i]

                # Play only when a finger changes from down to up
                if raised == 1 and prev_states[hand_type][finger] == 0:
                    note_name = finger_notes[hand_type][finger]
                    sound_map[note_name].play()
                    print(f"{hand_type} {finger} -> {note_name}")

                prev_states[hand_type][finger] = raised

        # Reset states when a hand leaves the camera
        for hand_type in finger_notes:
            if hand_type not in current_hands:
                for finger in finger_names:
                    prev_states[hand_type][finger] = 0

        cv2.imshow("Air Piano - Harmonium Sargam", img)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    pygame.mixer.quit()
