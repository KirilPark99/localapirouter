# Audio transcription

STT models use `model_type: "audio"`, not chat completions. Whisper is classified automatically on model discovery, including existing catalog entries. The Models page supports individual, batch and manual Audio mode selection.

```bash
curl http://localhost:8007/v1/audio/transcriptions \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -F model=groq/whisper-large-v3-turbo \
  -F file=@speech.mp3 \
  -F language=ru \
  -F response_format=json
```

`/api/v1/audio/transcriptions` is equivalent. Authentication, key permissions, request quotas, credential RPM/concurrency, configured proxies and safety processing are retained. Audio bytes are neither passed through chat compression nor stored in request logs. Responses support `json`, `text`, and `verbose_json`; repeated `timestamp_granularities[]=word/segment` require `verbose_json`. Language is optional (automatic detection).

The Playground Audio mode uploads a file and displays the transcript. This implementation supports direct models and files up to 25 MB; no recording, URL fetching, chunking, TTS, translations or routing-profile composition. Unsupported providers/models fail locally. Ambiguous paid submissions (read/write timeout, malformed successful response, upstream 5xx) are never automatically replayed.

STT billing uses audio duration, not text tokens. Existing token TPM and token/USD period quotas therefore fail closed for audio instead of silently bypassing budgets; request-count quotas work. Logs identify mode `AUDIO`, response format, file byte count, duration when supplied and unknown cost (no fabricated token price). Configure an unrestricted or request-count-limited key for STT until audio-duration budgets are added.

Regression check (use a secrets-free test environment and scratch database):

```bash
cd backend
python -m pytest tests/test_audio_transcription.py -q
```

Reference contract: https://console.groq.com/docs/speech-to-text
