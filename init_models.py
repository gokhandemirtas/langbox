"""Model initialization.

Checks for required GGUF models and downloads missing ones from HuggingFace.
"""

import re
from pathlib import Path

from huggingface_hub import hf_hub_download
from loguru import logger

# Registry mapping GGUF filenames to their HuggingFace repository IDs.
# Update these entries when adding new models to .env.
MODEL_REGISTRY = {
  "qwen2.5-1.5b-instruct-fp16.gguf": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
  "Qwen3-14B-Q5_0.gguf": "Qwen/Qwen3-14B-GGUF",
  "Hermes-2-Pro-Llama-3-8B-Q5_K_M.gguf": "NousResearch/Hermes-2-Pro-Llama-3-8B-GGUF",
  "llama-2-7b-chat.Q3_K_M.gguf": "TheBloke/Llama-2-7B-Chat-GGUF",
  "mistral-7b-instruct-v0.2.Q3_K_L.gguf": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
  "Phi-3-mini-4k-instruct-q4.gguf": "microsoft/Phi-3-mini-4k-instruct-gguf",
  "Finance-Llama-8B-GGUF-q4_K_M.gguf": "tarun7r/Finance-Llama-8B-q4_k_m-GGUF",
  "phi-4-Q5_0.gguf": "microsoft/phi-4-gguf",
}


def parse_env_models(env_path: str = ".env") -> dict[str, str]:
  """Parse .env file and return MODEL_ variables with .gguf values.

  Skips MODEL_PATH since it defines the directory, not a model file.

  Returns:
      Dict mapping variable name to filename
      (e.g., {"MODEL_QWEN2.5": "qwen2.5-1.5b-instruct-fp16.gguf"})
  """
  models = {}
  env_file = Path(env_path)
  if not env_file.exists():
    logger.warning(f".env file not found at {env_path}")
    return models

  for line in env_file.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
      continue

    match = re.match(r'^(MODEL_[\w.]+)\s*=\s*"?([^"#]+)"?', line)
    if match:
      key, value = match.group(1), match.group(2).strip()
      if key == "MODEL_PATH":
        continue
      if value.endswith(".gguf"):
        models[key] = value

  return models


def get_model_dir(env_path: str = ".env") -> Path:
  """Read MODEL_PATH from .env, defaulting to 'models/'."""
  env_file = Path(env_path)
  if env_file.exists():
    for line in env_file.read_text().splitlines():
      match = re.match(r'^MODEL_PATH\s*=\s*"?([^"#]+)"?', line.strip())
      if match:
        return Path(match.group(1).strip())
  return Path("models/")


def check_and_download_models(env_path: str = ".env") -> None:
  """Check for missing GGUF models and download them from HuggingFace."""
  models = parse_env_models(env_path)
  if not models:
    logger.info("No MODEL_ variables with .gguf values found in .env")
    return

  models_dir = get_model_dir(env_path)

  if not models_dir.exists():
    logger.info(f"Creating models directory: {models_dir}")
    models_dir.mkdir(parents=True)

  missing = {}
  present = {}

  for var_name, filename in models.items():
    if (models_dir / filename).exists():
      present[var_name] = filename
    else:
      missing[var_name] = filename

  if present:
    logger.info(f"Models already downloaded: {len(present)}/{len(models)}")
    for var_name, filename in present.items():
      logger.debug(f"  {var_name}: {filename}")

  if not missing:
    logger.info("All models are present")
    return

  logger.info(f"Missing models to download: {len(missing)}/{len(models)}")
  for var_name, filename in missing.items():
    logger.info(f"  {var_name}: {filename}")

  for var_name, filename in missing.items():
    repo_id = MODEL_REGISTRY.get(filename)
    if not repo_id:
      logger.warning(
        f"No HuggingFace repo configured for '{filename}' ({var_name}). "
        f"Add it to MODEL_REGISTRY in init_models.py"
      )
      continue

    logger.info(f"Downloading {filename} from {repo_id}...")
    try:
      hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(models_dir),
      )
      logger.info(f"Successfully downloaded {filename}")
    except Exception as e:
      logger.error(f"Failed to download {filename} from {repo_id}: {e}")


if __name__ == "__main__":
  check_and_download_models()
