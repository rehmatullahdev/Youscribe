# Verification — 21 October 2026

## Real transcription results

Tested on this Windows computer with Python 3.14, 4 logical processors, approximately 7.9 GB physical RAM (1.7 GB available at the initial check). CPU int8, multilingual Tiny, beam size 1, voice activity detection enabled. The model was downloaded before these timings.

| Test | Audio duration | Model load | Transcription | Total |
| --- | ---: | ---: | ---: | ---: |
| Uploaded JFK speech sample, first model load | 11.00 s | 2.24 s | 2.94 s | 5.25 s |
| YouTube, Me at the zoo, model already loaded | 19.01 s | 0.00 s | 0.92 s | 4.38 s |
| Browser form, same YouTube video, automatic language | 19.01 s | 0.00 s | 1.76 s | 5.04 s |

The upload test used the [faster-whisper test sample](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/tests/data/jfk.flac). Its actual output was:

> And so my fellow Americans ask not what your country can do for you ask what you can do for your country.

The YouTube tests used [Me at the zoo](https://www.youtube.com/watch?v=jNQXAC9IVRw). Audio retrieval and local recognition both succeeded. Tiny's output contained errors, including “long prompts” instead of “long trunks.” These short samples are functional checks, not a representative accuracy benchmark or a prediction for long videos. Network conditions, language, silence, model size, CPU load, and memory pressure change performance. Base and Small were not downloaded or benchmarked.

## Checks completed

- Main page HTTP 200 and health endpoint report CPU int8 with four threads.
- Python compilation, browser JavaScript syntax, and `pip check` pass.
- Two automated backend tests pass: canonicalization and rejection of unsafe/non-video URLs; cleanup and worker release after invalid audio.
- Live HTTP input checks reject unsupported URL destinations, invalid model selection, and missing input with HTTP 400.
- Browser review confirms rendered layout, source-tab switching, engine-ready state, form submission, in-progress state, completed timestamped transcript, and timing display.
- Browser Copy changes to “Copied” after the clipboard promise resolves. TXT and SRT download actions were triggered; saved download file contents were not independently inspected.
- Successful and failed jobs removed their temporary media directories.

## Issues found and resolved

The first install selected PyAV 19.0.2, which is incompatible with released faster-whisper 1.2.1 (`metadata_errors` was removed). Requirements now explicitly pin PyAV below 19; actual tests pass with 18.1.0. See the [upstream compatibility report](https://github.com/SYSTRAN/faster-whisper/issues/1589). Installed versions are recorded in `requirements-lock.txt`.

The first YouTube test video ID BaW_jenozKc was unavailable. The app surfaced that error and subsequently processed a different public video successfully. This does not establish that all YouTube videos are retrievable.

## Remaining limits

No public deployment, payment integration, concurrent-user load test, GPU benchmark, long-video benchmark, or Urdu accuracy test was performed. No paid service was used. All recognition ran locally. Only Tiny is predownloaded; the first use of Base or Small needs internet and more resources.
