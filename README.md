`fix_ilce_dbf.py`, shapefile’in `.dbf` dosyasındaki ilçe adlarını `ilceler.json` referansına göre düzeltir, `ADI` alanını cp1254 yazar ve adı tamamen BÜYÜK harfe çevirir. Varsayılan: aynı dosya adına yazar (temp alır).

Gereksinimler  
- Python 3.8+  
- `python -m pip install --user -r requirements.txt`

Kullanım  
- Varsayılan (aynı dosya adına yazar):  
  `python fix_ilce_dbf.py kars_ilce_sinirlar.dbf ilceler.json`
- Farklı dosya adı:  
  `python fix_ilce_dbf.py kars_ilce_sinirlar.dbf ilceler.json --out kars_ilce_sinirlar_fixed.dbf`

Parametreler  
- `dbf_path`: DBF dosyası  
- `ref_json`: il/ilçe referansı (UTF-8 JSON)  
- `--out`: Çıktı yolu (verilmezse girdi dosyasının üzerine yazar)  
- `--in-place`: Aynı dosyaya yazacağını açıkça belirtir  
- `--no-codepage`: Header codepage (cp1254) set etme

Not  
- Geometri ve diğer alanlar değişmez, sadece `ADI` güncellenir; `ilceler.json` içeriği neyse onu kullanır.
