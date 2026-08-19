# MCP Swing İz Kontrolü

Bu modül, yapay zekâ istemcisinin kontrollü bir Java Swing ekranındaki iz değerlerini
Model Context Protocol (MCP) araçlarıyla okuyup değiştirebildiğini gösteren yerel bir
demonstrasyondur. Gerçek sistem veya şirket verisi kullanmaz.

## Alanlar

- Hız: `0–100` knot
- Yön: `0–360` derece
- İz/gemi tipi: kontrollü `JComboBox` listesi

## MCP araçları

| Araç | İşlev |
|---|---|
| `get_application_status` | Açık Swing uygulamasını ve süreç kimliğini denetler. |
| `open_track_application` | Uygulama kapalıysa açar; açıksa ikinci pencere oluşturmaz. |
| `close_track_application` | Açık uygulamayı kontrollü biçimde kapatır. |
| `get_track_state` | Tüm iz durumunu okur. |
| `get_write_policy` | Operatörün MCP yazma iznini okur. |
| `get_change_history` | Son değişiklikleri kaynak ve zaman bilgisiyle okur. |
| `get_speed` / `set_speed` | Hızı okur veya günceller. |
| `get_heading` / `set_heading` | Yönü okur veya günceller. |
| `get_ship_type` / `set_ship_type` | Gemi tipini okur veya günceller. |
| `set_track_state` | Üç alanı tek atomik işlemle günceller. |

Arayüzdeki **MCP / model yazma izni** seçimi kapatıldığında bütün `set_*`
araçları güvenli biçimde reddedilir; `get_*` araçları çalışmaya devam eder. İşlem
geçmişi, son 100 operatör veya MCP güncellemesini kaynak ve değişiklik özetiyle
ekranda gösterir.

## Derleme ve çalıştırma

Windows terminalinde önce derleyin:

```powershell
cd mcp-swing-demo
.\mvnw.cmd clean verify
```

Track/Swing arayüzünü modelden önce elle açmak için:

```powershell
java -jar target\mcp-swing-demo.jar --ui-only
```

Codex tarafından STDIO MCP köprüsü olarak çalıştırmak için:

```powershell
java -jar target\mcp-swing-demo.jar --server-only
```

Argümansız çalıştırma da STDIO MCP köprüsü kipidir. Köprü yeni pencere açmaz; mevcut
Swing sürecini yerel loopback bağlantısından bulur. Bir `set_*` çağrısında uygulama
kapalıysa sonuçta açık geri bildirim döndürür, tek Swing örneğini başlatır ve ilk
komutu bu örneğe uygulayıp geri okur.

MCP istemcisi sunucuyu `java -jar <tam-yol>\mcp-swing-demo.jar --server-only`
komutuyla başlatmalıdır.
STDOUT MCP protokolüne ayrıldığı için uygulama tanılama mesajlarını STDERR'a yazar.
