import gradio as gr
import torch
from transformers import AutoProcessor, SeamlessM4Tv2Model
import scipy.io.wavfile as wavfile
import numpy as np
import librosa
import subprocess
import os

# Log fonksiyonu
def log(msg):
    print(f"[*] {msg}", flush=True)

log("--- OpenClaw Modern Tercüman: Screen Audio Edition ---")

device = "cuda" if torch.cuda.is_available() else "cpu"
model_id = "facebook/seamless-m4t-v2-large"

# Modeli Yükle (Blackwell Optimize)
log("Model ve İşlemci yükleniyor...")
processor = AutoProcessor.from_pretrained(model_id)
model = SeamlessM4Tv2Model.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    low_cpu_mem_usage=True
).to(device)
log("[+] Sistem Hazır!")

def process_translation(audio_input, video_input):
    # Giriş kontrolü: Video (Ekran) veya Audio (Mikrofon)
    source_path = None
    
    if video_input is not None:
        log("Ekran kaydından ses ayıklanıyor...")
        source_path = "extracted_audio.wav"
        # ffmpeg ile videodan sesi ayıkla (16kHz, mono)
        subprocess.run([
            "ffmpeg", "-y", "-i", video_input, 
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", 
            source_path
        ], check=True)
    elif audio_input is not None:
        source_path = audio_input
    else:
        return None, "Lütfen bir ses kaynağı seçin (Mikrofon veya Ekran)."

    try:
        log(f"Çeviri işlemi başladı: {source_path}")
        audio, _ = librosa.load(source_path, sr=16000)
        audio_inputs = processor(audios=audio, sampling_rate=16000, return_tensors="pt").to(device)
        
        if device == "cuda":
            audio_inputs = {k: v.to(torch.bfloat16) if v.dtype == torch.float32 else v for k, v in audio_inputs.items()}

        with torch.no_grad():
            output = model.generate(**audio_inputs, tgt_lang="tur")
        
        translated_text = processor.batch_decode(output[1], skip_special_tokens=True)[0]
        translated_audio = output[0].cpu().numpy().squeeze()

        output_path = "output.wav"
        max_val = np.max(np.abs(translated_audio))
        if max_val > 0: translated_audio = translated_audio / max_val
        wavfile.write(output_path, 16000, (translated_audio * 32767).astype(np.int16))
        
        log(f"Çeviri tamamlandı: {translated_text}")
        return output_path, translated_text
    except Exception as e:
        log(f"HATA: {str(e)}")
        return None, f"Hata: {str(e)}"

# Gradio Arayüzü
with gr.Blocks(title="OpenClaw Modern Tercüman") as demo:
    gr.Markdown("# 🎙️ SeamlessM4T v2 (Screen & System Audio)")
    gr.Markdown("Pencere sesini yakalamak için 'Ekran Kaydı' kısmını kullanın ve **'Sistem sesini paylaş'**ı işaretleyin.")
    
    with gr.Tabs():
        with gr.TabItem("🎤 Mikrofon"):
            mic_input = gr.Audio(sources=["microphone"], type="filepath", label="Mikrofonunuz")
        with gr.TabItem("🖥️ Ekran / Sistem Sesi"):
            screen_input = gr.Video(sources=["screen"], label="Ekran ve Ses Paylaşımı")
    
    with gr.Row():
        output_audio = gr.Audio(label="Türkçe Ses")
        output_text = gr.Textbox(label="Türkçe Metin")
    
    btn = gr.Button("Tercüme Et", variant="primary")
    btn.click(
        fn=process_translation, 
        inputs=[mic_input, screen_input], 
        outputs=[output_audio, output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
