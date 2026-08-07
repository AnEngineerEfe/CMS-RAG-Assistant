# MCP Swing İz Kontrolü · Teknik Rehber

## Amaç ve kapsam

Bu demonstrasyon, bir yapay zekâ istemcisinin Java Swing ile hazırlanmış kontrollü
bir iz ekranını Model Context Protocol üzerinden okuyup güncelleyebildiğini kanıtlar.
Gerçek savaş yönetim sistemine bağlanmaz; şirket verisi, operasyon verisi, ağ erişimi
ve genel amaçlı komut çalıştırma yeteneği içermez.

## Mimari

```text
Model / MCP istemcisi
        │ STDIO · JSON-RPC
        ▼
TrackMcpServer (infrastructure)
        │ yalnız izinli komutlar
        ▼
TrackCommandFacade (application)
        ▼
TrackStateService (application)
        ├── kaynaklı değişiklik geçmişi
        ├── operatör MCP yazma kilidi
        ▼
TrackState + ShipType (domain)
        ▲
        │ Swing olayları ve durum bildirimleri
TrackControlFrame (presentation)
```

MCP ile Swing aynı `TrackStateService` örneğini paylaşır. MCP aracı bir değeri
değiştirdiğinde Swing bileşenleri Event Dispatch Thread üzerinde yenilenir. Operatör
`Değerleri Uygula` düğmesine bastığında değişiklik aynı doğrulama katmanından geçer
ve sonraki MCP `get` çağrısında görünür.

## Veri sözleşmesi

| Alan | Tip | Sınır |
|---|---|---|
| `speedKnots` | Ondalıklı sayı | 0–100 knot |
| `headingDegrees` | Tam sayı | 0–360 derece |
| `shipType` | Enum | Tanımlı sekiz sınıftan biri |

Gemi tipi değerleri: `BELIRSIZ`, `FIRKATEYN`, `KORVET`, `MUHRIP`, `DENIZALTI`,
`HUCUMBOT`, `TICARI_GEMI`, `YARDIMCI_GEMI`.

## Araç kataloğu

| Araç | Girdi | Sonuç |
|---|---|---|
| `get_track_state` | Yok | Üç alanın tamamı |
| `get_write_policy` | Yok | MCP yazma izni ve politika durumu |
| `get_change_history` | Yok | Son değişikliklerin kaynaklı audit listesi |
| `get_speed` | Yok | Mevcut hız |
| `set_speed` | `speedKnots` | Güncellenmiş durum |
| `get_heading` | Yok | Mevcut yön |
| `set_heading` | `headingDegrees` | Güncellenmiş durum |
| `get_ship_type` | Yok | Gemi tipi kodu ve etiketi |
| `set_ship_type` | `shipType` | Güncellenmiş durum |
| `set_track_state` | Üç alan | Atomik güncellenmiş durum |

Araç girdileri hem MCP JSON Schema doğrulamasından hem alan modeli kurallarından
geçer. Örneğin `361` derecelik yön, iş mantığına ulaşmadan MCP hata sonucu üretir.
Arayüzdeki yazma izni kapatıldığında `set_*` araçları uygulama katmanında da
reddedilir. Bu kilit model tarafından değiştirilemez; yalnız operatör kontrolündedir.

## Canlı işlem geçmişi

Her başarılı değişiklik sıra numarası, UTC zaman damgası, kaynak (`OPERATOR` veya
`MCP`), önceki durum ve sonraki durumla bellekte kaydedilir. Swing tablosu değişen
alanların okunabilir özetini gösterir. `get_change_history` aynı kanıtı MCP istemcisine
geri verir. Bellek sınırı son 100 olaydır ve uygulama kapandığında kayıtlar silinir.

## Derleme ve çalıştırma

Gereksinim: Java 21 JDK. Global Maven kurulumu gerekmez; sürümlü Maven Wrapper
ilk çalıştırmada Maven 3.9.11'i indirir.

```powershell
cd mcp-swing-demo
.\mvnw.cmd clean verify
java -jar target\mcp-swing-demo.jar
```

Çalışma kipleri:

```powershell
# Yalnız Swing ekranı
java -jar target\mcp-swing-demo.jar --ui-only

# Yalnız STDIO MCP sunucusu
java -jar target\mcp-swing-demo.jar --server-only
```

## MCP istemci tanımı

STDIO destekleyen bir MCP istemcisinde sunucu komutu aşağıdaki mantıkla tanımlanır:

```json
{
  "command": "C:\\Program Files\\Eclipse Adoptium\\jdk-21.0.12.8-hotspot\\bin\\java.exe",
  "args": [
    "-jar",
    "C:\\Users\\HP\\Desktop\\CMS-RAG-Assistant\\mcp-swing-demo\\target\\mcp-swing-demo.jar"
  ]
}
```

MCP istemcisinin tam yapılandırma anahtarları kullandığı ürüne göre değişebilir;
komut ve argüman sözleşmesi değişmez. STDOUT protokole ayrılmıştır, uygulama
tanılama kayıtlarını STDERR'a yazar.

## Test kanıtı

`mvnw.cmd clean verify` aşağıdakileri otomatik sınar:

1. Alan sınırları ve geçersiz değerlerin durumu değiştirmemesi.
2. Atomik üç alan güncellemesi ve dinleyici bildirimi.
3. MCP biçimindeki girdilerin alan modeline dönüştürülmesi.
4. Gerçek alt Java süreci üzerinden STDIO bağlantısı ve MCP başlangıç anlaşması.
5. On aracın keşfi, `set_track_state` yazma ve `get_track_state` geri okuma.
6. MCP değişikliğinin kaynaklı işlem geçmişinde görünmesi.
7. Operatör kilidi kapalıyken MCP yazmasının reddedilmesi ve operatör yazmasının sürmesi.
8. Şema dışı `361` derece yön çağrısının hata olarak reddedilmesi.

## Güvenlik sınırı

- MCP sunucusu yalnız on sabit aracı sunar.
- Dosya sistemi, kabuk, veritabanı ve ağ aracı yoktur.
- Girdiler kapalı JSON Schema ile doğrulanır; ek alanlara izin verilmez.
- Model yazma yetkisi arayüzden anında kilitlenebilir; okuma yetkisi korunur.
- Durum yalnız süreç belleğinde tutulur ve uygulama kapanınca silinir.
- Bu demonstrasyon operasyonel karar veya gerçek platform kontrolü için değildir.
