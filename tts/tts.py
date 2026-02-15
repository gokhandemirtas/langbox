import subprocess
import time
from pathlib import Path

import numpy as np
import scipy.io.wavfile
from loguru import logger
from pedalboard import Bitcrush, Chorus, Gain, Pedalboard, PitchShift, Reverb
from pocket_tts import TTSModel

voice_ids=[
  "alba",
  "marius",
  "javert",
  "jean",
  "fantine",
  "cosette",
  "eponine",
  "azelma",
]

def _effects(input_path: str, sample_rate: int):
  """Apply cyborg voice effects to a wav file and overwrite it."""
  board = Pedalboard([
    PitchShift(semitones=-4),
    Chorus(rate_hz=2.5, depth=1.5, mix=0.8),
    Bitcrush(bit_depth=10),
    Reverb(room_size=0.2, wet_level=0.4),
    Gain(gain_db=-3),
  ])

  sr, audio = scipy.io.wavfile.read(input_path)
  logger.debug(f"Audio dtype: {audio.dtype}, shape: {audio.shape}, range: [{audio.min():.4f}, {audio.max():.4f}]")

  # Normalize to float32 in [-1, 1] for pedalboard
  if np.issubdtype(audio.dtype, np.integer):
    max_val = np.iinfo(audio.dtype).max
    audio = audio.astype(np.float32) / max_val
  else:
    audio = audio.astype(np.float32)

  # pedalboard expects shape (channels, samples)
  if audio.ndim == 1:
    audio = audio[np.newaxis, :]

  effected = board(audio, sr)

  # Convert back to int16 and write
  effected = np.clip(effected, -1.0, 1.0)
  effected = (effected * np.iinfo(np.int16).max).astype(np.int16)
  effected = effected.squeeze()
  scipy.io.wavfile.write(input_path, sr, effected)
  logger.debug("Applied cyborg voice effects")


def _play():
  try:
    logger.debug("Playing generated audio...")
    # Try different audio players commonly available on Linux
    players = ['aplay', 'paplay', 'ffplay']
    for player in players:
        if subprocess.run(['which', player], capture_output=True).returncode == 0:
            if player == 'ffplay':
                subprocess.run([player, '-nodisp', '-autoexit', "output.wav"],
                              capture_output=True, check=False, timeout=30)
            else:
                subprocess.run([player, "output.wav"], capture_output=True, check=False, timeout=30)
            break
    else:
        print("⚠️ No audio player found (aplay, paplay, or ffplay)")
  except Exception as e:
    logger.error(e)


def speak(text: str, voice_id: str = "eponine"):
  tts_model = TTSModel.load_model()
  try:
    start_time = time.time()
    logger.debug("Generating voice...")

    voice_state = tts_model.get_state_for_audio_prompt(voice_id)
    audio = tts_model.generate_audio(voice_state, text)
    scipy.io.wavfile.write("output.wav", tts_model.sample_rate, audio.numpy())
    logger.debug(f"Voice generation finished in {time.time() - start_time:.2f}s")

    _effects("output.wav", tts_model.sample_rate)
    _play()

  except Exception as e:
    logger.error(e)

if __name__ == "__main__":
  speak("""Pocket TTS is small enough to run directly in your browser in WebAssembly/JavaScript. We don't have official support for this yet, but you can try out one of these community implementations:""")