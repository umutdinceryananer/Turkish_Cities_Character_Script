### Ne İşe Yarar?
`fix_ilce_dbf.py`, shapefile’lerin `.dbf` tablosundaki ilçe adlarını, `ilceler.json` referansına bakarak otomatik düzeltir. `IlAdi` alanına göre doğru ilçe adını bulur, `ADI` alanını cp1254 kodlamasıyla yazar. Referansta bulunamasa bile mevcut adı TAMAMEN BÜYÜK harfe çevirir. Varsayılan davranış: aynı dosya adına yazar (temp kopya alıp üzerine yazar); istersen farklı dosya adı verebilirsin.

### Gereksinimler
- Python 3.8+  
- Paketler: `dbfread`, `dbf`  
Kurulum: `python -m pip install --user dbfread dbf`

### Kullanım
1) Varsayılan (aynı dosyaya yazar, temp alır):  
   `python fix_ilce_dbf.py kars_ilce_sinirlar.dbf ilceler.json`

2) Farklı dosya adına yazmak:  
   `python fix_ilce_dbf.py kars_ilce_sinirlar.dbf ilceler.json --out kars_ilce_sinirlar_fixed.dbf`

3) Konsolda “Önizleme” satırlarını kontrol et; yazılan dosyayı shapefile’ın DBF’i olarak kullan.

### Parametreler
- `dbf_path`: Düzeltilmesi istenen DBF yolu.  
- `ref_json`: İl/ilçe referansı (UTF-8 JSON, `ilce_adi` ve `sehir_adi` alanları).  
- `--out`: Çıktı dosya yolu (verilmezse girdi dosyasının üzerine yazar).  
- `--in-place`: (İsteğe bağlı) aynı dosya adına yazacağını açıkça belirtir.  
- `--no-codepage`: Header’daki codepage baytını cp1254 (202) olarak set etmez.

### Notlar
- İsim düzeltmeleri tamamen `ilceler.json` içeriğine göre yapılır; başka yazım değişikliği isterseniz referans dosyasını güncelleyin.
- Geometri ve diğer alanlar değiştirilmez, sadece `ADI` alanı güncellenir.
