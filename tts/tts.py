import os
import subprocess
import time

import numpy as np
import scipy.io.wavfile
from loguru import logger
from pocket_tts import TTSModel

voice_ids = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]
active_voice_id = "azelma"

def synthesise(text: str, output_path: str, voice_id: str = active_voice_id) -> str:
    if not text:
        raise ValueError("No text provided for TTS")
    
    logger.debug(f"Synthesizing {text}")

    tts_model = TTSModel.load_model(temp=0.5, lsd_decode_steps=7, eos_threshold=-1.0)
    voice_state = tts_model.get_state_for_audio_prompt(voice_id)
    chunks = tts_model.generate_audio_stream(voice_state, text_to_generate=text)

    all_audio = []
    for i, chunk in enumerate(chunks):
        all_audio.append(chunk.numpy())

    combined = np.concatenate(all_audio)
    scipy.io.wavfile.write(output_path, tts_model.sample_rate, combined)
    logger.debug(f"TTS audio saved to {output_path}")
    return output_path


def speak(text: str, voice_id: str = active_voice_id):
    if not text:
        logger.warning("No text provided for TTS, skipping")
        return

    tts_model = TTSModel.load_model(temp=0.5, lsd_decode_steps=7, eos_threshold=-1.0)
    sample_rate = tts_model.sample_rate

    fifo_path = "/tmp/tts_stream.pcm"
    if os.path.exists(fifo_path):
        os.remove(fifo_path)
    os.mkfifo(fifo_path)

    player_proc = subprocess.Popen(
        ["aplay", "-f", "S16_LE", "-r", str(sample_rate), "-c", "1", fifo_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        start_time = time.time()
        logger.debug("Generating voice...")
        voice_state = tts_model.get_state_for_audio_prompt(voice_id)
        chunks = tts_model.generate_audio_stream(voice_state, text_to_generate=text)

        with open(fifo_path, "wb") as fifo:
            for i, chunk in enumerate(chunks):
                pcm = (chunk.numpy() * 32767).astype(np.int16)
                fifo.write(pcm.tobytes())

        player_proc.wait()
        logger.debug(f"Voice generation finished in {time.time() - start_time:.2f}s")

    except Exception as e:
        logger.error(e)
        player_proc.kill()
    finally:
        os.remove(fifo_path)


if __name__ == "__main__":
    speak("""We offer commercial support for teams integrating Kitten TTS into their products. This includes integration assistance, custom voice development, and enterprise licensing.""")
