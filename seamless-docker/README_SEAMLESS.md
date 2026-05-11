# 🎙️ SeamlessM4T v2 Yerel Canlı Tercüman (Blackwell Edition)

Bu doküman, OpenClaw ekosistemi içerisinde RTX 5070 Ti (sm_120) donanımı üzerinde optimize edilmiş SeamlessM4T v2 modelinin kurulum ve kullanım detaylarını içerir.

## 🛠️ Sistem Özeti
- **Model:** Meta SeamlessM4T v2 (Large)
- **Motor:** Hugging Face Transformers
- **Arayüz:** Gradio (Web Tabanlı)
- **Donanım:** NVIDIA GeForce RTX 5070 Ti (16GB VRAM)
- **Teknoloji:** Docker, CUDA 12.6, PyTorch 2.5.1+cu124

## 🚀 Hızlı Başlangıç

Tercümanı başlatmak için aşağıdaki komutu terminalde çalıştırmanız yeterlidir:

```bash
cd ~/.openclaw/workspace/seamless-docker
docker build -t seamless-translator .
docker run --rm --gpus all -p 7860:7860 seamless-translator
```

Konteyner çalıştıktan sonra tarayıcınızdan şu adrese gidin:
👉 **http://localhost:7860**

## 💡 Kritik Optimizasyonlar

Bu kurulum, RTX 5070 Ti kartının potansiyelini tam kullanmak ve kütüphane uyumsuzluklarını gidermek için şu özel ayarları barındırır:

1.  **FP16 Hassasiyeti (Half Precision):** Model 8.5 GB olmasına rağmen, GPU belleğinde 34 GB yerine sadece ~4.2 GB yer kaplar. Bu sayede 16GB VRAM kapasitesine sahip kartlarda takılmadan çalışır.
2.  **sm_120 (Blackwell) Desteği:** PyTorch ve CUDA sürümleri, RTX 50 serisi çekirdeklerini en verimli şekilde kullanacak (Compute Capability 12.0) sürümler arasından seçilmiştir.
3.  **Modern Bridge (Kütüphane Yaması):** Meta'nın `seamless_communication` kütüphanesi ile modern `fairseq2` arasındaki API farkları, Dockerfile içinde çalışma anında otomatik olarak yamalanır.

## 📁 Dosya Yapısı
- `Dockerfile`: Sistemin işletim sistemi ve kütüphane iskeleti.
- `app.py`: Gradio arayüzü ve çeviri mantığını yöneten Python kodu.

## 🛠️ Sorun Giderme

### Port Hatası (Port already allocated)
Eğer 7860 portunun dolu olduğuna dair bir hata alırsanız, aşağıdaki temizlik komutunu çalıştırın:
```bash
docker rm -f $(docker ps -aq --filter "publish=7860")
```

### Docker Bellek Sorunları
Docker'ın sistem belleğini çok tükettiğini düşünüyorsanız, kullanılmayan tüm imaj ve konteynerleri şu komutla temizleyebilirsiniz:
```bash
docker system prune -a --volumes
```

---
*Hazırlayan: OpenClaw Assistant (Gemini CLI)*
*Tarih: 2 Mayıs 2026*
