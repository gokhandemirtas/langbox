"""Langbox HTTP API — serves the mobile app over Tailscale.

Endpoints:
  POST /query      — text query through the intent classifier
  POST /voice      — audio file → Whisper STT → intent classifier → pocket-tts → base64 audio
  GET  /notes      — list all notes from MongoDB
  GET  /reminders  — list reminders from MongoDB
  GET  /openapi.json — OpenAPI 3.0 spec (generated from skills registry)
  GET  /docs       — Swagger UI
"""

import base64
import json
import os
import tempfile

from aiohttp import web

from utils.log import logger


async def handle_query(request: web.Request) -> web.Response:
    data = await request.json()
    query = data.get("query", "").strip()
    if not query:
        return web.json_response({"error": "query is required"}, status=400)

    from agents.intent_classifier import run_intent_classifier
    response = await run_intent_classifier(query)
    return web.json_response({"response": response})


async def handle_voice(request: web.Request) -> web.Response:
    reader = await request.multipart()
    field = await reader.next()
    if field is None or field.name != "audio":
        return web.json_response({"error": "audio field is required"}, status=400)

    # Save uploaded audio to a temp file
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        audio_in = tmp.name
        while chunk := await field.read_chunk(8192):
            tmp.write(chunk)

    # Pre-convert to WAV with elevated probe settings so Whisper's ffmpeg can
    # handle Android m4a files that report "Audio: none, unknown codec".
    import subprocess
    wav_in = audio_in.replace(".m4a", ".wav")
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
        logger.error(f"[api/voice] ffmpeg pre-convert failed: {e.stderr.decode()}")
        return web.json_response({"error": "audio conversion failed"}, status=422)

    try:
        # STT via Whisper
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(wav_in)
        transcript = result["text"].strip()
        logger.debug(f"[api/voice] transcript='{transcript}'")

        # Run through intent classifier
        from agents.intent_classifier import run_intent_classifier
        response_text = await run_intent_classifier(transcript)

        # TTS via pocket-tts
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
            audio_out = tmp_out.name

        from tts.tts import synthesise
        synthesise(response_text, audio_out)

        with open(audio_out, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        return web.json_response({"text": response_text, "audio": audio_b64})

    finally:
        for path in (audio_in, wav_in, audio_out if "audio_out" in dir() else None):
            if path and os.path.exists(path):
                os.remove(path)


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
