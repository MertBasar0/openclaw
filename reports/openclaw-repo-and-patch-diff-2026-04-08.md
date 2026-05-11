# OpenClaw Sürüm Farkı ve Lokal Patch Özeti

Tarih: 2026-04-08
Hazırlayan: Ceviz

## Bu dosyanın amacı

Bu dosya şu iki şeyi ayırarak anlatır:

1. **Mert’te çalışan kurulu OpenClaw sürümü** ile **GitHub’dan çekilen source repo** arasındaki saf upstream fark
2. Bu source repo üstüne **bizim ayrıca eklediğimiz lokal patch farkı**

Yani bu dosya, yalnızca bizim patch’i değil, aynı zamanda kurulu sürüm ile çekilen repo arasındaki genel farkı da açıklar.

---

## 1) Karşılaştırılan iki ana referans

### A) Mert’te çalışan kurulu OpenClaw
- Sürüm: `2026.3.24`
- Kaynak/kurulum hattı: global kurulu stable paket
- Canlı gateway bu sürüm üzerinde çalışıyor

### B) GitHub’dan çekilen source repo
- Yol: `/home/mertb/.openclaw/workspace/openclaw-src`
- HEAD: `253ecd2a5d`
- Version: `2026.4.9`
- Tag baz çizgisi: `v2026.3.24`

---

## 2) Neden bu fark ilk bakışta yanlış gibi görünebilir?

İlk anda şu şüphe oluşabiliyor:
- “çekilen repo tarihin ilerisinde görünüyor, demek ki yanlış bir checkout alındı”

Ama burada asıl gerçek şu:
- çekilen repo, çalışan stable install ile aynı sürüm değil
- daha yeni upstream durumunu temsil ediyor
- OpenClaw takvim sürümleme (calver) ve farklı timezone/commit zamanları yüzünden tarih algısı yanıltıcı olabiliyor

Yani bu tek başına hata değil.
Hata ancak yanlış karşılaştırma yapılırsa olur.

Doğru karşılaştırma şu:
- çalışan stable `2026.3.24`
ile
- source repo `2026.4.9`
aynı şey değil

Dolayısıyla aradaki fark iki parçadan oluşur:
1. upstream OpenClaw’ın doğal gelişimi
2. bizim source repo üstüne eklediğimiz lokal patch

---

## 3) Saf upstream fark: `v2026.3.24` -> `2026.4.9`

### Commit farkı
`v2026.3.24` tag’inden çekilen repo HEAD’ine kadar:
- **7096 commit** var

Bu çok büyük bir farktır.
Yani çalışan kurulu sürüm ile çekilen repo arasında yalnızca birkaç küçük değişiklik değil, ciddi bir upstream evrim var.

---

## 4) Upstream farkın kapsamı: üst düzey alanlar

Tag `v2026.3.24` ile bugünkü HEAD arasında değişim en çok şu alanlarda yoğunlaşıyor:

- `src/agents` → **998 değişim**
- `src/infra` → **452 değişim**
- `src/plugins` → **406 değişim**
- `src/commands` → **396 değişim**
- `src/gateway` → **375 değişim**
- `src/plugin-sdk` → **369 değişim**
- `src/auto-reply` → **336 değişim**
- `docs/zh-CN` → **312 değişim**
- `extensions/browser` → **260 değişim**
- `src/cli` → **258 değişim**
- `extensions/discord` → **258 değişim**
- `extensions/matrix` → **239 değişim**
- `src/config` → **238 değişim**
- `extensions/telegram` → **227 değişim**
- `ui/src` → **203 değişim**
- `src/channels` → **196 değişim**
- `extensions/slack` → **167 değişim**
- `extensions/whatsapp` → **162 değişim**
- `apps/android` → **68 değişim**
- `apps/ios` → **48 değişim**
- `apps/macos` → **27 değişim**
- `src/acp` → **38 değişim**
- `extensions/acpx` → **38 değişim**

Bu sayıların anlamı:
- kurulu `2026.3.24` ile çekilen repo arasındaki fark çok geniş
- özellikle agent, gateway, infra, plugin, auto-reply ve channel katmanlarında yoğun değişim olmuş

---

## 5) Upstream değişimlerin tematik özeti

Commit geçmişine ve değişen dosyalara bakınca, `2026.3.24` ile `2026.4.9` arasındaki saf upstream farkı kabaca şu temalara ayrılıyor:

### A) Agents / subagents / lifecycle / task katmanı
En yoğun değişim alanı burası.
Muhtemel kapsam:
- subagent davranışları
- lifecycle akışları
- task registry / task executor ilişkileri
- browser cleanup / hook / context-engine bağları
- announce / follow-up / completion yolları

Bu, bizim reliability işimizin de neden bu bölgede yoğunlaştığını açıklıyor.

### B) Infra / outbound / system davranışları
Büyük değişim var:
- outbound delivery
- approval / exec / network / runtime yardımcıları
- state / restore / policy / auth yardımcıları
- performans ve boundary refactor’ları

### C) Gateway / auto-reply / commands
Burada da ciddi fark var:
- gateway session davranışları
- queued reply / runtime snapshot / follow-up mantıkları
- command yüzeyleri
- status / auth / routing davranışları

### D) Plugin SDK / plugins / bundled extension ekosistemi
Çok büyük değişim var:
- plugin contract’ları
- provider boundary’leri
- public artifact yapıları
- bundled metadata / package sınırları
- extension release / packaging işleri

### E) Channels ve messaging yüzeyi
Birçok kanal extension’ında değişim görülüyor:
- Discord
- Matrix
- Telegram
- Slack
- WhatsApp
- Feishu
- Teams
- Mattermost vb.

Yani çalışan sürüm ile çekilen repo arasında messaging yüzeyi de ciddi biçimde değişmiş.

### F) Mobile / desktop app yüzeyi
Dikkat çeken farklar:
- Android tarafında yeni işlevler ve testler
- iOS tarafında watch / connectivity / gateway sorunları / approval prompt köprüleri
- macOS tarafında gateway/runtime/policy güncellemeleri

### G) Docs / i18n / release / CI
Belgelendirme ve release/CI hatlarında da ciddi fark var:
- docs genişlemiş
- i18n materyali artmış
- workflow’lar yenilenmiş
- release/publish süreçlerinde değişiklikler var

---

## 6) Bu fark neden önemli?

Çünkü bu bize şunu söylüyor:

- çalışan stable install ile çekilen source repo arasında yalnızca bizim yaptığımız patch yok
- çekilen repo zaten başlı başına daha yeni ve çok daha geniş bir codebase durumu temsil ediyor

Dolayısıyla:
- source repo üstünde patch yazmak,
- bunu doğrudan çalışan stable sisteme geçirmekle aynı şey değil

Bu yüzden daha önce seçilen güvenli deployment stratejisi mantıklıydı:
- önce çalışan sürüm olan `2026.3.24` ile hizalı source checkout açmak
- sonra bizim patch’i oraya port etmek
- sonra testleyip deploy etmek

---

## 7) Bizim lokal patch farkımız (upstream farkın üstüne ek olarak)

Yukarıdaki tüm farklar **upstream saf fark** idi.

Bunun üstüne bir de **bizim lokal patch’imiz** var.
Şu anda source repo içinde local diff olarak duran dosyalar:

- `src/agents/subagent-registry.types.ts`
- `src/agents/subagent-registry-lifecycle.ts`
- `src/agents/subagent-registry.test.ts`
- `src/agents/subagent-registry-lifecycle.test.ts`

Yani bizim eklediğimiz fark, 7096 commitlik upstream farkın tamamı değil;
sadece bu 4 dosyalık local patch.

---

## 8) Bizim lokal patch’in teknik özeti

### Amaç
Subagent/child completion bildirimi immediate deliver edilemediğinde:
- bu durumu lifecycle state içinde durable tutmak
- success/give-up ile temizlemek
- testle doğrulamak

### Dosya bazında ne yaptık?

#### A) `src/agents/subagent-registry.types.ts`
Eklenenler:
- `PendingFinalDeliveryPayload`
- `pendingFinalDelivery`
- `pendingFinalDeliveryCreatedAt`
- `pendingFinalDeliveryLastAttemptAt`
- `pendingFinalDeliveryAttemptCount`
- `pendingFinalDeliveryLastError`
- `pendingFinalDeliveryPayload`

#### B) `src/agents/subagent-registry-lifecycle.ts`
Eklenen davranışlar:
- deferred announce olduğunda pending state yaz
- success olduğunda temizle
- give-up finalization olduğunda temizle

#### C) `src/agents/subagent-registry.test.ts`
Eklenen doğrulama:
- deferred anda pending state gerçekten yazılıyor mu?

#### D) `src/agents/subagent-registry-lifecycle.test.ts`
Eklenen doğrulama:
- give-up olduğunda pending state gerçekten temizleniyor mu?

---

## 9) Lokal patch’in test durumu

İlgili testler geçirildi:
- `src/agents/subagent-registry-lifecycle.test.ts`
- `src/agents/subagent-registry.test.ts`

Son sonuç:
- 2 test dosyası geçti
- 15 test geçti
- 0 fail

Not:
- full monorepo-wide compile (`tsc`) OOM verdi
- bu yüzden patch full repo compile ile değil, hedefli testlerle doğrulandı

---

## 10) En kısa doğru özet

### Çalışan OpenClaw ile çekilen repo arasındaki saf fark
- çok büyük bir upstream fark var
- `v2026.3.24` -> `2026.4.9`
- yaklaşık **7096 commit**
- en çok agent, infra, gateway, plugin, auto-reply ve channels katmanları değişmiş

### Bizim ayrıca eklediğimiz lokal fark
- yalnızca 4 dosyalık patch
- durable `pendingFinalDelivery` lifecycle state
- ilgili test coverage

---

## 11) Sonuç

Bu yüzden “bendeki kurulu sürüm ile çektiğin repo arasındaki fark nedir?” sorusunun doğru cevabı şu:

1. Önce: çekilen repo zaten çok daha yeni bir upstream durum
2. Sonra: onun üstüne bizim küçük ama hedefli bir lokal reliability patch’imiz var

Yani toplam fark:
- **büyük upstream fark**
- **küçük lokal patch farkı**

Bu ayrım, patch’i live sisteme taşırken neden önce `2026.3.24` ile hizalı checkout gerektiğini de açıklıyor.

---

## Kaynaklar
- `openclaw status`
- `openclaw-src/package.json`
- `git rev-parse v2026.3.24`
- `git rev-list --count v2026.3.24..HEAD`
- `git diff --name-status v2026.3.24..HEAD`
- `git diff --name-only v2026.3.24..HEAD`
- lokal patch diff ve hedefli test sonuçları
