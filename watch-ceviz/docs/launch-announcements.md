# Lansman duyuruları — hazır metinler

Sıra önerisi: **1) OpenClaw Discord `#self-promotion` → 2) X (@openclaw etiketli) → 3) LinkedIn.**
Discord ilk sırada çünkü hedef kitle tam orada (zaten kendi makinesinde ajan
çalıştıran insanlar) ve OpenClaw'ın resmi showcase sayfası açıkça oradan
paylaşmaya davet ediyor — showcase'e alınmanın yolu bu.

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
> control. Backend install is one command; it prints a QR you scan in the app to
> pair.
>
> It's a beta and I'd rather hear the rough edges than the compliments — feedback
> very welcome, especially from anyone running OpenClaw on macOS or bare Linux
> (I've been developing on WSL2).

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
> makinenizde çalışıyor, yalnızca kendi özel ağınızdan erişiliyor ve konuşma
> varsayılan olarak yine kendi makinenizde (Whisper ile) yazıya çevriliyor.
> Hiçbir içerik bizim sunucumuza uğramıyor — çünkü öyle bir sunucu yok.
>
> watchOS + iOS uygulaması SwiftUI ile, backend Python; dağıtım tek komutluk bir
> kurulum scripti ve QR ile eşleşme.
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
- [ ] Ekran görüntüleri hazır (Discord/LinkedIn görseli için)
- [ ] Beta'ya ilk gerçek dış kullanıcı katıldığında kurulum akışını izle
