import subprocess
import time

import scipy.io.wavfile
from loguru import logger
from pedalboard import Bitcrush, Chorus, Distortion, Pedalboard, Phaser, PitchShift
from pedalboard.io import AudioFile
from pocket_tts import TTSModel
import torch

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

active_voice_id = "eponine"
timeout = 300

def _effects(input_path: str):
  """Apply cyborg voice effects to a wav file and overwrite it."""

  output_path = "output.wav"

  with AudioFile(input_path) as f:
      audio = f.read(f.frames)
      samplerate = f.samplerate

  board = Pedalboard([
    Phaser(rate_hz=1.0, depth=0.4), Chorus(rate_hz=0.6, depth=0.2, mix=0.4)
  ])

  processed = board(audio, samplerate)

  with AudioFile(output_path, 'w', samplerate, processed.shape[0]) as f:
      f.write(processed)

  logger.debug("Applied voice effects")


def _play():
  try:
    logger.debug("Playing generated audio...")
    # Try different audio players commonly available on Linux
    players = ['aplay', 'paplay', 'ffplay']
    for player in players:
      if subprocess.run(['which', player], capture_output=True).returncode == 0:
        if player == 'ffplay':
          subprocess.run([player, '-nodisp', '-autoexit', "output.wav"],
                        capture_output=True, check=False, timeout=timeout)
        else:
          subprocess.run([player, "output.wav"], capture_output=True, check=False, timeout=timeout)
        break
    else:
      logger.error("⚠️ No audio player found (aplay, paplay, or ffplay)")
  except Exception as e:
    logger.error(e)


def speak(text: str, voice_id: str = active_voice_id):
  tts_model = TTSModel.load_model()
  try:
    start_time = time.time()
    logger.debug("Generating voice...")

    sentences = [s.strip() for s in text.split(".") if s.strip()]
    audios = []
    voice_state = tts_model.get_state_for_audio_prompt(voice_id)

    for sentence in sentences:
      audio = tts_model.generate_audio(voice_state, sentence)
      logger.debug(sentence)
      audios.append(audio)

    full_audio = torch.cat(audios, dim=0)

    scipy.io.wavfile.write("output.wav", tts_model.sample_rate, full_audio.numpy())
    logger.debug(f"Voice generation finished in {time.time() - start_time:.2f}s")

    _effects("output.wav")
    _play()

  except Exception as e:
    logger.error(e)

if __name__ == "__main__":
  speak("""Pocket TTS is small enough to run directly in your browser in WebAssembly/JavaScript. We don't have official support for this yet, but you can try out one of these community implementations:""")