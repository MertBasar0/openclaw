# App Store Connect — hazır metinler

Bu dosyadaki blokları App Store Connect'e olduğu gibi yapıştırabilirsin.
İngilizce olanlar birincil (App Review İngilizce okur), Türkçe karşılıkları
`Türkçe (Turkey)` yerelleştirmesi için.

---

## 1) App Review Information → Notes

> Ceviz is a control surface for OpenClaw, an AI agent that runs on the user's
> own computer. The Apple Watch app captures a short voice command, the iPhone
> app forwards it to the user's self-hosted backend over their own private
> network, and the result comes back as a short wrist summary plus a fuller
> report on the phone.
>
> IMPORTANT FOR REVIEW: that backend runs on the user's personal machine and is
> only reachable from their own private network, so it is not reachable from
> outside. For this reason the app ships with a built-in Demo Mode.
>
> Demo Mode turns on automatically on a fresh install — no account, no login, no
> credentials, and no server setup are required. Every screen is populated with
> sample data, and a "DEMO" badge is shown in the top bar. You can also toggle it
> manually in Settings (gear icon on the home screen).
>
> What you can review in Demo Mode:
> - Home screen with recent jobs
> - Job report screen: status, summary, analysis sections, subagents/tools
> - Job chain navigation (the first sample job is part of a 2-job chain)
> - Settings, including the QR pairing screen
> - Apple Watch app: jobs list and job detail, if you test on a paired watch
>
> The microphone permission is used only to record a voice command that is sent
> to the user's own backend. The camera permission is used only to scan the
> pairing QR code that the user's own install script prints. In Demo Mode
> neither is required to review the app.
>
> Contact: mertbasar0@hotmail.com

**Türkçe (gerekirse):**

> Ceviz, kullanıcının kendi bilgisayarında çalışan OpenClaw adlı yapay zekâ
> ajanı için bir kontrol yüzeyidir. Apple Watch uygulaması kısa bir sesli komut
> alır, iPhone uygulaması bunu kullanıcının kendi özel ağı üzerinden kendi
> sunucusuna iletir; sonuç bilekte kısa bir özet, telefonda ise ayrıntılı bir
> rapor olarak döner.
>
> İNCELEME İÇİN ÖNEMLİ: bu sunucu kullanıcının kişisel makinesinde çalışır ve
> yalnızca kendi özel ağından erişilebilir; dışarıdan erişilemez. Bu nedenle
> uygulama yerleşik bir Demo Modu ile gelir.
>
> Demo Modu taze kurulumda kendiliğinden açılır — hesap, giriş, kimlik bilgisi
> veya sunucu kurulumu gerekmez. Tüm ekranlar örnek veriyle dolar ve üst barda
> "DEMO" rozeti görünür. Ayarlar'dan (ana ekrandaki dişli) elle de açılıp
> kapatılabilir.

---

## 2) TestFlight → Test Information → Beta App Description

**English:**

> Ceviz puts your OpenClaw agent on your wrist. Start a job by speaking to your
> Apple Watch, see a short summary at a glance, and continue on your iPhone when
> you need the full report, the logs, or the next action.
>
> Built for developers and operators who run agents on their own machine: deploy
> checks, pull request summaries, incident triage. Your commands go to your own
> self-hosted backend over your own private network — nothing runs on our
> servers.
>
> New to the app? It opens in Demo Mode with sample data, so you can see how it
> works before connecting your own machine.

**Türkçe:**

> Ceviz, OpenClaw ajanını bileğine taşır. Apple Watch'a konuşarak bir iş başlat,
> özeti tek bakışta gör, ayrıntılı rapora veya sonraki adıma ihtiyaç duyduğunda
> iPhone'dan devam et.
>
> Kendi makinesinde ajan çalıştıran geliştiriciler ve operatörler için: deploy
> kontrolleri, pull request özetleri, olay müdahalesi. Komutların kendi özel ağın
> üzerinden kendi sunucuna gider — hiçbir şey bizim sunucularımızda çalışmaz.
>
> Uygulamayı ilk kez mi açıyorsun? Demo Modu ile örnek veri üzerinden nasıl
> çalıştığını görebilir, sonra kendi makineni bağlayabilirsin.

---

## 3) TestFlight → What to Test

**English:**

> 1. Open the app — it starts in Demo Mode with sample data (DEMO badge in the
>    top bar).
> 2. Tap a job in RECENT JOBS to open its report: status chip, watch summary,
>    analysis, subagents and next actions.
> 3. On the deploy job, use the CHAIN bar to move between the two linked jobs.
> 4. Open Settings (gear) to see pairing: QR scan, server URL and access token.
> 5. If you run OpenClaw yourself: run deploy/install.sh on that machine, scan
>    the printed QR, then send a real voice command from the watch.
>
> Please report anything that feels slow, unclear, or stuck — especially cases
> where the watch shows no result after a command.

**Türkçe:**

> 1. Uygulamayı aç — Demo Modu ile örnek veri gelir (üst barda DEMO rozeti).
> 2. SON İŞLER'den bir işe dokun: durum çipi, saat özeti, analiz, alt ajanlar ve
>    sonraki aksiyonlar.
> 3. Deploy işinde ZİNCİR çubuğuyla bağlı iki iş arasında gezin.
> 4. Ayarlar'ı (dişli) aç: QR ile eşleşme, sunucu adresi ve erişim token'ı.
> 5. OpenClaw'ı kendin çalıştırıyorsan: o makinede deploy/install.sh çalıştır,
>    basılan QR'ı okut, sonra saatten gerçek bir sesli komut gönder.
>
> Yavaş, belirsiz ya da takılan her şeyi bildir — özellikle komut sonrası saatte
> sonuç görünmeyen durumları.

---

## 4) Gizlilik Politikası (taslak — yayınlanması gerekiyor)

App Store Connect **Privacy Policy URL** alanı zorunlu; şu an `example.com`
yazıyor. Aşağıdaki metni `basarlabs.com.tr/ceviz/privacy` gibi bir adrese koy.

> ### Ceviz — Privacy Policy
>
> Ceviz does not collect, store, or transmit personal data to us. We operate no
> servers that receive your content.
>
> **What the app sends, and where.** When you record a voice command on your
> Apple Watch, the audio is passed to the paired iPhone and forwarded to the
> backend you configured — a server you run on your own machine, reachable only
> over your own private network. Your voice recordings, transcripts, job results
> and reports stay between your devices and your machine.
>
> **Speech recognition.** By default, speech is transcribed locally on your own
> machine. A third-party speech service is used only if you explicitly configure
> one with your own API key.
>
> **What is stored on the device.** The server address you enter is stored in the
> app's local settings. The access token is stored in the iOS Keychain. Neither
> is sent anywhere except to the backend you configured.
>
> **Permissions.** The microphone is used only to record voice commands you
> start. The camera is used only to scan the pairing QR code shown by your own
> install script.
>
> **Analytics.** The app contains no analytics, advertising, or tracking SDKs.
>
> **Demo Mode.** With no backend configured, the app shows built-in sample data
> and makes no network requests for content.
>
> **Contact:** mertbasar0@hotmail.com

**Türkçe:**

> ### Ceviz — Gizlilik Politikası
>
> Ceviz, kişisel verilerinizi toplamaz, saklamaz ve bize iletmez. İçeriğinizi
> alan herhangi bir sunucu işletmiyoruz.
>
> **Uygulama ne gönderir, nereye.** Apple Watch'ta bir sesli komut
> kaydettiğinizde ses, eşli iPhone'a aktarılır ve yapılandırdığınız sunucuya
> iletilir — bu sunucu kendi makinenizde çalışır ve yalnızca kendi özel ağınızdan
> erişilebilir. Ses kayıtlarınız, transkriptleriniz, iş sonuçlarınız ve
> raporlarınız cihazlarınızla makineniz arasında kalır.
>
> **Konuşma tanıma.** Varsayılan olarak konuşma kendi makinenizde çözülür.
> Üçüncü taraf bir konuşma servisi yalnızca kendi API anahtarınızla açıkça
> yapılandırırsanız kullanılır.
>
> **Cihazda ne saklanır.** Girdiğiniz sunucu adresi uygulamanın yerel
> ayarlarında, erişim token'ı ise iOS Keychain'de saklanır. İkisi de
> yapılandırdığınız sunucu dışında hiçbir yere gönderilmez.
>
> **İzinler.** Mikrofon yalnızca sizin başlattığınız sesli komutları kaydetmek
> için, kamera yalnızca kendi kurulum scriptinizin gösterdiği eşleşme QR kodunu
> okumak için kullanılır.
>
> **Analitik.** Uygulamada analitik, reklam veya izleme SDK'sı yoktur.
>
> **Demo Modu.** Yapılandırılmış bir sunucu yokken uygulama yerleşik örnek
> veriyi gösterir ve içerik için ağ isteği yapmaz.
>
> **İletişim:** mertbasar0@hotmail.com

---

## 5) App Privacy (App Store Connect anketi) — önerilen cevaplar

- **Data Collection:** "No, we do not collect data from this app."
  Gerekçe: uygulama veriyi yalnızca kullanıcının kendi sunucusuna iletir;
  geliştirici olarak hiçbir veri toplamıyoruz ve üçüncü taraf SDK yok.

Apple ses/kamera izinlerini ayrıca sorabilir; ikisi de kullanıcı tarafından
başlatılan işlevler için ve cihaz dışına yalnızca kullanıcının kendi sunucusuna
gider.

---

## 6) Kontrol listesi (App Review'a girmeden)

- [ ] Privacy Policy URL gerçek bir sayfaya işaret ediyor (`example.com` değil)
- [ ] Marketing URL ya gerçek ya boş
- [ ] Beta App Description dolduruldu (yukarıdaki metin)
- [ ] What to Test dolduruldu (EN + TR)
- [ ] App Review Notes'a Demo Modu açıklaması eklendi
- [ ] Test Information'daki iletişim bilgileri güncel
- [ ] En son build (Demo Modu içeren) external gruba eklendi
