from pypdf import PdfReader

pdf_path = "data/raw/havelsan/advent_cms.pdf"

reader = PdfReader(pdf_path)

print("=" * 60)
print(f"Toplam Sayfa Sayısı: {len(reader.pages)}")
print("=" * 60)

for page_number, page in enumerate(reader.pages, start=1):
    print(f"\n📄 SAYFA {page_number}")
    print("-" * 60)

    text = page.extract_text()

    if text:
        print(text[:500])  # İlk 500 karakter
    else:
        print("Bu sayfadan metin okunamadı.")