# OpenClaw Çalışma Özeti

Tarih: 2026-04-08
Hazırlayan: Ceviz

## Bu dosyanın amacı

Bu özet, Mert ile OpenClaw üzerinde şimdiye kadar yaptığımız çalışmaları bir araya getirir. Özellikle:
- çalışma tarzı ve davranış kararları
- Windows bridge / executor hattı
- mail/Graph tarafı
- yeni ürün yönü (CAD/BIM copilot benzeri yaklaşım)
- gateway follow-up reliability problemi
- SketchUp PoC ve Watch Ceviz paralel track’leri
- bugün yapılan source patch ve test çalışmaları

---

## 1) Çalışma tarzı ve davranış kararları

Zaman içinde netleşen en önemli çalışma kuralı şu oldu:

- ACP/subagent işi verdiğimizde, kullanıcı ara durum istemediyse erken mesajla turn kapatılmayacak.
- Mümkün olan her durumda child işin bitmesi beklenecek.
- Sonuçlar tek final mesajda dönecek.
- “sen sonra sor / bekliyor” tarzı kullanıcıya top atan akışlardan kaçınılacak.

Buna ek olarak bir başka önemli operasyonel karar da netleşti:

- webchat/direct gibi thread-bound ACP oturumu desteklemeyen yüzeylerde auto completion event’e güvenmek zayıf kalabiliyor.
- bu nedenle child session history’sini explicit takip edip sonucu synthesize ederek final dönmek daha güvenilir bir yöntem olarak benimsendi.

---

## 2) Windows bridge / executor hattı

Mert’in tercih ettiği model doğrultusunda şu mimari benimsendi:

- Ceviz: orchestrator / registrator
- Windows tarafı: ayrı executor / uygulayıcı lane

Temel teknik yön:
- Linux/WSL: planlama, workspace işleri, orkestrasyon
- Windows-capable lane: `cmd.exe`, `pwsh.exe`, `dotnet.exe`, browser launch, Windows-side artifact üretimi

Önemli bulgu:
- sorun genel olarak “Windows interop bozuk” değildi
- execution lane’e göre davranış değişiyordu

Tamamlanan ana aşamalar:
- Windows bridge bootstrap Phase 1
- capability probe
- queue skeleton
- queue-driven helper runner
- WSL enqueue/wait wrapper
- tek komutluk request/response bridge

Sonuç:
- Windows ile kontrollü request/response temelli bir çalışma hattı kuruldu ve doğrulandı.

---

## 3) Mail / Microsoft Graph tarafı

Başlangıçta Outlook COM yönü denendi ama bu makinede uygun olmadığı görüldü.

Bunun üzerine yön değiştirildi:
- Microsoft Graph PowerShell yerine
- MSAL + doğrudan Graph REST yaklaşımı benimsendi

Doğrulananlar:
- MSAL device flow ile login alındı
- `mertbasar0@hotmail.com` hesabında başarılı auth yapıldı
- Graph REST ile mailbox taraması çalıştı
- paging ile ~5000 mail / 25 sayfa derin tarama yapıldı

Öne çıkan örnek kayıtlar:
- Wipro recruiter outreach
- KoçDigital application link
- Turkish Technology süreç mailleri

---

## 4) Ürün yönü: CAD/BIM copilot benzeri yapı

Çalışma sırasında ürün yönü şu tarafa evrildi:

- mimarlık/mühendislik çizim programları kullanan profesyoneller için yardımcı asistan
- CAD/BIM copilot benzeri yapı

Doğru başlangıç yaklaşımı olarak şu noktada hizalanıldı:
- önce read-only analiz + öneri
- sonra onaylı düzenleme

Muhtemel mimari:
- plugin/add-in
- local Windows bridge / executor
- Ceviz orchestrator
- rules / approval layer

---

## 5) Gateway follow-up reliability problemi

Bu, son günlerdeki en önemli teknik odak haline geldi.

### Sorun nasıl tanımlandı?

Önce problem davranışsal görünüyordu:
- child/subagent işi bitince final kullanıcı bildirimi bazen kaçıyordu
- erken kapanma veya reconnect sonrası sonuç kaybı yaşanabiliyordu

Daha sonra bunun sadece davranışsal değil, altyapısal bir güvenilirlik problemi olduğu netleşti.

### Ana teknik bulgu

Şu nokta kritik olarak tespit edildi:
- child completion ve WhatsApp reconnect/disconnect gibi olaylar sistemde biliniyor
- ama final kullanıcı bildirimi yeterince durable / parent-owned değil
- system event hattı ephemeral kalabiliyor

Yani:
- bilgi sistemde kısa süre biliniyor olabilir
- ama güvenilir final delivery garantisi oluşmuyor

### Hedef mimari yön

Bu yüzden çözüm yönü şu olarak netleşti:
- ephemeral system event yerine
- durable, parent-owned `pending completion delivery` / follow-up obligation

Yani child iş bittiğinde:
- requester session için kalıcı bir final delivery state oluşmalı
- immediate teslim mümkünse gönderilmeli
- değilse reconnect / uygun ilk anda retry ile yeniden denenmeli

---

## 6) İlk transient patch denemesi

Memory kayıtlarına göre 2026-04-07 civarında ilk patch denemesi transient bir checkout üzerinde başlamıştı:
- `/tmp/openclaw-src/src/agents/subagent-final-delivery.ts`
- `/tmp/openclaw-src/src/agents/subagent-registry-lifecycle.ts`

Ama bu checkout kalıcı değildi ve daha sonra kayboldu.

Sonuç:
- tarihsel iz var
- ama exact artifact elde kalmadı

---

## 7) Kalıcı source checkout ve bugünkü patch çalışması

Daha sonra GitHub’dan kalıcı bir source checkout açıldı:
- `/home/mertb/.openclaw/workspace/openclaw-src`

Bu repo üzerinde follow-up reliability için gerçek patch çalışması yeniden kuruldu.

### Patch’in odak dosyaları

Son durumda bizim local patch’imiz şu dosyalarda toplandı:
- `src/agents/subagent-registry.types.ts`
- `src/agents/subagent-registry-lifecycle.ts`
- `src/agents/subagent-registry.test.ts`
- `src/agents/subagent-registry-lifecycle.test.ts`

### Patch’in yaptığı şey

#### A) Yeni durable state
`SubagentRunRecord` üstüne şu alanlar eklendi:
- `pendingFinalDelivery`
- `pendingFinalDeliveryCreatedAt`
- `pendingFinalDeliveryLastAttemptAt`
- `pendingFinalDeliveryAttemptCount`
- `pendingFinalDeliveryLastError`
- `pendingFinalDeliveryPayload`

Ayrıca yeni tip:
- `PendingFinalDeliveryPayload`

Bu payload içinde retry için gerekli minimum state tutuluyor:
- requester session/origin/display key
- child session/run
- task/label
- outcome
- frozen result
- fallback result
- startedAt / endedAt
- expectsCompletionMessage / spawnMode / wakeOnDescendantSettle

#### B) Lifecycle tarafındaki davranış
`subagent-registry-lifecycle.ts` içinde:
- announce başarılıysa pending state temizleniyor
- deferred/fail durumunda pending state yazılıyor
- give-up cleanup olduğunda state temizleniyor

Yani artık deferred completion delivery bilgisi ephemeral kalmıyor; run üstünde açık şekilde iz bırakıyor.

### Test ve düzeltme turu

İlk test koşusunda bir semantik hata bulundu:
- registry tarafında eklenen ilk retry yaklaşımı mevcut retry/backoff davranışını erkenden bozuyordu

Bu düzeltildi.

Son durumda testler:
- `src/agents/subagent-registry-lifecycle.test.ts`
- `src/agents/subagent-registry.test.ts`
üzerinde geçti.

Ayrıca yeni test coverage ile şu davranışlar da doğrulandı:
- deferred announce sonrası pending final delivery state gerçekten yazılıyor
- give-up finalization sırasında pending state temizleniyor

Not:
- full repo-wide `tsc` OOM verdiği için tam monorepo compile doğrulaması tamamlanamadı
- ama ilgili patch alanı testlerle doğrulandı

---

## 8) Çalışan sistem ile patch’in durumu

Önemli operasyonel ayrım:

- çalışan gateway sürümü: `2026.3.24`
- patch çalışılan source repo sürümü: `2026.4.9`

Dolayısıyla patch şu anda:
- source repo içinde uygulanmış durumda
- testlenmiş durumda
- ama çalışan global OpenClaw install’ine henüz deploy edilmedi

Yani patch şu an:
- source-level / commit-ready
- live/runtime’a uygulanmış değil

---

## 9) SketchUp PoC paralel track’i

Bu track paralelde ilerletildi.

### A4
`liveModelHeader` yüzeyi eklendi:
- `modelTitle`
- `modelPath`
- `modelGuid`
- `requestedDocumentMatched`
- `sourceKind`
- `stats` (`entityCount`, `sceneCount`, `selectionCount`)

Amaç:
- traversal/full snapshot iddiasına girmeden
- dürüst, küçük, read-only canlı metadata yüzeyi vermek

### A5
`header inspect command` eklendi:
- helper script
- inspect output
- sample payload/response
- demo script flag’leri

Amaç:
- `liveModelHeader` sadece artifact içinde kalmasın
- okunabilir, çağrılabilir bir inspect yüzeyine bağlansın

### A6
Sonraki turda `header diagnostic summary` istendi ve subagent’a dağıtıldı.

Beklenen/çıkan yön:
- doğru doküman mı?
- canlı erişim kanıtı var mı?
- sadece process metadata mı?
- bootstrap ack var ama snapshot yok mu?
- neden/uyarı özeti

Bu, inspect yüzeyini daha açıklayıcı hale getirme yönü.

---

## 10) Watch Ceviz paralel track’i

Bu track de paralelde ilerletildi.

### Phase 4
Phone Handoff thin package:
- `handoff_url`
- `requires_phone_handoff`
- `job_id`
- watch → phone handoff affordance

### Phase 5
iOS Companion deep-link consumer + minimal Job Detail screen:
- `ceviz://job/<id>/report` parse
- route state
- minimal detail screen
- simulator log akışı

### Phase 6
Backend report endpoint + iOS fetch/render thin package dağıtıldı:
- `GET /api/v1/jobs/:id/report`
- JSON response contract
- iOS fetch/render (loading/error/success)
- simulator/README güncellemesi

Bu çizgi, mock detail ekrandan gerçek thin-client davranışına geçiş olarak ilerledi.

---

## 11) Genel sonuç

Şu ana kadar en önemli teknik kazanımlar:

1. Windows bridge/executor hattı kurulup doğrulandı.
2. Graph REST + MSAL ile mail erişimi çalıştırıldı.
3. Ürün yönü CAD/BIM copilot benzeri yapıya çevrildi.
4. Gateway follow-up reliability problemi sadece davranışsal değil, yapısal olarak yeniden tanımlandı.
5. Bu problem için source repo üzerinde durable `pendingFinalDelivery` tabanlı minimum patch yazıldı.
6. Patch ilgili testlerle doğrulandı ama live sisteme henüz deploy edilmedi.
7. SketchUp PoC ve Watch Ceviz paralel track’lerinde küçük, dürüst, incremental paketlerle ilerleme sağlandı.

---

## 12) Sonraki mantıklı adımlar

1. Çalışan sürüm olan `2026.3.24` ile hizalı source checkout açmak
2. Bugünkü patch’i o sürüme port etmek
3. Aynı testleri orada çalıştırmak
4. Deploy/cutover planını netleştirmek
5. Daha sonra live gateway’ye uygulamak

---

## Kaynaklar

Bu özet şu kayıtlara dayanır:
- `MEMORY.md`
- `memory/2026-04-07.md`
- bugünkü source diff ve test sonuçları
- OpenClaw status çıktısı
