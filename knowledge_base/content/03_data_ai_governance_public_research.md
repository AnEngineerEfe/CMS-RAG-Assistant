# Deniz C2, Veri Birlikte Çalışabilirliği ve Sorumlu AI — Açık Kaynak Özeti

## Kapsam

Bu paket, NATO ve ABD Deniz Kuvvetlerinin kamuya açık resmî metinlerinden
hazırlanmıştır. ADVENT'e özgü olmayan genel veri, birlikte çalışabilirlik,
komuta-kontrol ve sorumlu yapay zekâ ilkelerini açıklar. ADVENT ile doğrudan bir
entegrasyon veya kurumsal ilişki, kaynak açıkça belirtmedikçe çıkarılamaz.

## Veri-merkezli birlikte çalışabilirlik

NATO'nun 5 Mayıs 2025 tarihli Alliance Data Strategy metni; kaliteli ve küratörlü
veriyi çok alanlı harekât, birlikte çalışabilirlik, durumsal farkındalık ve
veriye dayalı karar verme için temel stratejik varlık olarak ele alır. Alliance
Data Sharing Ecosystem, NATO Digital Backbone, kontrollü veri paylaşım alanları,
federe veri meshleri, veri katalogları ve standart meta veri bu yaklaşımın
bileşenleridir.

Verinin bulunabilirliği, erişilebilirliği, kalitesi ve yeni teknolojilere uyumu
veri-merkezli referans mimarisinin temel hedefleridir. Standart meta veri,
insanlar ve makineler tarafından aranabilirliği destekler. Semantik birlikte
çalışabilirlik ve makinece okunabilir biçimler, farklı sistemlerin aynı veriyi
anlamlandırabilmesi açısından önemlidir.

## Deniz komuta-kontrolünde ortak resim ve karar desteği

ABD Deniz Kuvvetlerinin kamuya açık GCCS-M tanımında sistem; gemi, denizaltı ve
karadaki deniz harekât merkezlerinde kullanıcılar için gerçeğe yakın zamanlı
taktik/operasyonel durumsal farkındalık, ortak operasyon ve taktik resim ile
Müttefik/koalisyon ortakları arasında veri paylaşımını destekleyen bir deniz
komuta-kontrol sistemi olarak açıklanır.

Kamuya açık Undersea Warfare Decision Support System tanımında ağ üzerindeki
denizaltı savunma harbi kuvvetlerinin işbirlikçi planlama ve görev icrası;
çevresel analiz, arama planlama, kuvvet yönetimi, ortak taktik resim, sensör iz
ve ölçümleri, otomatik ve manuel platformlar arası iz füzyonu gibi işlevler
belirtilir. Bunlar belirli bir ürünün gizli ayrıntıları değil, resmî açık kaynak
C2 işlev örnekleridir.

## NATO sorumlu yapay zekâ ilkeleri

NATO'nun 10 Temmuz 2024 tarihli güncellenmiş AI stratejisi savunmada AI için altı
sorumlu kullanım ilkesini sıralar: hukuka uygunluk; sorumluluk ve hesap
verebilirlik; açıklanabilirlik ve izlenebilirlik; güvenilirlik; yönetilebilirlik;
önyargı azaltma.

Stratejiye göre güvenli ve güvenilir AI için kaliteli, AI-hazır veri ön
koşuldur. Test, değerlendirme, doğrulama ve geçerleme (TEV&V); risk yönetimi,
insan-makine takımındaki sorumluluk ve sistemler arası birlikte çalışabilirlik
AI kabiliyetlerinin benimsenmesinde temel konulardır.

## Bu RAG prototipine yansıyan ilkeler

- Kaynak izi: Her cevap belge ve sayfaya bağlanır.
- Kapalı bilgi alanı: Çalışma anında web taraması yapılmaz.
- Veri minimizasyonu: Yalnız kamuya açık ve küratörlü belgeler indekslenir.
- Güvenli ret: Kaynakta bulunmayan iddia üretilmez.
- İnsan denetimi: Yanıt araştırma yardımcısı çıktısıdır, operasyonel karar değildir.
- Tekrarlanabilirlik: PDF paketi, manifest ve indeks sürümlenir.

## Kaynaklar

1. NATO, “Data Strategy for the Alliance”, 5 Mayıs 2025.
   https://www.nato.int/en/about-us/official-texts-and-resources/official-texts/2025/05/05/data-strategy-for-the-alliance
2. NATO, “Summary of NATO's Revised Artificial Intelligence Strategy”,
   10 Temmuz 2024.
   https://www.nato.int/en/about-us/official-texts-and-resources/official-texts/2024/07/10/summary-of-natos-revised-artificial-intelligence-ai-strategy
3. U.S. Navy PEO C4I, “PMW 150 Command and Control Systems Program Office”,
   Ocak 2026.
   https://www.peoc4i.navy.mil/Portals/98/2026_PMW%20150_Tear%20Sheet_FINAL_JAN2026.pdf
4. U.S. Navy, “AN/UYQ-100 Undersea Warfare Decision Support System”,
   20 Eylül 2021.
   https://www.navy.mil/Resources/Fact-Files/Display-FactFiles/Article/2166791/anuyq-100-undersea-warfare-decision-support-system-usw-dss/

