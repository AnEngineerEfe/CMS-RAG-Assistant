# CMS-RAG Asistanı · MCP Swing Entegrasyonu

## Amaç

Bu entegrasyon, mevcut kanıta dayalı RAG sohbetini bozmadan aynı arayüzden yerel
Swing iz durumunu okumayı ve operatör onayıyla değiştirmeyi sağlar. Codex çalışma
zamanı bağımlılığı değildir. Streamlit uygulaması kendi MCP istemcisini içerir ve
Java sunucusunu ihtiyaç olduğunda yerel alt süreç olarak başlatır.

## Çalışma akışı

```text
Kullanıcı iletisi
  -> güvenli niyet ayrımı
     -> CMS bilgi sorusu: mevcut RAG ve kaynak gösterimi
     -> canlı iz okuma: MCP get_track_state
     -> iz yazma: işlem planı -> kullanıcı onayı -> izin kontrolü
        -> set_track_state -> get_track_state ile geri-okuma doğrulaması
```

Model veya kullanıcı metni Swing bileşenlerine, Java private alanlarına ya da
genel amaçlı bir komut çalıştırıcıya ulaşmaz. Yalnız geliştirici tarafından
tanımlanan kapalı MCP araç sözleşmesi kullanılır. Swing ve MCP aynı Java
`TrackStateService` örneğini paylaşır; ekran servis değişikliğini dinleyerek
kendini yeniler.

## Güvenlik kararları

- Genel CMS soruları MCP kanalına yönlendirilmez.
- Belirsiz komutlar çalıştırılmaz; kullanıcıdan açık değer istenir.
- Birleşik komutta bir alan geçersizse uygun alanlar ayrı bir işlem planına alınır;
  sorunlu alanın korunacağı açıkça gösterilir ve geçerli alt küme de kullanıcı
  onayı olmadan uygulanmaz.
- Küçük gemi tipi yazım hatalarında en yakın izinli değer yalnız önerilir; kullanıcı
  onayı veya düzeltilmiş yeni komut olmadan otomatik tipe dönüştürülmez.
- Negatif veya 360'tan büyük tam sayı yönler döngüsel esas açıya çevrilir
  (`-10° → 350°`, `370° → 10°`) ve dönüşüm onay ekranında gösterilir.
- Yazma isteği onaydan önce yalnız bir işlem planıdır ve yan etkisi yoktur.
- Onay beklerken canlı durum değişirse eski plan iptal edilir.
- Operatörün Swing ekranındaki yazma kilidi her işlemde yeniden okunur.
- Hız `0–100`, yön `0–360`; gemi tipi kapalı enum listesidir.
- Güncelleme üç alanı tek atomik `set_track_state` çağrısıyla uygular.
- Başarı ancak yazma sonucu ve sonraki geri-okuma hedefle aynıysa bildirilir.
- Audit kaydı serbest kullanıcı metnini değil yalnız sonucu ve önce/sonra
  değerlerini `data/audit/mcp_events.jsonl` altında saklar.
- Java MCP sunucusunda dosya sistemi, kabuk, ağ veya veritabanı aracı yoktur.

## Örnek istekler

```text
İz durumunu göster.
Mevcut hız kaç?
Hızı 24,5 knot yap.
Yönü 270 derece yap.
Gemi tipini fırkateyn yap.
İzin hızını 24,5 knot, yönünü 270 derece ve tipini fırkateyn yap.
Yönü -10 derece yap.
```

Yazma isteklerinde asistan önce değişiklik özetini gösterir. Kullanıcı
`Onayla ve uygula` düğmesine basmadıkça MCP yazma aracı çağrılmaz.
Birleşik komutun yalnız bir bölümü geçerliyse düğme `Geçerli değişiklikleri uygula`
olarak görünür ve uygulanmayacak alanlar ayrıca listelenir.

## Kurulum ve çalıştırma

Gereksinimler Python ortamına ek olarak Java 21 JDK'dır. Java modülü temiz
kurulumda bir kez derlenmelidir:

```powershell
cd mcp-swing-demo
.\mvnw.cmd clean verify
cd ..
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Alternatif olarak kök dizinde aşağıdaki yardımcı komut jar yoksa modülü derler
ve Streamlit uygulamasını açar:

```powershell
.\scripts\run_local.ps1
```

İlk canlı iz isteğinde Swing penceresi açılır. Pencere kapatılırsa Java süreci de
kapanır; sonraki istekte yeni bir süreç başlangıç değerleriyle açılır.

## Taşıma ve ölçek sınırı

Mevcut sürüm tek kullanıcı/tek bilgisayar demonstrasyonu için yerel `STDIO`
kullanır. Böylece ağ portu açılmaz ve Streamlit ile Swing aynı Java sürecinde aynı
durumu paylaşır. Birden fazla kullanıcı veya bilgisayar aynı duruma erişecekse
sonraki sürümde ortak MCP HTTP taşıması, TLS, kimlik doğrulama, rol tabanlı yetki,
kalıcı durum ve merkezi audit eklenmelidir. Yerel STDIO demonstrasyonu bu ağ
özelliklerini varmış gibi iddia etmez.

## Test kapsamı

- Türkçe komut ve canlı okuma niyeti ayrımı
- Genel CMS sorularının RAG kanalında kalması
- Alan sınırı ve enum doğrulaması
- Onaysız yazma yapılmaması
- Operatör kilidinde okumanın sürmesi ve yazmanın reddedilmesi
- Onay beklerken değişen durumun iptali
- Gerçek Python–Java STDIO MCP başlatma, yazma, geri okuma ve geçmiş testi
- Streamlit onay düğmesi üzerinden tek atomik yazma
- Audit kaydında serbest kullanıcı metni bulunmaması
