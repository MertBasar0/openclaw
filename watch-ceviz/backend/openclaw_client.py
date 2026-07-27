from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TaskResult:
    category: str
    canned_result: str
    watch_summary: str
    requires_phone_handoff: bool
    phone_report: str
    next_action: str | None
    outcome: str | None = None
    next_action_actor: str | None = None


@dataclass
class InvocationHandle:
    command: list[str]
    log_path: str
    started_at: float
    process: subprocess.Popen[Any]
    prompt: str


class OpenClawClient:
    """Thin OpenClaw CLI integration for watch-originated jobs."""

    REPORT_START = "<watch_ceviz_phone_report>"
    REPORT_END = "</watch_ceviz_phone_report>"
    META_START = "<watch_ceviz_meta>"
    META_END = "</watch_ceviz_meta>"

    def __init__(
        self,
        agent: str | None = None,
        runtime_dir: str | os.PathLike[str] | None = None,
    ) -> None:
        self.agent = agent or os.environ.get("OPENCLAW_WATCH_AGENT", "main")
        self.runtime_dir = Path(
            runtime_dir
            or os.environ.get("OPENCLAW_WATCH_RUNTIME_DIR")
            or (Path(tempfile.gettempdir()) / "watch-ceviz-openclaw")
        )
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def invoke_watch_command(self, payload: dict[str, Any]) -> InvocationHandle:
        prompt = self._build_prompt(payload)
        log_path = self.runtime_dir / f"watch-job-{uuid.uuid4().hex}.log"
        log_file = log_path.open("w", encoding="utf-8")
        command = [
            "openclaw",
            "agent",
            "--agent",
            self.agent,
            "--json",
            "--message",
            prompt,
        ]
        process = subprocess.Popen(  # noqa: S603
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_file.close()
        return InvocationHandle(
            command=command,
            log_path=str(log_path),
            started_at=time.time(),
            process=process,
            prompt=prompt,
        )

    def extract_result(self, log_path: str) -> TaskResult:
        raw_output = Path(log_path).read_text(encoding="utf-8")
        parsed = json.loads(raw_output)
        payloads = parsed.get("result", {}).get("payloads", [])
        response_text = "\n\n".join(
            payload.get("text", "").strip()
            for payload in payloads
            if payload.get("text")
        ).strip()
        if not response_text:
            response_text = "OpenClaw çağrısı tamamlandı ama metin yanıtı dönmedi."

        structured = self._extract_structured_payload(response_text)
        clean_text = structured["phone_report"] or response_text

        return TaskResult(
            category=structured["category"] or self._categorize_text(clean_text),
            canned_result=clean_text,
            watch_summary=structured["watch_summary"] or self._build_watch_summary(clean_text),
            requires_phone_handoff=(
                structured["requires_phone_handoff"]
                if structured["requires_phone_handoff"] is not None
                else self._requires_phone_handoff(clean_text)
            ),
            phone_report=self._build_phone_report(clean_text),
            next_action=structured["next_action"] or self._extract_next_action(clean_text),
            outcome=structured.get("outcome"),
            next_action_actor=structured.get("next_action_actor"),
        )

    # --- Canli durum enjeksiyonu ---------------------------------------
    # Saat komutlari kendi session'inda calisiyor (agent:<id>:main), TUI /
    # webchat isleri baska session'da. Bu yuzden ajan "ne uzerinde
    # calisiyorsun?" sorusuna kendi transkriptinden bakip "is yok" diyor,
    # zorlandiginda hafizadan eski isleri anlatiyordu. Cozum: session
    # indeksinden CANLI durumu okuyup prompt'a gercek veri olarak vermek.

    @staticmethod
    def _last_user_message(session_path: Path, max_tail: int = 200_000) -> str:
        """Buyuk transkriptleri bastan okumamak icin yalnizca kuyrugu tara."""
        try:
            size = session_path.stat().st_size
            with session_path.open("rb") as fh:
                if size > max_tail:
                    fh.seek(size - max_tail)
                    fh.readline()  # yarim satiri at
                raw = fh.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

        latest = ""
        for line in raw.splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                continue
            message = obj.get("message") if isinstance(obj.get("message"), dict) else obj
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text", "")) for part in content if isinstance(part, dict)
                )
            text = " ".join(str(content or "").split())
            if text:
                latest = text
        return latest

    def collect_live_status(self, limit: int = 4, window_hours: float = 24.0) -> list[str]:
        own_key = f"agent:{self.agent}:main"
        try:
            index_path = Path.home() / ".openclaw" / "agents" / self.agent / "sessions" / "sessions.json"
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        now_ms = time.time() * 1000
        rows: list[tuple[float, str, dict]] = []
        for key, info in (data.items() if isinstance(data, dict) else []):
            if not isinstance(info, dict):
                continue
            updated = info.get("updatedAt") or info.get("lastActivity") or 0
            if not isinstance(updated, (int, float)) or updated <= 0:
                continue
            if (now_ms - updated) > window_hours * 3600 * 1000:
                continue
            rows.append((updated, key, info))

        rows.sort(reverse=True)
        sessions_dir = Path.home() / ".openclaw" / "agents" / self.agent / "sessions"
        lines: list[str] = []
        for updated, key, info in rows[:limit]:
            minutes = max(0, int((now_ms - updated) / 60000))
            when = f"{minutes} dk önce" if minutes < 60 else f"{minutes // 60} sa önce"
            origin = info.get("origin") if isinstance(info.get("origin"), dict) else {}
            surface = str(origin.get("surface") or origin.get("provider") or "bilinmeyen")
            if key == own_key:
                surface += " (bu saat kanalı)"

            summary = ""
            session_id = info.get("sessionId")
            if session_id:
                summary = self._last_user_message(sessions_dir / f"{session_id}.jsonl")
            # Saat komutlari uzun prompt sarmalayicisi; kisalt.
            if summary.startswith("Bu istek Apple Watch"):
                summary = "(saatten gelen sesli komut)"
            if len(summary) > 160:
                summary = summary[:159].rstrip() + "…"

            lines.append(f"- {surface} · {when}: {summary or '(içerik okunamadı)'}")

        return lines

    def collect_background_activity(self, started_at: float, log_path: str) -> list[str]:
        """Is sirasinda arkada ne oldu: kullanilan araclar + alt ajanlar.

        Rapora "ALT AJANLAR & ARACLAR" bolumu olarak girer. Veri iki
        kaynaktan: sonuc JSON'undaki toolSummary ve `openclaw sessions`
        listesindeki, is penceresi icinde guncellenmis subagent session'lari.
        """
        lines: list[str] = []

        try:
            parsed = json.loads(Path(log_path).read_text(encoding="utf-8"))
            summary = parsed.get("result", {}).get("meta", {}).get("toolSummary") or {}
            tools = summary.get("tools") or []
            if tools:
                calls = summary.get("calls", 0)
                failures = summary.get("failures", 0)
                fail_note = f", {failures} hata" if failures else ""
                lines.append(f"Araçlar: {', '.join(tools)} ({calls} çağrı{fail_note})")
        except Exception:
            pass

        # `openclaw sessions` CLI'i spawn edilen oturumlari listelemiyor;
        # dogrudan agent'in sessions.json indeksinden oku. Is penceresinde
        # guncellenen, ana oturum ve kanal oturumlari disindaki her oturum
        # arka plan calismasi sayilir.
        try:
            index_path = Path.home() / ".openclaw" / "agents" / self.agent / "sessions" / "sessions.json"
            data = json.loads(index_path.read_text(encoding="utf-8"))
            window_start_ms = (started_at - 5) * 1000
            channel_markers = (
                ":whatsapp:", ":telegram:", ":discord:", ":slack:", ":matrix:",
                ":qqbot:", ":signal:", ":imessage:", ":sms:",
            )
            for key, info in (data.items() if isinstance(data, dict) else []):
                if not isinstance(info, dict):
                    continue
                if key == f"agent:{self.agent}:main" or any(m in key for m in channel_markers):
                    continue
                updated = info.get("updatedAt") or info.get("lastActivity") or 0
                if not isinstance(updated, (int, float)) or updated < window_start_ms:
                    continue
                title = info.get("displayName") or info.get("title") or info.get("label") or key.split(":")[-1]
                lines.append(f"Alt ajan/oturum: {str(title)[:90]}")
        except Exception:
            pass

        return lines

    def read_log_tail(self, log_path: str, max_chars: int = 1200) -> str:
        if not Path(log_path).exists():
            return ""
        contents = Path(log_path).read_text(encoding="utf-8", errors="replace")
        return contents[-max_chars:].strip()

    # Cihaz dili -> (dil adi, hedef dilde vurgulu direktif). Prompt iskeleti
    # Turkce kalir (tum davranis kurallari orada test edildi) ama CIKTI dili
    # kullanicinin cihaz diline gore belirlenir.
    LANGUAGE_DIRECTIVES = {
        "tr": ("Türkçe", "Tüm çıktıyı Türkçe üret."),
        "en": ("English", "IMPORTANT: Write every part of your answer in English."),
        "de": ("Deutsch", "WICHTIG: Antworte vollständig auf Deutsch."),
        "fr": ("Français", "IMPORTANT : rédige toute ta réponse en français."),
        "es": ("Español", "IMPORTANTE: escribe toda tu respuesta en español."),
        "it": ("Italiano", "IMPORTANTE: scrivi tutta la risposta in italiano."),
        "nl": ("Nederlands", "BELANGRIJK: schrijf je volledige antwoord in het Nederlands."),
        "pt": ("Português", "IMPORTANTE: escreva toda a resposta em português."),
    }

    def _language_block(self, payload: dict[str, Any]) -> str:
        locale = str(payload.get("locale") or "").strip()
        code = locale.replace("_", "-").split("-")[0].lower() if locale else "tr"
        name, emphatic = self.LANGUAGE_DIRECTIVES.get(
            code, (locale or code, f"IMPORTANT: Write your entire answer in the user's language ({locale or code}).")
        )
        return (
            f"ÇIKTI DİLİ: {name} (kullanıcının cihaz dili). Rapor bloğu, watch_summary, "
            f"next_action ve tüm serbest metinler bu dilde olmalı; alan adları/JSON anahtarları değişmez.\n"
            f"{emphatic}\n"
        )

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        audio_format = payload.get("format", "unknown")
        client_timestamp = payload.get("client_timestamp", "unknown")
        audio_size = len(payload.get("audio_data", ""))
        optional_transcript = (payload.get("transcript") or "").strip()
        stt_source = (payload.get("_stt_source") or "unknown").strip()
        stt_error = (payload.get("_stt_error") or "").strip()

        transcript_line = (
            f"Çözümlenen transkript: {optional_transcript}\n"
            if optional_transcript
            else "Transkript üretilemedi.\n"
        )
        continuation = (payload.get("_continuation_context") or "").strip()
        continuation_block = f"\n{continuation}\n" if continuation else ""

        # Saat kendi session'inda calisir; makinede olan biteni gormesi icin
        # canli durumu prompt'a gercek veri olarak koy.
        try:
            live = self.collect_live_status()
        except Exception:
            live = []
        live_block = ""
        if live:
            live_block = (
                "\nCANLI DURUM (bu makinedeki oturumların son etkinliği — gerçek veri, "
                "senin transkriptinde görünmese de geçerli):\n"
                + "\n".join(live)
                + "\nBu listeyi 'ne üzerinde çalışıyorsun / aktif işler neler' türü sorularda "
                "BİRİNCİL kaynak olarak kullan. Kendi konuşma geçmişinde iş görmüyorsan 'iş yok' "
                "deme; buradaki oturumlara bak. Hafızadaki/eski notlardaki işleri güncel işmiş "
                "gibi sunma — yalnızca burada listelenenler güncel.\n"
            )
        stt_status_line = f"STT kaynağı: {stt_source}\n"
        stt_error_line = f"STT fallback nedeni: {stt_error}\n" if stt_error else ""

        return (
            "Bu istek Apple Watch kaynaklı Watch Ceviz backend entegrasyonundan geliyor. "
            "Amaç, saatten gelen kısa komutları telefona devredilebilir net bir sonuca çevirmek.\n\n"
            f"Ses formatı: {audio_format}\n"
            f"İstemci zaman damgası: {client_timestamp}\n"
            f"Base64 ses yükü uzunluğu: {audio_size}\n"
            f"{stt_status_line}"
            f"{stt_error_line}"
            f"{transcript_line}"
            f"{continuation_block}"
            f"{live_block}\n"
            f"{self._language_block(payload)}"
            "Eğer gerçek transkript yoksa bunu açıkça söyle ve en güvenli bir sonraki adımı öner. "
            "Transkript bozuk/anlamsız görünüyorsa TAHMİNLE İŞLEM YAPMA: ne anladığını tek cümleyle söyle, "
            "requires_phone_handoff=true yap ve next_action olarak düzeltilmiş komutu onaylatmayı öner. "
            "watch_summary HER ZAMAN somut olsun: tam olarak ne yapıldığını veya neden yapılmadığını söyle; "
            "'önceki rapora işlendi' gibi bağlama atıf yapan opak ifadeler kullanma. "
            "Yanıtı iki blok halinde üret ve marker metinlerini aynen koru.\n"
            f"1) İlk blok tam olarak {self.REPORT_START} ile başlayıp {self.REPORT_END} ile bitsin. "
            "Bu blokta telefonda gösterilecek doğal Türkçe rapor olsun. Raporda şu sırayı kullan: "
            "1. Kısa durum, 2. Ne anlaşıldı / sınırlama, 3. Önerilen sonraki adım.\n"
            f"2) İkinci blok tam olarak {self.META_START} ile başlayıp {self.META_END} ile bitsin. "
            "Bu blokta tek satır geçerli JSON nesnesi ver. Şema: "
            '{"watch_summary":"...","next_action":"..."|null,"next_action_actor":"agent"|"user","outcome":"done"|"blocked"|"needs_input","requires_phone_handoff":true,"category":"..."}. '
            "outcome: istenen iş gerçekten yapıldıysa done, yapılamadıysa blocked, kullanıcıdan bilgi/onay gerekiyorsa needs_input. "
            "next_action_actor: next_action'ı AJAN kendisi çalıştırabilecekse agent yaz ve next_action'ı komut kipinde üret; "
            "yalnızca kullanıcının davranışı gerekiyorsa user yaz (bu tür öneriler kullanıcıya bilgi olarak gösterilir, ajana geri gönderilmez). "
            "user türü next_action'da 'onaylayın/onayla' gibi seçim-bekleyen ifadeler KULLANMA — ortada onaylanacak bir şey yok; "
            "bunun yerine kullanıcının ne söylemesi gerektiğini çıktı dilinde açık bir yönerge olarak yaz "
            "(TR: 'Yeni komut verin: ...', EN: 'Say this instead: ...'). "
            "Yapılacak bir sonraki adım YOKSA next_action'ı null bırak ve next_action_actor'ı da null yap. "
            "'Yok.', 'Ek işlem gerekmiyor.', 'İşlem gerekmiyor.' gibi dolgu cümlelerini next_action olarak ASLA yazma — "
            "bunlar buton haline gelip tekrar sana gönderiliyor ve kısır döngü yaratıyor; durumu anlatmak istiyorsan rapor bloğunda anlat. "
            "watch_summary tek cümle ve 160 karakter altında olsun. next_action net, uygulanabilir tek adım olsun. "
            "JSON dışında meta bloğunda başka açıklama yazma."
        )

    def _extract_structured_payload(self, text: str) -> dict[str, Any]:
        phone_report = self._extract_tagged_block(text, self.REPORT_START, self.REPORT_END)
        meta_raw = self._extract_tagged_block(text, self.META_START, self.META_END)
        meta: dict[str, Any] = {}

        if meta_raw:
            try:
                parsed_meta = json.loads(meta_raw)
                if isinstance(parsed_meta, dict):
                    meta = parsed_meta
            except json.JSONDecodeError:
                meta = {}

        return {
            "phone_report": (phone_report or self._strip_structured_blocks(text)).strip(),
            "watch_summary": self._clean_optional_text(meta.get("watch_summary")),
            "next_action": self._clean_optional_text(meta.get("next_action")),
            "category": self._clean_optional_text(meta.get("category")),
            "requires_phone_handoff": self._coerce_optional_bool(meta.get("requires_phone_handoff")),
            "outcome": self._clean_optional_text(meta.get("outcome")),
            "next_action_actor": self._clean_optional_text(meta.get("next_action_actor")),
        }

    def _extract_tagged_block(self, text: str, start_tag: str, end_tag: str) -> str | None:
        pattern = re.escape(start_tag) + r"\s*(.*?)\s*" + re.escape(end_tag)
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            return None
        block = match.group(1).strip()
        return block or None

    def _strip_structured_blocks(self, text: str) -> str:
        stripped = re.sub(
            re.escape(self.REPORT_START) + r".*?" + re.escape(self.REPORT_END),
            "",
            text,
            flags=re.DOTALL,
        )
        stripped = re.sub(
            re.escape(self.META_START) + r".*?" + re.escape(self.META_END),
            "",
            stripped,
            flags=re.DOTALL,
        )
        return stripped.strip()

    def _clean_optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if text.lower() == "null":
            return None
        return text or None

    def _coerce_optional_bool(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1", "evet"}:
                return True
            if normalized in {"false", "no", "0", "hayır", "hayir"}:
                return False
        return None

    def _categorize_text(self, text: str) -> str:
        text_lower = text.lower()
        if any(word in text_lower for word in ["mail", "e-posta", "posta"]):
            return "E-posta İşlemleri"
        if any(word in text_lower for word in ["takvim", "calendar", "meeting", "toplantı"]):
            return "Takvim / Program"
        if any(word in text_lower for word in ["kod", "git", "pull request", "pr", "review"]):
            return "Yazılım / Kod"
        return "OpenClaw Asistan"

    def _build_watch_summary(self, text: str, max_len: int = 200) -> str:
        normalized = " ".join(part.strip() for part in text.splitlines() if part.strip())
        normalized = re.sub(r"\b[123]\s*[\.)]\s*", "", normalized).strip()
        if not normalized:
            return "Sonuç üretildi ama özet metni boş döndü."

        preferred_chunks = []
        for separator in [". ", "\n", "; "]:
            preferred_chunks.extend(chunk.strip() for chunk in normalized.split(separator) if chunk.strip())
        preferred_chunks.append(normalized)

        for chunk in preferred_chunks:
            if len(chunk) < 8:
                continue
            if len(chunk) <= max_len:
                return chunk

        return normalized[: max_len - 1].rstrip() + "…"

    def _requires_phone_handoff(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True

        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        text_lower = stripped.lower()
        code_markers = ["```", "def ", "class ", "diff ", "+++", "---", "{" , "}"]
        has_code_like_content = any(marker in stripped for marker in code_markers)
        has_list_like_content = sum(line.startswith(("-", "*", "•")) for line in lines) >= 3
        has_many_lines = len(lines) >= 5
        is_long = len(stripped) > 280
        has_dense_guidance = any(keyword in text_lower for keyword in ["adım", "next", "sonraki adım", "checklist", "liste"]) and len(stripped) > 180
        return has_code_like_content or has_list_like_content or has_many_lines or is_long or has_dense_guidance

    def _build_phone_report(self, text: str) -> str:
        return text.strip() or "OpenClaw çağrısı tamamlandı ama ayrıntılı rapor boş döndü."

    def _extract_next_action(self, text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None

        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        heading_markers = [
            "3. önerilen sonraki adım",
            "3) önerilen sonraki adım",
            "önerilen sonraki adım:",
            "sonraki adım:",
            "suggested next action:",
            "next action:",
        ]

        for index, line in enumerate(lines):
            normalized = line.lower()
            if normalized in heading_markers:
                collected: list[str] = []
                for candidate in lines[index + 1 :]:
                    candidate_lower = candidate.lower()
                    if any(
                        candidate_lower.startswith(prefix)
                        for prefix in ["1.", "2.", "3.", "1)", "2)", "3)"]
                    ):
                        break
                    collected.append(candidate.lstrip("-• ").strip())
                result = " ".join(part for part in collected if part).strip()
                if result:
                    return result

            for marker in heading_markers:
                if normalized.startswith(marker):
                    inline = line[len(marker):].lstrip(" :-").strip()
                    if inline:
                        return inline

        return None
