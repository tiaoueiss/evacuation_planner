"""
audio.py
--------
Procedurally generated creepy alien audio for the evacuation planner.

We don't ship any audio files with the project. Instead we synthesize
all sounds at startup using numpy, then play them through pygame.mixer.

Generated sounds:
    - ambient_hum   : low pulsing drone, plays in a loop in the background
    - blip          : short alien "click" - played when a node is expanded
    - found         : two-tone chime - played when a path is found
    - failed        : low descending sweep - played when no path exists
    - block         : metallic thud - played when blocking/unblocking an edge
    - alarm         : the warning siren that loops if no path exists

If pygame.mixer can't initialize (no audio device, e.g. running on a
headless server), the module silently falls back to no-op functions
so the rest of the app still works.
"""

import math
import os
import struct

# We want pygame.mixer initialized BEFORE pygame.init for clean audio
import pygame

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


SAMPLE_RATE = 22050
_AUDIO_OK = False
_SOUNDS = {}      # name -> pygame.mixer.Sound
_AMBIENT_CHANNEL = None


def _init_mixer():
    global _AUDIO_OK
    try:
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
        pygame.mixer.init()
        _AUDIO_OK = True
    except Exception as e:
        print(f"[audio] mixer init failed: {e}; running silently")
        _AUDIO_OK = False


# -------------------- waveform generators --------------------

def _to_sound(samples_mono):
    """Convert a mono float32 array in [-1,1] to a stereo pygame Sound."""
    samples = np.clip(samples_mono, -1.0, 1.0)
    # apply a tiny fade-in/fade-out to avoid clicks
    fade = min(int(SAMPLE_RATE * 0.01), len(samples) // 4)
    if fade > 0:
        ramp = np.linspace(0, 1, fade)
        samples[:fade] *= ramp
        samples[-fade:] *= ramp[::-1]
    int_samples = (samples * 32767).astype(np.int16)
    stereo = np.column_stack([int_samples, int_samples])
    return pygame.sndarray.make_sound(stereo)


def _gen_ambient_hum(duration=4.0):
    """A pulsing low drone with subtle noise on top - 'something is alive'."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # two detuned low sines that beat against each other
    drone = (
        0.35 * np.sin(2 * np.pi * 55 * t)
        + 0.25 * np.sin(2 * np.pi * 55.7 * t)
        + 0.15 * np.sin(2 * np.pi * 110.3 * t)
    )
    # slow amplitude pulse
    pulse = 0.5 + 0.5 * np.sin(2 * np.pi * 0.4 * t)
    # tiny breath of noise
    noise = 0.05 * np.random.randn(n)
    sig = (drone * pulse + noise) * 0.5
    return _to_sound(sig)


def _gen_blip(freq=440, duration=0.08):
    """A short alien click for when a node gets expanded."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # frequency drops over the duration ('descending click')
    f = freq * (1.0 - 0.3 * t / duration)
    sig = np.sin(2 * np.pi * f * t)
    # exponential envelope
    env = np.exp(-25 * t / duration)
    sig = sig * env * 0.4
    # add a tiny bit of harmonic for character
    sig += 0.15 * np.sin(2 * np.pi * f * 2 * t) * env
    return _to_sound(sig)


def _gen_found(duration=0.7):
    """Two-tone success chime, but in a minor mode so it still feels uneasy."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    half = n // 2
    sig = np.zeros(n)
    # first note: A4 (440), second note: C5 (523, minor third)
    sig[:half] = np.sin(2 * np.pi * 440 * t[:half])
    sig[half:] = np.sin(2 * np.pi * 523 * t[half:])
    env = np.exp(-3 * t / duration)
    return _to_sound(sig * env * 0.35)


def _gen_failed(duration=0.9):
    """Descending growl - no path found."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    f = 220 * (1.0 - 0.7 * t / duration)  # 220 -> 66 Hz
    sig = np.sin(2 * np.pi * f * t)
    sig += 0.5 * np.sin(2 * np.pi * f * 1.5 * t)
    sig += 0.2 * np.random.randn(n)  # a bit of grit
    env = np.exp(-2 * t / duration)
    return _to_sound(sig * env * 0.4)


def _gen_block(duration=0.15):
    """Metallic thud when blocking/unblocking a road."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # noise burst filtered into a 'clunk'
    sig = np.random.randn(n)
    f = 80
    sig += 1.5 * np.sin(2 * np.pi * f * t)
    env = np.exp(-30 * t / duration)
    return _to_sound(sig * env * 0.35)


def _gen_alarm(duration=2.0):
    """Slow alarm sweep - plays on failure to find a path."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # square-ish oscillating between two pitches
    f = 600 + 200 * np.sin(2 * np.pi * 1.2 * t)
    sig = np.sign(np.sin(2 * np.pi * f * t)) * 0.25
    return _to_sound(sig)


# -------------------- public API --------------------

def init():
    """Call once at startup, before any play_*() call."""
    global _SOUNDS, _AMBIENT_CHANNEL
    if not _HAS_NUMPY:
        print("[audio] numpy not available - running silently")
        return False

    _init_mixer()
    if not _AUDIO_OK:
        return False

    print("[audio] generating procedural sounds...")
    _SOUNDS["ambient"] = _gen_ambient_hum()
    _SOUNDS["blip"]    = _gen_blip()
    _SOUNDS["blip_lo"] = _gen_blip(freq=300, duration=0.06)
    _SOUNDS["blip_hi"] = _gen_blip(freq=600, duration=0.06)
    _SOUNDS["found"]   = _gen_found()
    _SOUNDS["failed"]  = _gen_failed()
    _SOUNDS["block"]   = _gen_block()
    _SOUNDS["alarm"]   = _gen_alarm()
    print(f"[audio] {len(_SOUNDS)} sounds ready")
    return True


def start_ambient():
    """Begin the looping ambient hum on its own channel so it can mix with blips."""
    global _AMBIENT_CHANNEL
    if not _AUDIO_OK or "ambient" not in _SOUNDS:
        return
    _AMBIENT_CHANNEL = _SOUNDS["ambient"].play(loops=-1)
    if _AMBIENT_CHANNEL:
        _AMBIENT_CHANNEL.set_volume(0.45)


def stop_ambient():
    if _AMBIENT_CHANNEL is not None:
        _AMBIENT_CHANNEL.stop()


def play(name, volume=1.0):
    """Play a one-shot sound. Silently no-ops if audio failed to init."""
    if not _AUDIO_OK:
        return
    snd = _SOUNDS.get(name)
    if snd is None:
        return
    ch = snd.play()
    if ch:
        ch.set_volume(volume)


def play_blip_for_floor(floor):
    """Different floors get different blip pitches - feedback for animation."""
    if floor in ("UB2", "UB1"):
        play("blip_lo", volume=0.7)
    elif floor in ("F2", "F3"):
        play("blip_hi", volume=0.6)
    else:
        play("blip", volume=0.6)


def shutdown():
    if _AUDIO_OK:
        try:
            pygame.mixer.stop()
            pygame.mixer.quit()
        except Exception:
            pass
