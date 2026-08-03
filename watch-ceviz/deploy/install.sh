#!/usr/bin/env bash
# Watch Ceviz backend — tek komutluk kurulum.
#
#   bash deploy/install.sh
#
# Yaptiklari:
#   - Python venv olusturur, bagimliliklari kurar (GPU varsa CUDA lib'leri de)
#   - Erisim token'i uretir
#   - systemd --user servisini yazar ve baslatir (yoksa nohup fallback)
#   - Tailscale varsa backend'i tailnet'e /ceviz olarak yayinlar
#   - Telefonda okutacagin QR + pairing bilgisini basar
#
# Repo kok dizininde ya da watch-ceviz/ icinde calistirilabilir.
set -euo pipefail

# --- Repo kokunu bul (bu script deploy/ altinda) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"          # watch-ceviz/
cd "$APP_DIR"

PORT="${WATCH_CEVIZ_PORT:-8080}"
VENV="$APP_DIR/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "==> Watch Ceviz kurulumu: $APP_DIR"

# --- 0) OpenClaw var mi? Backend onu calistiracak. ---
if command -v openclaw >/dev/null 2>&1; then
  echo "==> OpenClaw bulundu: $(command -v openclaw)"
else
  echo "!!  UYARI: 'openclaw' PATH'te bulunamadi."
  echo "    Watch Ceviz komutlari OpenClaw CLI'ini calistirir; kurulum devam"
  echo "    edecek ama komutlar 'OpenClaw CLI bulunamadi' hatasi verecek."
  echo "    OpenClaw'i kur (https://openclaw.ai) ya da servis dosyasindaki"
  echo "    PATH degiskenine openclaw'in dizinini ekle."
fi

# --- 1) venv + bagimliliklar ---
if [ ! -x "$PY" ]; then
  echo "==> Python venv olusturuluyor"
  python3 -m venv "$VENV"
fi
"$PIP" install -q --upgrade pip
"$PIP" install -q -r "$SCRIPT_DIR/requirements.txt"

# --- 2) GPU tespiti + CUDA lib'leri ---
WHISPER_MODEL="${WATCH_CEVIZ_WHISPER_MODEL:-small}"
LD_LIBS=""
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  echo "==> GPU bulundu — CUDA kutuphaneleri kuruluyor (large-v3 icin)"
  "$PIP" install -q nvidia-cublas-cu12 nvidia-cudnn-cu12
  SITE="$("$PY" -c 'import site; print(site.getsitepackages()[0])')"
  LD_LIBS="$SITE/nvidia/cublas/lib:$SITE/nvidia/cudnn/lib"
  WHISPER_MODEL="${WATCH_CEVIZ_WHISPER_MODEL:-large-v3}"
else
  echo "==> GPU yok — CPU modu (model=$WHISPER_MODEL)"
fi

# --- 3) Token ---
TOKEN_FILE="$APP_DIR/.auth-token"
if [ -f "$TOKEN_FILE" ]; then
  TOKEN="$(cat "$TOKEN_FILE")"
  echo "==> Mevcut token kullaniliyor ($TOKEN_FILE)"
else
  TOKEN="$(openssl rand -hex 24)"
  ( umask 077; printf '%s' "$TOKEN" > "$TOKEN_FILE" )
  echo "==> Yeni token uretildi ($TOKEN_FILE)"
fi

# --- 4) systemd --user servisi ---
LANG_ENV="${WATCH_CEVIZ_WHISPER_LANGUAGE:-tr}"
AGENT_ENV="${OPENCLAW_WATCH_AGENT:-main}"
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  {
    echo "[Unit]"
    echo "Description=Watch Ceviz Backend (PTT->Summary, local Whisper STT)"
    echo "After=network-online.target"
    echo ""
    echo "[Service]"
    echo "Type=simple"
    echo "WorkingDirectory=$APP_DIR"
    echo "Environment=HOME=$HOME"
    echo "Environment=WATCH_CEVIZ_STT_ENGINE=auto"
    echo "Environment=WATCH_CEVIZ_WHISPER_MODEL=$WHISPER_MODEL"
    echo "Environment=WATCH_CEVIZ_WHISPER_LANGUAGE=$LANG_ENV"
    echo "Environment=OPENCLAW_WATCH_AGENT=$AGENT_ENV"
    echo "Environment=WATCH_CEVIZ_AUTH_TOKEN=$TOKEN"
    [ -n "$LD_LIBS" ] && echo "Environment=LD_LIBRARY_PATH=$LD_LIBS"
    echo "ExecStart=$PY $APP_DIR/backend/main.py $PORT"
    echo "Restart=on-failure"
    echo "RestartSec=5"
    echo ""
    echo "[Install]"
    echo "WantedBy=default.target"
  } > "$UNIT_DIR/watch-ceviz-backend.service"
  systemctl --user daemon-reload
  systemctl --user enable --now watch-ceviz-backend >/dev/null 2>&1 || systemctl --user restart watch-ceviz-backend
  command -v loginctl >/dev/null 2>&1 && loginctl enable-linger "$(whoami)" >/dev/null 2>&1 || true
  echo "==> Servis calisiyor (systemctl --user status watch-ceviz-backend)"
else
  echo "==> systemd yok — nohup ile baslatiliyor"
  pkill -f "backend/main.py $PORT" 2>/dev/null || true
  LD_LIBRARY_PATH="$LD_LIBS" WATCH_CEVIZ_AUTH_TOKEN="$TOKEN" \
    WATCH_CEVIZ_WHISPER_MODEL="$WHISPER_MODEL" WATCH_CEVIZ_WHISPER_LANGUAGE="$LANG_ENV" \
    WATCH_CEVIZ_STT_ENGINE=auto OPENCLAW_WATCH_AGENT="$AGENT_ENV" \
    nohup "$PY" "$APP_DIR/backend/main.py" "$PORT" > "$APP_DIR/backend.log" 2>&1 &
fi

# --- 5) Tailscale yayini + URL ---
# Tailscale yoksa bile kullanilabilir bir adres uret: yerel ag IP'si.
# Minimal sistemlerde `ip`/`hostname` bulunmayabilir — hicbiri kurulumu
# durdurmamali, en kotu ihtimalle yer tutucu adres basariz.
LAN_IP=""
if command -v ip >/dev/null 2>&1; then
  LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.*src \([0-9.]*\).*/\1/p' | head -1 || true)"
fi
if [ -z "$LAN_IP" ] && command -v hostname >/dev/null 2>&1; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi
BASE_URL="http://${LAN_IP:-<bu-makinenin-adresi>}:$PORT"
if command -v tailscale >/dev/null 2>&1; then
  tailscale serve --bg --set-path=/ceviz "http://127.0.0.1:$PORT" >/dev/null 2>&1 || \
    tailscale serve --bg --https=443 --set-path /ceviz "http://127.0.0.1:$PORT" >/dev/null 2>&1 || true
  TS_HOST="$(tailscale status --json 2>/dev/null | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("Self",{}).get("DNSName","").rstrip("."))' 2>/dev/null || true)"
  [ -n "$TS_HOST" ] && BASE_URL="https://$TS_HOST/ceviz"
  echo "==> Tailscale serve: $BASE_URL"
else
  echo "==> Tailscale bulunamadi — telefonun backend'e ulasabilecegi bir URL girmen gerekecek"
fi

# --- 6) Pairing QR + bilgi ---
echo ""
echo "======================================================================"
echo "  Kurulum tamam. Telefonda Ceviz > Ayarlar > QR Tara ile oku:"
echo "======================================================================"
"$PY" - "$BASE_URL" "$TOKEN" <<'PYEOF'
import sys, urllib.parse
base, token = sys.argv[1], sys.argv[2]
uri = "ceviz://pair?u=" + urllib.parse.quote(base, safe="") + "&t=" + urllib.parse.quote(token, safe="")
try:
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(uri); qr.make(fit=True)
    qr.print_ascii(invert=True)
except Exception as e:
    print("(QR ciziminde sorun:", e, "— asagidaki bilgiyi elle gir)")
print()
print("  Sunucu adresi :", base)
print("  Token         :", token)
print("  Pairing URI   :", uri)
PYEOF
echo "======================================================================"
