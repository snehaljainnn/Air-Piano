# Air Tiles

A Real-Time Gesture-Controlled Synthwave Rhythm Game Using Webcam Hand Tracking and Temporal Filtering.

## Team
* Snehal Jain
* Parth Tiwari
* Institution: SVKM NMIMS Indore
* Program: MBA Tech 3rd Year
* Course: Image and Video Processing IVP

## Project Overview
Air Tiles is a retro-synthwave rhythm game in which the player slides a bar left and right with their index finger, tracked by an ordinary webcam, to catch falling tiles. 

Standard webcams capture noisy video at about 30 frames per second FPS, while games must render at 60 FPS to remain smooth. This project solves the resulting lag and stuttering by moving the vision processing into an asynchronous background thread and applying a speed-adaptive One Euro filter. The outcome is a playable, responsive, touch-free game that runs on a standard laptop.

## Key Features
* Touch-Free Interaction: Predicts 21 3D hand landmarks in real-time, mapping the index fingertip to game controls.
* Asynchronous Architecture: Decouples the 30 Hz computer vision thread from the fixed 60 Hz Pygame rendering loop, eliminating frozen frames.
* Advanced Temporal Filtering: Uses a One Euro filter and a frame-rate-independent exponential glide to remove landmark jitter while maintaining fast response times.
* Synthwave Aesthetics: Built with ordered dithering Bayer matrix for sky gradients, alpha compositing for glowing panels, and retro pixel-art text.
* Dynamic Gameplay: Features a 70-second challenge with a linear difficulty ramp increasing tile speed and spawn rates, combo multipliers, and an interactive menu.

## Tech Stack
* Language: Python 3.12
* Computer Vision: OpenCV cv2 for real-time capture, geometric transforms, spatial resampling, and color-space conversions.
* Machine Learning: MediaPipe Hands via cvzone wrapper for lightweight CPU-bound hand tracking.
* Game Engine: Pygame for 60 FPS graphics rendering, input handling, and audio playback.

## How to Run

1. Clone the repository:
bash
git clone [https://github.com/snehaljainnn/Air-Piano.git](https://github.com/snehaljainnn/Air-Piano.git)
cd Air-Piano
Create and activate a virtual environment Recommended:

Bash
python -m venv venv
source venv/bin/activate
Install dependencies:

Bash
pip install -r requirements.txt
Add Music:
Ensure your mp3 files e.g. cheapthrills.mp3 boywithlove.mp3 dancemonkeys.mp3 are placed inside the music directory.

Play:

Bash
python main.py
Controls: Use Left and Right arrows to change tracks, Space to start, F11 to toggle fullscreen, and Q or ESC to quit.

IVP Concepts Applied
Geometric Transformations: Mirroring frames cv2.flip so horizontal movement matches the players physical perspective.

Spatial Resampling: Area interpolation downsampling to 640px to optimize detection speed without severe aliasing.

Temporal Filtering: Speed-adaptive 1 Euro low-pass filter coupled with an exponential glide algorithm for coordinate stabilization.

Color-Space Conversion: Translating BGR webcam frames to RGB for MediaPipe processing and Pygame rendering.

Ordered Dithering: Utilizing a 4x4 Bayer matrix to render a banded pixel-art gradient with minimal colors.
