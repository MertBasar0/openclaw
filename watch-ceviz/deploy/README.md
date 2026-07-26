# Watch Ceviz — Kurulum

OpenClaw'ın çalıştığı makinede, repo kökünde:

```bash
bash deploy/install.sh
```

Script şunları yapar:

1. Python venv + bağımlılıklar (GPU varsa CUDA lib'leri de kurar, model `large-v3` olur; yoksa CPU + `small`)
2. Erişim token'ı üretir (`.auth-token`, ikinci çalıştırmada korunur)
3. `systemd --user` servisini yazıp başlatır (boot'ta otomatik; systemd yoksa `nohup`)
4. Tailscale varsa backend'i tailnet'e `/ceviz` olarak yayınlar
5. Telefonda okutacağın **QR** + adres/token bilgisini basar

Telefonda: **Ceviz → Ayarlar (dişli) → QR İLE EŞLEŞ** → scriptin bastığı QR'ı okut → **BAĞLANTIYI TEST ET** → **KAYDET**.
Token telefonda Keychain'de saklanır; uygulama silinip yeniden kurulsa bile kalır.

## Ortam değişkenleri (opsiyonel)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `WATCH_CEVIZ_PORT` | `8080` | Backend portu |
| `WATCH_CEVIZ_WHISPER_MODEL` | GPU'da `large-v3`, CPU'da `small` | STT modeli |
| `WATCH_CEVIZ_WHISPER_LANGUAGE` | `tr` | STT dili |
| `OPENCLAW_WATCH_AGENT` | `main` | Komutların gideceği OpenClaw ajanı |

## WSL2 + Windows notu

Tailscale Windows host'ta çalışıyorsa (WSL2 kurulumu), `tailscale` WSL PATH'inde
olmayabilir. Bu durumda script Tailscale adımını atlar; `tailscale serve` komutunu
**Windows tarafında** bir kez elle çalıştır:

```powershell
tailscale serve --bg --set-path=/ceviz http://127.0.0.1:8080
```

Ardından telefona `https://<makine-adı>.<tailnet>.ts.net/ceviz` adresini ve `.auth-token`
içindeki token'ı gir (ya da bu ikisinden bir QR üretip okut).
