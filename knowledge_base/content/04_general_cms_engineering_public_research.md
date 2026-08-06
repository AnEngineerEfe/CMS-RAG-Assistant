# Deniz Savaş Yönetim Sistemleri — Genel Mühendislik ve Güvenilir AI İlkeleri

## Kapsam ve ürünlerden bağımsızlık

Bu bilgi paketi, ABD Deniz Kuvvetleri, NAVSEA ve NIST tarafından yayımlanmış kamuya
açık resmî kaynaklardan hazırlanmıştır. Deniz savaş yönetim sistemlerine ilişkin
genel mühendislik kavramlarını açıklar; ADVENT'e veya başka bir ürüne kaynakta
bulunmayan özellik atfetmez. Şirket içi, tasnifli, operasyonel ya da kişisel veri
içermez ve operasyonel talimat niteliği taşımaz.

## Bütünleşik savaş sistemi ve karar desteği

ABD Deniz Kuvvetlerinin AEGIS kamu tanımında savaş sistemi; merkezî, otomatik bir
komuta-kontrol ve silah kontrol sistemi olarak açıklanır. Bilgisayar tabanlı komuta
ve karar bileşeni sistemin çekirdeğidir. Çok işlevli sensörler arama, izleme ve
güdüm görevlerini birlikte destekler; savaş sistemi hava, suüstü ve denizaltı
harbi gibi birden fazla görev alanındaki unsurları bütünleştirir.

Bu örnekten çıkarılabilecek genel CMS ilkesi, sensör verisinin karar desteği ve
uygun görev kaynaklarıyla aynı bilgi zincirinde yönetilmesidir. Bu ifade belirli
bir angajman yöntemi veya ürün performansı iddiası değildir. Amaç operatöre
tutarlı bir durum resmi ve izlenebilir karar desteği sağlamaktır; yetkili insanın
karar sorumluluğu korunur.

## Ortak operasyon resmi ve veri füzyonu

ABD Deniz Kuvvetlerinin GCCS-M kamu açıklamasına göre deniz komuta-kontrol sistemi;
dost, hasım ve tarafsız kara, deniz ve hava unsurlarının konum ve nitelik bilgisini
birleştirir, ilişkilendirir, süzer, sürdürür ve görüntüler. Haritalar, seyir
haritaları, topoğrafik ve oşinografik katmanlar, meteoroloji, görüntü ve farklı
istihbarat kaynakları ortak operasyon resminde bir araya getirilebilir.

Ortak resim, aynı verinin herkes tarafından kontrolsüz biçimde görülmesi anlamına
gelmez. Kullanıcı rolü, görev kapsamı, veri kaynağı, zaman damgası, güven seviyesi
ve paylaşım politikası korunmalıdır. Bir CMS açısından veri füzyonu yalnız
görselleştirme değil; gözlemlerin ilişkilendirilmesi, mükerrer kayıtların
azaltılması, kimlik ve niteliklerin güncellenmesi ve kaynağın izlenebilmesidir.

## Dağıtık sensör ağı ve birlikte çalışabilirlik

ABD Deniz Kuvvetleri Cooperative Engagement Capability tanımında coğrafi olarak
dağıtılmış sensörlerin ağ üzerinden birleştirilerek tek bir bütünleşik hava resmi
üretmesi anlatılır. Sistem, radar ve dost-düşman tanıma sensörü verisini yetkili
birimler arasında paylaşır. Sensör ağı işleme bileşeni ile gerçek zamanlı veri
dağıtım bileşeni iki temel işlev grubu olarak belirtilir.

Genel CMS mühendisliğinde birlikte çalışabilirlik; yalnız fiziksel bağlantı
kurmak değildir. Veri modeli, ileti biçimi, zamanlama, kimlik, koordinat referansı,
güvenlik etiketi ve anlamın iki sistemde tutarlı yorumlanması gerekir. Taktik veri
bağları ve standart arayüzler, farklı platformların ortak durumsal farkındalık ve
koordineli görev icrası için veri alışverişini destekler.

## Açık ve modüler mimari ile yaşam döngüsü

NAVSEA PEO IWS kamu açıklamasında açık mimari girişimi; radar, sonar, silah,
elektronik harp, denizaltı harbi ve komuta-kontrol bileşenlerinin gemi, müşterek ve
müttefik sistemlerle uyumlu çalışmasını destekleyen bir yaklaşım olarak sunulur.
Kamuya açık savaş sistemi mühendisliği yayınlarında iyi tanımlanmış ve kararlı
arayüzlerin, iç bileşenlerin birbirinden daha bağımsız geliştirilmesine yardımcı
olduğu belirtilir.

Modülerlik, her parçanın sınırsız biçimde değiştirilebilmesi demek değildir.
Arayüz sözleşmeleri, sürüm uyumluluğu, emniyet, siber güvenlik ve yeniden
sertifikasyon etkileri yönetilmelidir. Yaşam döngüsü; gereksinim, tasarım,
entegrasyon, doğrulama, geçerleme, konuşlandırma, bakım, modernizasyon ve kullanım
dışı bırakma aşamalarını kapsayan sürekli bir mühendislik faaliyetidir.

## Test, değerlendirme ve insanlı ekip

NAVSEA Surface Combat Systems Center kamu tanımında sistemler arası, platformlar
arası ve müşterek ortam birlikte çalışabilirlik testleri; canlı ve benzetimli
operasyonlar, eğitim, geliştirme, sertifikasyon ve donanım-döngüde testler birlikte
ele alınır. Yüksek doğruluklu test ortamı, gerçek sisteme geçmeden önce arayüz,
veri akışı ve insan-makine etkileşimi sorunlarının gözlenmesini destekler.

Bir RAG veya AI bileşeni CMS araştırmasına eklendiğinde değerlendirme yalnız cevap
akıcı mı sorusuyla sınırlı kalmamalıdır. Doğru kanıtın bulunması, yanlış olumlu ve
yanlış olumsuz kararlar, kaynak sadakati, gecikme, tekrar üretilebilirlik, güvenli
ret ve insan denetimine uygunluk ayrı ölçülmelidir.

## Sıfır güven ve güvenilir yapay zekâ

NIST SP 800-207, sıfır güven yaklaşımında kullanıcı veya varlıklara yalnız ağ
konumu ya da sahiplik nedeniyle örtük güven verilmemesini; kimlik doğrulama ve
yetkilendirmenin kurumsal kaynağa erişimden önce ayrı işlevler olarak uygulanmasını
tanımlar. Koruma odağı yalnız ağ segmentleri değil, varlıklar, hizmetler, iş
akışları ve hesaplardır.

NIST AI RMF; geçerli ve güvenilir, emniyetli, güvenli ve dayanıklı, hesap verebilir
ve şeffaf, açıklanabilir ve yorumlanabilir, mahremiyeti güçlendirilmiş ve zararlı
önyargıları yönetilmiş AI özelliklerini ele alır. Govern, Map, Measure ve Manage
işlevleri risk yönetimini yaşam döngüsüne yayar. Yüksek etkili kullanımda insan
rolleri, sorumlulukları, müdahale noktaları ve sistem sınırları açıkça
tanımlanmalıdır.

## Kaynaklar

1. U.S. Navy, “AEGIS Weapon System”, 20 Eylül 2021.
   https://www.navy.mil/Resources/Fact-Files/Display-FactFiles/Article/2166739/aegis/aegis-weapon-system/
2. U.S. Department of the Navy, “Global Command and Control System–Maritime”.
   https://www.secnav.navy.mil/rda/Pages/Programs/GCCSM.aspx
3. U.S. Navy, “Cooperative Engagement Capability”, 14 Ekim 2021.
   https://www.navy.mil/DesktopModules/ArticleCS/Print.aspx?Article=2166802&ModuleId=724&PortalId=1
4. NAVSEA, “PEO IWS Industry Engagement”.
   https://www.navsea.navy.mil/Home/PEO-IWS/PEO-IWS-Industry-Engagement/
5. NAVSEA Surface Combat Systems Center, “About Us”.
   https://www.navsea.navy.mil/Home/SCSC/About-Us/
6. NIST, “SP 800-207: Zero Trust Architecture”, Ağustos 2020.
   https://csrc.nist.gov/pubs/sp/800/207/final
7. NIST, “Artificial Intelligence Risk Management Framework 1.0”, Ocak 2023.
   https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10
