# LocalScribe — local Windows prototype

A browser webpage backed by Python, faster-whisper, and yt-dlp. No paid API, account, hosting, or deployment is needed. This is a single-user performance workbench.

## Start

1. Double-click **start.cmd** in this folder.
2. Keep its terminal window open and visit **http://127.0.0.1:8765** in your browser.
3. Paste a public YouTube video link, choose **Tiny**, and click **Transcribe**. If retrieval fails, switch to **Upload a file**.
4. Copy the result or download TXT/SRT. Stop the server with Ctrl+C in its terminal window.

If dependencies are missing, run **setup.cmd** once first. It creates `.venv` here and installs the tested versions from `requirements-lock.txt`; `requirements.txt` records the direct dependency constraints. Internet access is needed for installation, YouTube retrieval, and the first download of each selected model. Installed model files live in `data/models`. Tiny downloads roughly 75 MB of weights; Base roughly 145 MB; Small roughly 485 MB, plus metadata. Package installation also downloads several hundred MB. Downloaded models are reused; file transcription then works offline.

Use Python 3.12 or newer on 64-bit Windows. The tested installation uses Python 3.14. If the computer is missing Microsoft's Visual C++ runtime, CTranslate2 may require the Microsoft Visual C++ 2015–2022 x64 Redistributable. Setup does not change system packages. The virtual environment depends on the installed Python path; run setup again after moving to another computer.

## Workflow and measurement

- Single videos and local audio/video files, up to 60 minutes and 250 MB. Playlists, live broadcasts, private, sign-in-only, and DRM media are outside this prototype.
- CPU with int8 computation and up to four threads. Tiny is the default for the observed four logical CPUs and 7.9 GB RAM. Base/Small improve recognition at greater memory/time cost. Urdu and other supported languages use multilingual models; the tool transcribes speech without translating it.
- A background worker runs one job at a time; the webpage polls for progress. Refreshing the same browser tab reconnects to its latest job.
- Timing includes model loading, transcription, and total processing. Total starts after file upload completes and includes YouTube retrieval and initial model download. Transcription/audio ratio below 1 means faster than real time. Compare a first cold run with a second warm run using the same sample.
- Whisper output can contain errors or invented words, especially around music, noise, and silence. Review the result.

## YouTube dependency and limitations

yt-dlp includes its EJS challenge solver through `yt-dlp[default]`. A supported JavaScript runtime improves YouTube retrieval. This installation automatically finds the bundled Codex Node 24 runtime, a Node executable on PATH, or `LOCALSCRIBE_NODE`. On another computer, install a supported Node runtime or set `LOCALSCRIBE_NODE` to its executable path. The pip-bundled FFmpeg executable is used when needed; PyAV decodes local uploads.

YouTube can still require authentication, reject downloads, restrict content by region, or change its extraction behavior. Errors are shown in the webpage. There is no automatic cookie extraction or authentication bypass. Update yt-dlp with `.venv\Scripts\python.exe -m pip install -U "yt-dlp[default]"` if extraction breaks. Use media you have permission to process.

## Data and boundaries

The server binds only to 127.0.0.1. Audio files are temporarily stored under `data/temporary` and removed when a job finishes or fails. Results exist in server memory, capped at 20 jobs, and disappear when the server restarts. Download transcripts to retain them. An abrupt process kill can leave temporary files; close the server before manually clearing `data/temporary`.

Uploaded media is processed locally. YouTube links contact YouTube and first-time model downloads contact Hugging Face. No transcription audio is sent to a paid service. This prototype needs further access control, resource limits, durable job storage, deployment design, and rights/terms review before any public monetized launch.

## Sources

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): model implementation and CPU int8 settings.
- [yt-dlp JavaScript requirements](https://github.com/yt-dlp/yt-dlp/wiki/EJS): YouTube extraction runtime requirements.

See `VERIFICATION.md` for actual checks and measured outcomes from this build.
