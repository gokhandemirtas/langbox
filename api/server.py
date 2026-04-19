"""Langbox HTTP API — serves the mobile app over Tailscale.

Endpoints:
  POST /query          — text query through the intent classifier
  POST /voice          — audio file → enqueues processing, returns job_id immediately
  GET  /voice/{job_id} — poll for voice job result (pending | done | error)
  GET  /plans          — list saved planner plans
  GET  /notes          — list all notes from MongoDB
  GET  /reminders      — list reminders from MongoDB
  GET  /openapi.json   — OpenAPI 3.0 spec (generated from skills registry)
  GET  /docs           — Swagger UI
"""

import asyncio
import base64
import json
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor

from aiohttp import web

from utils.log import logger

# ---------------------------------------------------------------------------
# Voice job queue
# ---------------------------------------------------------------------------

_voice_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice")
_voice_jobs: dict[str, dict] = {}  # job_id → {status, result}


async def handle_query(request: web.Request) -> web.Response:
    data = await request.json()
    query = data.get("query", "").strip()
    if not query:
        return web.json_response({"error": "query is required"}, status=400)

    if query.startswith("/planner"):
        task = query[len("/planner"):].strip()
        if not task:
            return web.json_response({"error": "task is required. Usage: /planner <task>"}, status=400)
        from skills.planner import run_planner
        response = await run_planner(task)
        return web.json_response({"response": response})

    from agents.intent_classifier import run_intent_classifier
    response = await run_intent_classifier(query)
    return web.json_response({"response": response})


def _process_voice_job(job_id: str, audio_in: str, loop: asyncio.AbstractEventLoop) -> None:
    """Blocking pipeline: ffmpeg → Whisper → intent classifier → TTS. Runs in thread pool."""
    import subprocess
    import whisper
    from tts.tts import synthesise

    wav_in = audio_in.replace(".m4a", ".wav")
    audio_out = None
    try:
        # ffmpeg pre-convert
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-nostdin",
                    "-analyzeduration", "10M", "-probesize", "10M",
                    "-i", audio_in,
                    "-ac", "1", "-acodec", "pcm_s16le", "-ar", "16000",
                    wav_in,
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"[api/voice] ffmpeg failed: {e.stderr.decode()}")
            _voice_jobs[job_id] = {"status": "error", "error": "audio conversion failed"}
            return

        # Whisper STT
        model = whisper.load_model("base")
        transcript = model.transcribe(wav_in)["text"].strip()
        logger.debug(f"[api/voice] transcript='{transcript}'")

        # Intent classifier (async — run via the event loop from this thread)
        from agents.intent_classifier import run_intent_classifier
        future = asyncio.run_coroutine_threadsafe(run_intent_classifier(transcript), loop)
        response_text = future.result()

        # TTS
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
            audio_out = tmp_out.name
        synthesise(response_text, audio_out)

        with open(audio_out, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        _voice_jobs[job_id] = {
            "status": "done",
            "transcription": transcript,
            "text": response_text,
            "audio": audio_b64,
        }
    except Exception as e:
        logger.error(f"[api/voice] job {job_id} failed: {e}")
        _voice_jobs[job_id] = {"status": "error", "error": str(e)}
    finally:
        for path in (audio_in, wav_in, audio_out):
            if path and os.path.exists(path):
                os.remove(path)


async def handle_voice(request: web.Request) -> web.Response:
    reader = await request.multipart()
    field = await reader.next()
    if field is None or field.name != "audio":
        logger.warning("[api/voice] missing audio field in multipart request")
        return web.json_response({"error": "audio field is required"}, status=400)

    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        audio_in = tmp.name
        while chunk := await field.read_chunk(8192):
            tmp.write(chunk)

    file_size = os.path.getsize(audio_in)
    job_id = str(uuid.uuid4())
    logger.info(f"[api/voice] job {job_id} queued — file size {file_size} bytes")
    _voice_jobs[job_id] = {"status": "pending"}

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_voice_executor, _process_voice_job, job_id, audio_in, loop)

    job = _voice_jobs.pop(job_id, None)
    if job is None or job.get("status") == "error":
        error = job.get("error", "processing failed") if job else "job lost"
        logger.error(f"[api/voice] job {job_id} failed: {error}")
        return web.json_response({"error": error}, status=422)

    return web.json_response(job)


async def handle_voice_result(request: web.Request) -> web.Response:
    job_id = request.match_info["job_id"]
    job = _voice_jobs.get(job_id)
    if job is None:
        logger.warning(f"[api/voice] job {job_id} not found")
        return web.json_response({"error": "job not found"}, status=404)
    if job["status"] == "error":
        logger.error(f"[api/voice] job {job_id} failed: {job['error']}")
        _voice_jobs.pop(job_id)
        return web.json_response({"error": job["error"]}, status=422)
    if job["status"] == "pending":
        logger.debug(f"[api/voice] job {job_id} still pending")
        return web.json_response({"status": "pending"}, status=202)
    # done — return result and clean up
    logger.info(job)
    _voice_jobs.pop(job_id)
    return web.json_response(job)


async def handle_plans(request: web.Request) -> web.Response:
    from db.schemas import Plans
    plans = await Plans.find().sort(-Plans.created_at).to_list()
    return web.json_response({
        "plans": [
            {
                "id": str(p.id),
                "ask": p.ask,
                "plan": p.plan,
                "created_at": p.created_at.isoformat(),
            }
            for p in plans
        ]
    })


async def handle_notes(request: web.Request) -> web.Response:
    from db.schemas import Note
    notes = await Note.find().sort(-Note.created_at).to_list()
    return web.json_response({
        "notes": [
            {
                "id": str(n.id),
                "title": n.title,
                "content": n.content,
                "category": n.category,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ]
    })


async def handle_reminders(request: web.Request) -> web.Response:
    from db.schemas import Reminders
    include_completed = request.rel_url.query.get("include_completed", "false").lower() == "true"

    query = Reminders.find() if include_completed else Reminders.find(Reminders.is_completed == False)
    reminders = await query.sort(Reminders.reminder_datetime).to_list()

    return web.json_response({
        "reminders": [
            {
                "id": str(r.id),
                "description": r.description,
                "reminder_datetime": r.reminder_datetime.isoformat(),
                "is_completed": r.is_completed,
            }
            for r in reminders
        ]
    })


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def handle_openapi(request: web.Request) -> web.Response:
    from api.openapi import build_spec
    return web.Response(
        text=json.dumps(build_spec(), indent=2),
        content_type="application/json",
    )


async def handle_docs(request: web.Request) -> web.Response:
    html = """<!DOCTYPE html>
<html>
<head>
  <title>Langbox API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" })
  </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


@web.middleware
async def log_middleware(request: web.Request, handler):
    response = await handler(request)
    if request.path != "/health":
        logger.info(f"{request.method} {request.path} → {response.status}")
    return response


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers=_CORS_HEADERS)
    response = await handler(request)
    response.headers.update(_CORS_HEADERS)
    return response


def create_app() -> web.Application:
    app = web.Application(middlewares=[log_middleware, cors_middleware])
    app.router.add_get("/health", handle_health)
    app.router.add_post("/query", handle_query)
    app.router.add_post("/voice", handle_voice)
    app.router.add_get("/voice/{job_id}", handle_voice_result)
    app.router.add_get("/plans", handle_plans)
    app.router.add_get("/notes", handle_notes)
    app.router.add_get("/reminders", handle_reminders)
    app.router.add_get("/openapi.json", handle_openapi)
    app.router.add_get("/docs", handle_docs)
    return app


async def start_api_server(host: str = "0.0.0.0", port: int = 8000) -> web.AppRunner:
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"API server listening on {host}:{port}")
    return runner


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        from db.init import db_init
        await db_init()
        runner = await start_api_server()
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    asyncio.run(_main())
