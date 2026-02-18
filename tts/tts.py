import os
import subprocess
import threading
import time

import scipy.io.wavfile
from loguru import logger
from pedalboard import Chorus, Pedalboard, Phaser
from pedalboard.io import AudioFile
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

active_voice_id = "fantine"
timeout = 300

def _effects(input_path: str):
  """Apply cyborg voice effects to a wav file and overwrite it."""

  with AudioFile(input_path) as f:
      audio = f.read(f.frames)
      samplerate = f.samplerate

  board = Pedalboard([
    Phaser(rate_hz=1.0, depth=0.4, mix=0.1), Chorus(rate_hz=0.6, depth=0.2, mix=0.4)
  ])

  processed = board(audio, samplerate)

  with AudioFile(input_path, 'w', samplerate, processed.shape[0]) as f:
      f.write(processed)

  logger.debug("Applied voice effects")


def _play(audioFile: str):
  try:
    logger.debug("Playing generated audio...")
    # Try different audio players commonly available on Linux
    players = ['aplay', 'paplay', 'ffplay']
    for player in players:
      if subprocess.run(['which', player], capture_output=True).returncode == 0:
        if player == 'ffplay':
          subprocess.run([player, '-nodisp', '-autoexit', audioFile],
                        capture_output=True, check=False, timeout=timeout)
        else:
          subprocess.run([player, audioFile], capture_output=True, check=False, timeout=timeout)
        break
    else:
      logger.error("⚠️ No audio player found (aplay, paplay, or ffplay)")
  except Exception as e:
    logger.error(e)


def speak(text: str, voice_id: str = active_voice_id):
  if not text:
    logger.warning("No text provided for TTS, skipping")
    return

  tts_model = TTSModel.load_model(temp=0.5, lsd_decode_steps=5, eos_threshold=-3.0)
  try:
    start_time = time.time()
    logger.debug("Generating voice...")

    # Split on line breaks first, then on dashes within each line
    raw_lines = text.split("\n")
    chunks = []
    for line in raw_lines:
      parts = [p.strip() for p in line.split("-") if p.strip()]
      chunks.extend(parts)
    voice_state = tts_model.get_state_for_audio_prompt(voice_id)
    play_thread = None
    prev_chunk_file = None

    for i, chunk in enumerate(chunks):
      chunk_file = os.path.join(os.path.dirname(__file__), f"chunk_{i}.wav")
      audio = tts_model.generate_audio(voice_state, chunk)
      scipy.io.wavfile.write(chunk_file, tts_model.sample_rate, audio.numpy())
      
      logger.debug(f"Chunk {i} generated: {chunk[:60]}...")

      if play_thread is not None:
        play_thread.join()
        os.remove(prev_chunk_file)
        logger.debug(f"Deleted {prev_chunk_file}")

      play_thread = threading.Thread(target=_play, args=(chunk_file,))
      play_thread.start()
      prev_chunk_file = chunk_file

    if play_thread is not None:
      play_thread.join()
      os.remove(prev_chunk_file)
      logger.debug(f"Deleted {prev_chunk_file}")

    logger.debug(f"Voice generation finished in {time.time() - start_time:.2f}s")

  except Exception as e:
    logger.error(e)

if __name__ == "__main__":
  speak("""- Watch: Key moments that defined Jesse Jackson's life: The civil rights leader, who ran for president twice in the 1980s, leaves a lasting legacy.
- Dual nationals face scramble for UK passports as new rules come into force: Entry requirements to the UK for dual nationals are being overhauled as part of sweeping changes to the immigration system.
- Cold health alert issued as temperatures fall across the UK: Yellow weather warnings will also come into force on Wednesday across parts of England and much of Wales.
- Reform names Robert Jenrick as pick for chancellor: Leader Nigel Farage says Reform is "the voice of opposition" to Labour, as he unveils his new top team.
- UK unemployment hits highest rate for nearly five years: It marks the highest rate since the Covid pandemic, official figures show.
- Legal challenge to Met's Freemasons policy thrown out: The Met had announced that membership of the Freemasons or similar organisations would have to declared.
- Shop owners in Northern Ireland fear violence after paramilitaries demand protection money: One business owner says she was approached by paramilitaries before her new shop even opened.
- Patients describe 'culture of abuse' as 15 hospital staff arrested: Patients and their relatives say there is a culture of abuse at a mental health hospital.
- 'A sad day' - curling cheating row at Winter Games unsettles Canadians: Both men's and women's Canadian curling teams have been accused of cheating at the 2026 Winter Olympics.
- Singer and YouTuber who makes music with Furbys and Game Boys picked for UK at Eurovision: Synth artist Look Mum No Computer is described as "a bold and brave choice" to represent the UK.
- USA's Meyers Taylor, 41, becomes oldest individual Olympic champion at a Winter Games: Elana Meyers Taylor made history by winning monobob gold to become the oldest individual athlete to become Winter Olympic champion, all while empowering mothers and female athletes.
- Lindsey Vonn 'yet to stand' but returns home to US: Lindsey Vonn is home in the United States after four operations on the broken leg she sustained at the Winter Olympics - but is yet to stand up nine days after the crash.
- A big day for GB's men's curling team - Tuesday's guide: What's happening and who to look out for at the 2026 Winter Olympics in Milan-Cortina.
- The man whose bad break-up gave Madonna her breakthrough hit Like A Virgin: Billy Steinberg, who has died at the age of 75, co-wrote Madonna's 1984 chart-topper Like a Virgin.
- Adoption breakdown ended my career and relationship – we're told to get on with it: A mum says she has been physically attacked by her daughter and is reaching "breaking point".
- Viral face depuffing tricks - skin experts reveal if they work: We look at three viral hacks to unpick fact from fiction - the effects are often at best, temporary, say experts.
- Reddit's human content wins amid the AI flood: Reddit says its human contributors are valued amid an internet awash with AI-generated content.
- How will freeze on tax thresholds affect your take-home pay? Use our calculator: Wages have been rising faster than prices but you could pay more tax because of frozen thresholds.
- Why are some students claiming Covid compensation from universities?: Dozens of universities face legal action from students who say they missed out during the pandemic.
- Boy first in UK to have pioneering leg-lengthening surgery: Alfie Phillips, 9, had the pioneering treatment at Liverpool's Alder Hey Children's Hospital.""")