import subprocess
import time

import scipy.io.wavfile
from loguru import logger
from pocket_tts import TTSModel


def speak(text: str, voice_id: str = "marius"):
  tts_model = TTSModel.load_model(voice_cloning=False)
  try:
    start_time = time.time()
    logger.debug("Generating voice...")
    audio = tts_model.generate_audio(voice_id, text)
# Audio is a 1D torch tensor containing PCM data.
    scipy.io.wavfile.write("output.wav", tts_model.sample_rate, audio.numpy())
    logger.debug(f"Voice generation finished in {time.time() - start_time:.2f}s")

    subprocess.run(["ffplay", "-nodisp", "-autoexit", "output.wav"])

  except Exception as e:
    logger.error(e)

