# Ceviz 2026.6.5 Beta 1

Ceviz'in ilk açık beta sürümü, kendi makinesinde OpenClaw çalıştıran
geliştiriciler ve operatörler için Apple Watch ve iPhone'u kompakt bir kontrol
yüzeyine dönüştürüyor.

## Öne çıkanlar

- Apple Watch'tan kısa sesli komut gönderme, bilekte sonuç özeti ve iPhone'da
  ayrıntılı rapor.
- Aynı konuşmada devam komutları, iş zinciri gezinmesi, alt ajan/araç bilgileri
  ve eyleme dönük sonraki adımlar.
- Tek komutluk self-hosted backend kurulumu; QR eşleşme, Keychain token saklama,
  Tailscale ve WSL2 için yerel Windows relay seçenekleri.
- Taze kurulumda otomatik Demo Modu; hesap veya backend olmadan tüm temel
  ekranların örnek veriyle incelenebilmesi.
- İngilizce ana dil ve Türkçe yerelleştirme.
- iPhone ve Apple Watch'a terminal durum push bildirimleri, ayırt edilebilir
  bildirim sesi ve uyku/yeniden açılma sonrasında sonuç toparlama.

## Güvenlik ve gizlilik

- Komutlar yalnızca kullanıcının yapılandırdığı self-hosted backend'e gider.
- Erişim bearer token ile korunur; token iOS Keychain'de saklanır.
- Düz HTTP yalnızca yerel ağ relay adresleri için kabul edilir; genel uçlar
  HTTPS gerektirir.
- Varsayılan konuşma çözümleme kullanıcının kendi makinesinde Whisper ile
  yapılır. Uygulamada analitik, reklam veya izleme SDK'sı yoktur.

## Doğrulama

- Backend ve contract testleri: **34/34 geçti**.
- iOS + gömülü watchOS Release build'i ve TestFlight yüklemesi aynı zorunlu CI
  bariyerinde geçti.
- TestFlight build: **2026.6.5 (1787259702)**.
- Fiziksel iPhone + Apple Watch smoke testi geçti: doğrudan Watch push, sonuç
  ekranı ve bildirim sesi doğrulandı.
- Temiz Ubuntu 24.04 WSL2 ortamında sıfırdan kurulum, QR eşleşme, 401/200 auth,
  komut polling'i ve servis yeniden başlatma kalıcılığı doğrulandı.
- Simulator screenshot workflow'u:
  <https://github.com/MertBasar0/openclaw/actions/workflows/ceviz-screenshots.yml>

## Bilinen sınırlamalar

- İlk Whisper model indirmesi ilk komutu birkaç dakika yavaşlatabilir.
- watchOS kısıtları nedeniyle kısa ve odaklı sesli komutlar önerilir.
- WSL2 yolu kapsamlı doğrulandı; macOS ve bare Linux kurulumları dış kullanıcı
  geri bildirimi açısından daha az test edildi.
- Bağımsız bir dış kullanıcının yardım almadan onboarding tamamlaması hâlâ açık
  beta sırasında izlenecek kullanılabilirlik doğrulamasıdır.

## Bağlantılar

- Açık beta: <https://testflight.apple.com/join/nEdn2Np2>
- Ürün ve kurulum özeti: <https://basarlabs.com.tr/ceviz/>
- Gizlilik politikası: <https://basarlabs.com.tr/ceviz/privacy/>
