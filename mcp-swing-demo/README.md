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
| `get_track_state` | Tüm iz durumunu okur. |
| `get_speed` / `set_speed` | Hızı okur veya günceller. |
| `get_heading` / `set_heading` | Yönü okur veya günceller. |
| `get_ship_type` / `set_ship_type` | Gemi tipini okur veya günceller. |
| `set_track_state` | Üç alanı tek atomik işlemle günceller. |

## Derleme ve çalıştırma

Windows terminalinde:

```powershell
cd mcp-swing-demo
.\mvnw.cmd clean verify
java -jar target\mcp-swing-demo.jar
```

Yalnız arayüzü açmak için:

```powershell
java -jar target\mcp-swing-demo.jar --ui-only
```

Yalnız STDIO MCP sunucusunu çalıştırmak için:

```powershell
java -jar target\mcp-swing-demo.jar --server-only
```

MCP istemcisi sunucuyu `java -jar <tam-yol>\mcp-swing-demo.jar` komutuyla başlatmalıdır.
STDOUT MCP protokolüne ayrıldığı için uygulama tanılama mesajlarını STDERR'a yazar.
