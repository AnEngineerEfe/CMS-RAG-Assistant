# CMS-RAG Git Akışı

## Amaç

Bu politika, çalışan sürümü korurken yeni özelliklerin ve acil düzeltmelerin
birbirine karışmasını önler. Mevcut geçmiş silinmemiş veya yeniden yazılmamıştır;
önceki commitlerin tamamı gerektiğinde geri dönüş için korunur.

## Kalıcı dallar

| Dal | Görev | Doğrudan commit |
|---|---|---|
| `main` | Sunulabilir, testleri geçmiş sürümler | Hayır |
| `develop` | Bir sonraki sürümün entegrasyon tabanı | Hayır |

## Geçici dallar

| Biçim | Kaynak | Hedef | Kullanım |
|---|---|---|---|
| `codex/<konu>` | `develop` | `develop` | Özellik, refactor ve test çalışması |
| `release/<sürüm>` | `develop` | `main` ve sonra `develop` | Son kabul ve sürüm hazırlığı |
| `hotfix/<sürüm>` | `main` | `main` ve `develop` | Üretim sürümündeki acil hata |

Codex çalışma dallarında uygulamanın gerektirdiği `codex/` öneki kullanılır.
İnsan geliştiriciler aynı amaçla kurum standardındaki `feature/` önekini
kullanabilir.

## Günlük geliştirme

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c codex/kisa-konu-adi

# Değiştir, test et ve küçük mantıksal commitler oluştur.
git add <ilgili-dosyalar>
git commit -m "refactor: sunum katmanini modullere ayir"

# İnceleme sonrası entegrasyon.
git switch develop
git merge --no-ff codex/kisa-konu-adi
```

## Sürüm hazırlığı

```powershell
git switch develop
git switch -c release/1.0.0

python -m unittest discover -s tests -v
python -m scripts.evaluate_retrieval

git switch main
git merge --no-ff release/1.0.0
git tag -a v1.0.0 -m "CMS-RAG Assistant v1.0.0"

git switch develop
git merge --no-ff release/1.0.0
```

## Commit standardı

Commit başlıkları tek bir mantıksal değişikliği ve niyetini göstermelidir:

- `feat:` yeni kullanıcı özelliği
- `fix:` hata düzeltmesi
- `refactor:` davranışı koruyan mimari düzenleme
- `test:` test veya kabul kapsamı
- `docs:` dokümantasyon
- `chore:` bağımlılık ve bakım işi

PDF, model ağırlığı, indeks ve çalışma zamanı önbelleği gibi büyük veya yeniden
üretilebilir dosyalar commitlenmez. Yalnız temiz kurulum kabulü için seçilmiş
kamuya açık başlangıç belgesi istisnadır.

## Koruma kuralları

GitHub üzerinde `main` ve `develop` için şu kurallar önerilir:

1. Pull request olmadan birleştirmeyi engelle.
2. En az bir inceleme iste.
3. Otomatik test ve retrieval kabul işini zorunlu durum kontrolü yap.
4. Force-push ve dal silmeyi engelle.
5. Birleştirmeden önce dalın hedefle güncel olmasını zorunlu tut.

## Mevcut geçiş

- Eski `main` geçmişi değiştirilmeden korunmuştur.
- Son doğrulanmış ürün `develop` tabanına alınmıştır.
- Modüler mimari çalışması `codex/modular-architecture` dalında yürütülmektedir.
- Uzak depoya gönderme ve GitHub dal koruma ayarları, kullanıcı onayı ve uzak
  depo yetkisi gerektiren ayrı yayımlama adımlarıdır.
