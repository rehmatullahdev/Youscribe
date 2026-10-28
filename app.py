"""Loopback-only transcription workbench. Run start.cmd on Windows."""
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('HF_HOME', str(ROOT / 'data' / 'huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL

app = FastAPI(title='LocalScribe')
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', 'testserver'])
jobs = {}
pool = ThreadPoolExecutor(max_workers=1)
gate = threading.Lock()
models = {}
MAX_BYTES = 250 * 1024 * 1024
MAX_SECONDS = 3600
TMP = ROOT / 'data' / 'temporary'
TMP.mkdir(parents=True, exist_ok=True)

@app.middleware('http')
async def local_requests(request: Request, call_next):
    if request.method == 'POST':
        length = request.headers.get('content-length')
        if length and length.isdigit() and int(length) > MAX_BYTES + 1024 * 1024:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'Request exceeds the 250 MB upload limit.'}, status_code=413)
    origin = request.headers.get('origin')
    if request.method == 'POST' and origin and origin not in ('http://127.0.0.1:8765', 'http://localhost:8765'):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail': 'Open this app at http://127.0.0.1:8765.'}, status_code=403)
    return await call_next(request)

def youtube_url(value):
    parsed = urlparse(value.strip())
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError('Paste a public HTTPS YouTube video link.')
    video = None
    if host == 'youtu.be':
        video = parsed.path.strip('/').split('/')[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        if parsed.path == '/watch':
            video = parse_qs(parsed.query).get('v', [None])[0]
        elif parsed.path.startswith(('/shorts/', '/live/', '/embed/')):
            video = parsed.path.split('/')[2]
    import re
    if not video or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('Use a single YouTube video link, such as https://www.youtube.com/watch?v=VIDEO_ID.')
    return 'https://www.youtube.com/watch?v=' + video

def run_job(jid, source, model_size, language, uploaded):
    job = jobs[jid]
    started = time.perf_counter()
    folder = TMP / jid
    try:
        title = Path(source).name if uploaded else 'YouTube video'
        audio = source
        if not uploaded:
            job.update(stage='Retrieving YouTube audio', progress=0)
            opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True,
                    'no_warnings': True, 'outtmpl': str(folder / 'audio.%(ext)s'),
                    'max_filesize': MAX_BYTES, 'socket_timeout': 20, 'retries': 2,
                    'cachedir': str(ROOT / 'data' / 'yt-dlp'),
                    'match_filter': lambda info, **kw: 'Video must be recorded and no longer than 60 minutes.' if info.get('is_live') or (info.get('duration') or 0) > MAX_SECONDS else None}
            bundled_node = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
            node = os.environ.get('LOCALSCRIBE_NODE') or shutil.which('node') or (str(bundled_node) if bundled_node.exists() else None)
            if node:
                opts['js_runtimes'] = {'node': {'path': node}}
            import imageio_ffmpeg
            opts['ffmpeg_location'] = imageio_ffmpeg.get_ffmpeg_exe()
            def downloading(d):
                if d.get('status') == 'downloading' and d.get('downloaded_bytes', 0) > MAX_BYTES:
                    raise ValueError('Audio exceeds the 250 MB limit.')
            opts['progress_hooks'] = [downloading]
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(source, download=True)
                if not info:
                    raise ValueError('No downloadable audio was returned.')
                audio = ydl.prepare_filename(info)
                title = info.get('title') or title
        import av
        with av.open(str(audio)) as container:
            duration = float(container.duration / av.time_base) if container.duration else None
            if duration and duration > MAX_SECONDS:
                raise ValueError('Please use audio shorter than 60 minutes.')
        job.update(stage='Loading model (first use downloads model)', progress=0, title=title)
        load_start = time.perf_counter()
        # Retain just one model to keep memory bounded on modest computers.
        if model_size not in models:
            models.clear()
            models[model_size] = WhisperModel(model_size, device='cpu', compute_type='int8',
                cpu_threads=min(4, os.cpu_count() or 2), download_root=str(ROOT / 'data' / 'models'))
        load_seconds = time.perf_counter() - load_start
        job.update(stage='Transcribing locally')
        inference_start = time.perf_counter()
        segments, info = models[model_size].transcribe(str(audio), language=language or None,
            beam_size=1, vad_filter=True, condition_on_previous_text=False)
        result = []
        for seg in segments:
            if seg.end > MAX_SECONDS:
                raise ValueError('Audio exceeds the 60 minute limit.')
            result.append({'start': round(seg.start, 2), 'end': round(seg.end, 2), 'text': seg.text.strip()})
            job['progress'] = min(99, round(100 * seg.end / max(info.duration, 1)))
        transcribe_seconds = time.perf_counter() - inference_start
        job.update(status='done', stage='Complete', progress=100, segments=result,
            text='\n'.join(s['text'] for s in result), language=info.language,
            duration_seconds=round(info.duration, 2), model=model_size,
            model_load_seconds=round(load_seconds, 2), transcription_seconds=round(transcribe_seconds, 2),
            total_seconds=round(time.perf_counter() - started, 2),
            realtime_factor=round(transcribe_seconds / max(info.duration, 0.01), 3))
    except Exception as exc:
        job.update(status='error', stage='Unable to finish', error=str(exc)[:1800],
                   total_seconds=round(time.perf_counter() - started, 2))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        gate.release()

@app.get('/')
def index():
    return FileResponse(ROOT / 'index.html')

@app.get('/api/health')
def health():
    return {'ok': True, 'device': 'CPU / int8', 'threads': min(4, os.cpu_count() or 2),
            'models': ['tiny', 'base', 'small'], 'busy': gate.locked()}

@app.post('/api/transcribe', status_code=202)
async def transcribe(url: str = Form(''), model: str = Form('tiny'), language: str = Form(''),
                     file: UploadFile | None = File(None)):
    if model not in ('tiny', 'base', 'small'):
        raise HTTPException(400, 'Unknown model.')
    import re
    if language and not re.fullmatch(r'[a-z]{2,3}', language):
        raise HTTPException(400, 'Use a language code such as en or ur, or leave automatic.')
    if bool(url.strip()) == bool(file and file.filename):
        raise HTTPException(400, 'Provide either a YouTube link or one audio/video file.')
    try:
        source = youtube_url(url) if url.strip() else ''
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not gate.acquire(blocking=False):
        raise HTTPException(409, 'A transcription is already running. Wait for it to finish.')
    jid = uuid.uuid4().hex
    folder = TMP / jid
    folder.mkdir()
    try:
        uploaded = bool(file and file.filename)
        if uploaded:
            suffix = Path(file.filename).suffix.lower()
            if suffix not in ('.mp3', '.wav', '.m4a', '.mp4', '.webm', '.ogg', '.flac', '.aac', '.mov', '.mkv'):
                raise HTTPException(400, 'Choose a supported audio or video file.')
            source = str(folder / ('upload' + suffix))
            size = 0
            with open(source, 'wb') as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, 'File exceeds 250 MB.')
                    target.write(chunk)
            if not size:
                raise HTTPException(400, 'The file is empty.')
        # Results are session memory only; cap history to 20 jobs.
        while len(jobs) >= 20:
            jobs.pop(next(iter(jobs)))
        jobs[jid] = {'id': jid, 'status': 'running', 'stage': 'Starting', 'progress': 0,
                     'started_at': time.time()}
        pool.submit(run_job, jid, source, model, language, uploaded)
        return {'id': jid}
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        gate.release()
        raise
    finally:
        if file:
            await file.close()

@app.get('/api/jobs/{jid}')
def job_status(jid: str):
    if jid not in jobs:
        raise HTTPException(404, 'Job no longer available. Results reset when the server restarts.')
    return jobs[jid]

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8765)
