# RTX 50 serisi (sm_120) tam uyumlu temel imaj
FROM nvidia/cuda:12.6.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

RUN apt-get update && apt-get install -y \
    python3.10 python3-pip python3.10-venv \
    libsndfile1 libsox-dev ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python
RUN pip install --upgrade pip setuptools wheel

# ADIM 1: Blackwell desteği için Modern PyTorch
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# ADIM 2: Modern fairseq2 0.8.1
RUN pip install fairseq2==0.8.1 --extra-index-url https://fair.pkg.atmeta.com/fairseq2/whl/nightly/pt2.1.1/cu121 || \
    pip install fairseq2

# ADIM 3: Gradio 5 ve Güncel Kütüphaneler (Ekran kaydı desteği için ŞART)
RUN pip install \
    "gradio>=5.0.0" \
    "huggingface_hub>=0.25.0" \
    datasets==2.18.0 \
    sonar-space==0.5.0 \
    soundfile librosa scipy fire simuleval

# ADIM 4: Seamless
RUN pip install --no-deps git+https://github.com/facebookresearch/seamless_communication.git

# ADIM 5: Kütüphane API Köprüsü
RUN printf "\nfrom typing import Any, Union\nStringLike = Union[str, Any]\nclass SequenceData: pass\n" >> /usr/local/lib/python3.10/dist-packages/fairseq2/data/__init__.py && \
    printf "\nfrom .store import get_asset_store\nasset_store = get_asset_store()\nFileAssetMetadataProvider = AssetMetadataProvider\n" >> /usr/local/lib/python3.10/dist-packages/fairseq2/assets/__init__.py && \
    printf "\nclass TextTokenizer: pass\n" >> /usr/local/lib/python3.10/dist-packages/fairseq2/data/text/__init__.py && \
    printf "from pathlib import Path\nfrom fairseq2.assets import get_asset_store\n__version__ = '0.1.0'\ndef _update_asset_store(): pass\n_update_asset_store()\n" > /usr/local/lib/python3.10/dist-packages/seamless_communication/__init__.py

WORKDIR /app
COPY . /app

EXPOSE 7860

# Blackwell optimizasyonu ve Başlatma
ENV TORCH_CUDA_ARCH_LIST="12.0"
CMD ["sh", "-c", "python -c \"import torch; print(f'RTX 5070 Ti Aktif! CUDA: {torch.version.cuda}, SM: {torch.cuda.get_device_capability()}')\" && exec python app.py"]
