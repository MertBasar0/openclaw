# Lansman duyuruları — hazır metinler

Sıra önerisi: **1) OpenClaw Discord `#self-promotion` → 2) X (@openclaw etiketli) → 3) LinkedIn.**
Discord ilk sırada çünkü hedef kitle tam orada (zaten kendi makinesinde ajan
çalıştıran insanlar) ve OpenClaw'ın resmi showcase sayfası açıkça oradan
paylaşmaya davet ediyor — showcase'e alınmanın yolu bu.

**Açık beta kararı:** Bağımsız dış kullanıcı onboarding'i için uygun ek cihaz
ve test kullanıcısı bulunamadığından bu kapı açık beta için kabul edilmiş risk
olarak ertelendi. İzole temiz ortam doğrulaması ve fiziksel iPhone + Apple Watch
Beta 2 akışı yeterli proxy doğrulama kabul edildi. Duyurular yayımlanabilir;
ilk gerçek dış kurulumlar lansman sonrası yakından izlenecek. macOS ve bare
Linux yolları “geçti” olarak sunulmayacak.

### Güncel doğrulama durumu (23 Ağustos 2026)

| Doğrulanmış | Doğrulanmamış |
|---|---|
| Beta 2 (`2026.6.5 (1787435232)`) fiziksel iPhone + Apple Watch'ta doğrulandı; doğrudan Watch push, uygulama açılmadan bildirim, bildirime dokununca tamamlanmış sonucun Home'a uygulanması ve ses doğru çalıştı | Gerçek bir dış kullanıcının talimatları yardım almadan tamamladığı kullanılabilirlik testi; açık beta sonrası izlenecek kabul edilmiş risk |
| Resmî Ubuntu 24.04 rootfs ile ayrı WSL2 sanal dağıtımında GitHub klonu ve sıfırdan teknik onboarding geçti | Windows üzerinde iOS/Watch simülatörü bulunmadığı için aynı turda simülatör UI testi |
| Resmî OpenClaw installer, Ceviz venv/token/service kurulumu, 401/200 auth ayrımı, poll edilebilir komut ve yeniden başlatma kalıcılığı doğrulandı | macOS ve bare Linux kurulum yollarının gerçek kullanıcı testi |
| QR eşleşme, token korumalı relay erişimi ve aynı Wi-Fi akışı | Taze kurulumda ilk Whisper model indirme süresinin farklı makinelerde ölçümü |
| TestFlight CI: 34/34 backend/contract testi, iOS/Watch build ve yükleme aynı zorunlu bariyerde geçti | Farklı Apple ID ve farklı saat modellerinde son build testi |
| WSL2 keepalive; backend kesintisinde relay'in yaşaması ve otomatik toparlanması | Çok günlük kesintisiz kullanım ve farklı ağlar arasında soak testi |
| TestFlight build'i public external `Beta` grubunda; `VALID / BETA_APPROVED` durumu ve public link erişimi otomatik olarak tekrar okundu | İlk dış kullanıcıdan tamamlanmış onboarding geri bildirimi |

### Temiz sanal onboarding kararı

Release kapısı teknik onboarding açısından **geçti**. Test, mevcut geliştirme
ortamından kopya kullanmadan resmî Ubuntu 24.04 WSL rootfs'i ve GitHub'daki
`ceviz-watch-app-build` dalı ile yapıldı. Test sırasında relay kurulumu
başarısızken installer'ın boş URL'li QR üretip başarılı çıkması yakalandı;
installer artık bu durumda fail-closed davranıyor.

Bu sonuç bağımsız bir insanın dokümantasyonu yardım almadan anlayabildiğini
kanıtlamaz. Uygun ek cihaz/test kullanıcısı bulunamadığı için bu doğrulama
“geçti” sayılmadı; açık betayı durdurmayan, lansman sonrası izlenecek kabul
edilmiş risk olarak kaydedildi.

---

## 1) Discord — `#self-promotion` (discord.gg/clawd)

> **Ceviz — OpenClaw on your wrist (Apple Watch + iPhone, open beta)**
>
> I kept reaching for my laptop just to ask "did that deploy go through?", so I
> built a control surface for OpenClaw that lives on my watch.
>
> Press, speak, done: the watch records a short command, my iPhone forwards it to
> a small backend on my own machine, and OpenClaw does the actual work. The reply
> comes back as a summary short enough to read on a wrist; when there's more to
> it, the phone gets the full report — status, analysis, which subagents and
> tools ran, and the next action worth taking. Follow-ups stay in the same
> conversation, so "now do it for staging" just works.
>
> Everything stays on your side: the backend runs next to your OpenClaw install,
> reachable only over your own private network (Tailscale works well), and speech
> is transcribed locally with Whisper by default — no cloud STT unless you
> configure one yourself.
>
> **Open beta on TestFlight:** https://testflight.apple.com/join/nEdn2Np2
> **What it is / how it works:** https://basarlabs.com.tr/ceviz/
>
> You'll need an iPhone + Apple Watch and OpenClaw running on a machine you
> control. Backend install is one command; choose the connection that fits your
> setup — Tailscale for private access across networks, the built-in Windows
> relay for WSL2 on the same Wi-Fi, or your own VPN/reverse proxy. The installer
> prints a QR you scan in the app to pair.
>
> **Known rough edges, so nothing surprises you:**
> - The first voice command after install is slow — the backend downloads the
>   speech model on first use. Give it a few minutes, then it's fast.
> - Keep watch commands short and focused; longer voice input takes more time to
>   transcribe and is more likely to be interrupted by watchOS.
> - If you use Tailscale, turn on VPN On Demand. iOS drops the VPN in the
>   background and then the app can't reach your machine.
> - The built-in relay is for WSL2 machines on the same Wi-Fi; use Tailscale or
>   your own secure tunnel when the phone leaves that network.
> - You need OpenClaw already running on a machine you control. Without a
>   backend the app opens in demo mode with sample data — enough to see the
>   product, not to do real work.
>
> It's a beta and I'd rather hear the rough edges than the compliments — feedback
> very welcome, especially from anyone running OpenClaw on macOS or bare Linux
> (I've been developing on WSL2, so those paths are the least tested).
>
> Full disclosure: I verified the build structure, backend installation in a
> clean isolated environment, QR pairing, authenticated relay access, recovery
> after a backend interruption, and every screen. Beta 2 was also verified on a
> physical iPhone + Apple Watch: the notification arrived without opening Ceviz,
> tapping it opened the completed result, and Home reflected the terminal state.
> Independent onboarding and the macOS/bare-Linux paths still need real-world
> feedback, so if something breaks, tell me and I'll turn it around quickly.

**Notlar:**
- İlk mesajda ekran görüntüsü/kısa video paylaşmak dönüşümü ciddi artırır:
  saatte kayıt ekranı + telefonda rapor ekranı yeterli.
- Showcase'e alınırsan kart formatı şu: **@kullanıcı** • `etiketler` + 2 cümle.
  Öneri etiketler: `apple-watch` `ios` `voice` `mobile`.

---

## 2) X / Twitter (@openclaw etiketli)

> Built @openclaw into my Apple Watch.
>
> Press, speak: "is prod healthy?" — the job runs on my own machine, the summary
> comes back to my wrist, and the full report waits on my phone. Speech is
> transcribed locally; nothing goes to anyone else's server.
>
> Open beta 👇
> https://testflight.apple.com/join/nEdn2Np2

---

## 3) LinkedIn (TR)

> **Ceviz — OpenClaw'ı bileğinize taşıyan kontrol katmanı, açık betada.**
>
> Bir dağıtımın sağlıklı gidip gitmediğini öğrenmek için her seferinde bilgisayara
> dönmek zorunda kalmak canımı sıkıyordu. Ceviz bunun için: Apple Watch'a kısa bir
> komut söylüyorsunuz, iş kendi makinenizdeki OpenClaw ajanında çalışıyor, sonuç
> bileğinize tek bakışta okunacak bir özet olarak dönüyor. Derinlik gerektiğinde
> telefon devralıyor — durum, analiz, arka planda hangi alt ajanların çalıştığı ve
> önerilen sonraki adım.
>
> Teknik tarafta üzerinde en çok durduğum şey gizlilik oldu: backend kendi
> makinenizde çalışıyor ve konuşma varsayılan olarak yine kendi makinenizde
> (Whisper ile) yazıya çevriliyor. Farklı ağlardan erişim için Tailscale'i, WSL2
> ve aynı Wi-Fi senaryosu için Ceviz'in yerel Windows relay'ini ya da kendi güvenli
> tunnel altyapınızı seçebiliyorsunuz. Hiçbir içerik bizim sunucumuza uğramıyor —
> çünkü öyle bir sunucu yok.
>
> watchOS + iOS uygulaması SwiftUI ile, backend Python; dağıtım tek komutluk bir
> kurulum scripti, yönlendirmeli bağlantı seçimi ve QR ile eşleşme.
>
> TestFlight açık betası: https://testflight.apple.com/join/nEdn2Np2
> Detaylar: https://basarlabs.com.tr/ceviz/
>
> iPhone + Apple Watch'u olan ve kendi makinesinde OpenClaw çalıştıran herkes
> deneyebilir. Geri bildirime, özellikle de takıldığınız yerlere açığım.

**Not:** LinkedIn'de ilk yoruma bağlantıları koymak erişimi artırıyor; gönderi
metnindeki linkleri oraya taşımayı düşünebilirsin (acp-net duyurusunda olduğu gibi).

---

## Duyurudan önce kontrol

- [x] TestFlight public link canlı (BETA_APPROVED)
- [x] basarlabs.com.tr/ceviz/ ve /ceviz/privacy/ yayında
- [x] Kurulum scripti temiz ortamda test edildi
- [x] QR eşleşme + token korumalı relay erişimi doğrulandı
- [x] WSL2 keepalive ve backend kesintisinden toparlanma doğrulandı
- [x] Backend/contract testleri 34/34 ve TestFlight CI bariyerinde
- [x] Ekran görüntüleri hazır (5 temiz 1320×2868 JPEG; Actions artefaktı)
- [x] Beta 2 build'i fiziksel iPhone + Apple Watch'ta bildirimden sonuca kadar doğrulandı
- [x] Beta 2 build'i public external `Beta` grubuna eklendi (`BETA_APPROVED`)
- [ ] Beta'ya ilk gerçek dış kullanıcı katıldığında kurulum akışını izle (lansman sonrası, non-blocking)
