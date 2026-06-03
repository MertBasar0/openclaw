# Watch Ceviz — STT (Konuşma→Metin) Kurulumu

Backend artık **key gerektirmeyen, lokal, gizli** STT kullanıyor: **faster-whisper**.
OpenAI artık zorunlu değil; yalnızca opsiyonel fallback.

## Nasıl çalışıyor
`backend/stt.py` → motor seçimi `WATCH_CEVIZ_STT_ENGINE` (default **auto**):
1. İstemci `transcript` gönderdiyse → onu kullan (STT atlanır).
2. **auto/local:** lokal Whisper (`backend/local_whisper.py`, faster-whisper). CUDA varsa GPU, yoksa CPU'ya düşer (warmup ile doğrulanır).
3. **auto/openai:** lokal başarısızsa ve `OPENAI_API_KEY` varsa OpenAI'ye düşer.

## Env ayarları
| Değişken | Default | Açıklama |
|---|---|---|
| `WATCH_CEVIZ_STT_ENGINE` | `auto` | `auto` \| `local` \| `openai` |
| `WATCH_CEVIZ_WHISPER_MODEL` | `small` | `small` \| `medium` \| `large-v3` (Türkçe doğruluk ↑) |
| `WATCH_CEVIZ_WHISPER_DEVICE` | `auto` | `auto` \| `cuda` \| `cpu` |
| `WATCH_CEVIZ_WHISPER_LANGUAGE` | `tr` | |

## Doğrulanan durum (2026-06-04)
- CPU `small`: jfk klibi 0.8s'de doğru transkript (~14x realtime). İlk çağrı model yükleme + cuda-warmup nedeniyle ~3.7s.
- CUDA şu an kapalı: `libcublas.so.12` eksik (sm_120 mimari değil, sadece runtime lib). GPU için:
  `./.venv/bin/pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` + `LD_LIBRARY_PATH`'e ekle, sonra `WATCH_CEVIZ_WHISPER_MODEL=large-v3` ile RTX 5070 Ti'de anlık çalışır.
- Türkçe sesli komutlar için öneri: GPU açılınca `large-v3`; CPU'da kalınırsa `small`/`medium`.

## Servis
`watch-ceviz-backend.service` (systemd --user, port 8080) bu venv'i + bu env'leri kullanır.
Kopyası: `deploy/watch-ceviz-backend.service`. Boot'ta otomatik (linger + WSL autostart).
Kurulum: `cp deploy/watch-ceviz-backend.service ~/.config/systemd/user/ && systemctl --user enable --now watch-ceviz-backend`.
