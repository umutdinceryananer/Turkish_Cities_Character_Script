"""
DBF ilçe isimlerini referans JSON (ilceler.json) üzerinden düzeltir.

Kullanım:
    # Varsayılan: girdi dosyasının üzerine yazar (temp alır, sonra değiştirir)
    python fix_ilce_dbf.py kars_ilce_sinirlar.dbf ilceler.json

    # Farklı dosyaya yazmak için
    python fix_ilce_dbf.py kars_ilce_sinirlar.dbf ilceler.json --out kars_ilce_sinirlar_fixed.dbf

İşlem sırasında önce kopyalanır, sonra ADI alanı cp1254 olarak yazılır.
Header'daki codepage baytını cp1254 (202) olarak set eder.
"""

from __future__ import annotations

import argparse
import json
import shutil
import unicodedata
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

from dbfread import DBF

# Türkçe karakterleri ASCII'ye indirgerken kullanılacak dönüşüm tablosu
TR_MAP = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ç": "c",
        "Ç": "c",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ö": "o",
        "Ö": "o",
        "ü": "u",
        "Ü": "u",
        "â": "a",
        "Â": "a",
        "î": "i",
        "Î": "i",
        "û": "u",
        "Û": "u",
    }
)


def norm(text: str) -> str:
    """
    Eşleşme için basitleştirilmiş anahtar üretir:
    - Yaygın mojibake dizilerini temizler (ï¿½),
    - Türkçe karakterleri sadeleştirir,
    - Kombine işaretleri kaldırır,
    - ASCII'ye indirip küçültür.
    """
    cleaned = text.replace("ï¿½", "")
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = cleaned.translate(TR_MAP)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii").lower()
    return cleaned


def to_ascii_upper(text: str) -> str:
    """
    Türkçe karakterleri ASCII'ye çevirip büyük harfe çıkarır.
    """
    cleaned = unicodedata.normalize("NFKD", text)
    cleaned = cleaned.translate(TR_MAP)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii")
    return cleaned.upper()


def build_lookup(ref_rows: List[dict]) -> Dict[str, Dict[str, str]]:
    """
    Referans JSON listesinden il -> {normalized: canonical} sözlüğü üretir.
    İl isimleri upper-case tutulur, ilçe isimleri Title-case'e çevrilir.
    """
    lookup: Dict[str, Dict[str, str]] = {}
    for row in ref_rows:
        il = row["sehir_adi"].strip().upper()
        # Referanstaki haliyle bırak (örn. tamamen büyük harf)
        raw_ilce = row["ilce_adi"].strip()
        key = norm(raw_ilce)
        lookup.setdefault(il, {})[key] = raw_ilce

    return lookup


def suggest_name(il: str, current: str, lookup: Dict[str, Dict[str, str]]) -> str | None:
    """
    İl bilgisine göre referanstan en yakın ilçe adını döndürür.
    - Önce normalleştirilmiş tam eşleşme,
    - Sonra fuzzy eşleşme (SequenceMatcher, eşik 0.6)
    """
    candidates = lookup.get(il.upper())
    if not candidates:
        return None

    key = norm(current)
    if key in candidates:
        return candidates[key]

    best_key, best_score = None, 0.0
    for cand_key in candidates:
        score = SequenceMatcher(None, key, cand_key).ratio()
        if score > best_score:
            best_score, best_key = score, cand_key

    if best_key is not None and best_score >= 0.6:
        return candidates[best_key]
    return None


def compute_offsets(table: DBF) -> Dict[str, Tuple[int, int]]:
    """
    Alan başlangıç offset'i ve uzunluğu (byte) hesaplar.
    Dönen dict: field_name -> (offset, length)
    """
    offsets: Dict[str, Tuple[int, int]] = {}
    pos = 1  # silinme bayrağı
    for field in table.fields:
        offsets[field.name.upper()] = (pos, field.length)
        pos += field.length
    return offsets


def apply_updates(
    src: Path,
    dest: Path,
    updates: List[Tuple[int, str]],
    header_len: int,
    record_len: int,
    adi_offset: int,
    adi_length: int,
    field_meta: List[Tuple[str, int, int]],
    encoding: str = "cp1254",
    codepage_byte: int | None = 202,
    write_cpg: bool = True,
) -> None:
    """
    İstenen kayıtların ADI alanını belirtilen encoding ile yazar.
    updates: (record_index, new_value) listesi.
    """
    src_resolved = src.resolve()
    dest_resolved = dest.resolve()
    if src_resolved == dest_resolved:
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        shutil.copyfile(src, tmp)
        target = tmp
    else:
        shutil.copyfile(src, dest)
        target = dest

    data = bytearray(target.read_bytes())

    # dBase codepage marker byte (offset 29)
    if codepage_byte is not None:
        data[29] = codepage_byte

    # Alan displacement'lerini düzelt (dBase field descriptor offset 12-15, little-endian)
    desc_start = 32
    for idx, (_name, field_offset, _field_len) in enumerate(field_meta):
        pos = desc_start + idx * 32 + 12
        data[pos : pos + 4] = int(field_offset).to_bytes(4, "little")

    for rec_idx, new_value in updates:
        record_start = header_len + rec_idx * record_len
        field_start = record_start + adi_offset
        encoded = new_value.encode(encoding, errors="replace")[:adi_length]
        encoded = encoded.ljust(adi_length, b" ")
        data[field_start : field_start + adi_length] = encoded

    target.write_bytes(data)

    if target is not dest:
        target.replace(dest)

    if write_cpg:
        cpg_path = dest.with_suffix(".cpg")
        cpg_path.write_text("UTF-8" if encoding.lower() == "utf-8" else "CP1254", encoding="ascii")


def main() -> None:
    # Konsola UTF-8 yazabilmek için
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="DBF ilçe adlarını düzeltir.")
    parser.add_argument("dbf_path", type=Path, help="Girdi DBF yolu (ör: kars_ilce_sinirlar.dbf)")
    parser.add_argument(
        "ref_json",
        type=Path,
        help="İl/ilçe referans JSON yolu (ör: ilceler.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Çıktı DBF yolu (varsayılan: girdi dosyasının üzerine yazar)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Aynı dosyaya yazar (varsayılan davranış; temp kopya alır).",
    )
    parser.add_argument(
        "--no-codepage",
        action="store_true",
        help="Header codepage baytını cp1254 olarak güncelleme.",
    )
    parser.add_argument(
        "--no-cpg",
        action="store_true",
        help=".cpg dosyasını yazma (varsayılan: CP1254 yazar).",
    )
    parser.add_argument(
        "--utf8",
        action="store_true",
        help="ADI alanını UTF-8 yazar, codepage baytını 0xF0 ve .cpg'yi UTF-8 yapar.",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="ADI alanını aksansız ASCII (büyük harf) yazar (ş->s, ç->c, ğ->g...).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Değer değişmese bile ADI alanlarını yeniden yazar (yeniden kodlamak için).",
    )
    args = parser.parse_args()

    src_dbf = args.dbf_path
    if args.in_place and args.out:
        raise SystemExit("--in-place ile --out birlikte kullanılamaz.")
    if args.out:
        out_dbf = args.out
    else:
        out_dbf = src_dbf

    ref_rows = json.loads(args.ref_json.read_text(encoding="utf-8"))
    lookup = build_lookup(ref_rows)

    table = DBF(str(src_dbf), encoding="cp1254", char_decode_errors="ignore", load=True)
    offsets = compute_offsets(table)
    if "ADI" not in offsets:
        raise SystemExit("ADI alanı bulunamadı.")

    field_meta: List[Tuple[str, int, int]] = []
    for f in table.fields:
        off, flen = offsets[f.name.upper()]
        field_meta.append((f.name, off, flen))

    header_len = table.header.headerlen
    record_len = table.header.recordlen
    adi_offset, adi_length = offsets["ADI"]

    updates: List[Tuple[int, str]] = []
    report_lines: List[str] = []
    for idx, rec in enumerate(table):
        current = rec["ADI"]
        il = rec["IlAdi"] if "IlAdi" in rec else rec.get("ILADI", "")
        suggestion = suggest_name(il, current, lookup)
        if suggestion:
            suggestion = suggestion.upper()
        else:
            # Referansta bulunamazsa mevcut adı tamamen büyük harfe çevir.
            suggestion = current.upper()

        if args.ascii:
            suggestion = to_ascii_upper(suggestion)

        if suggestion != current or args.utf8 or args.force:
            updates.append((idx, suggestion))
            report_lines.append(f"FIX  | {il:<10} | '{current}' -> '{suggestion}'")
        else:
            report_lines.append(f"OK   | {il:<10} | '{current}'")

    print("Önizleme:")
    for line in report_lines:
        print(line)

    encoding = "utf-8" if args.utf8 else "cp1254"
    codepage_byte = 0xF0 if args.utf8 else 202
    if args.no_codepage:
        codepage_byte = None

    apply_updates(
        src=src_dbf,
        dest=out_dbf,
        updates=updates,
        header_len=header_len,
        record_len=record_len,
        adi_offset=adi_offset,
        adi_length=adi_length,
        field_meta=field_meta,
        encoding=encoding,
        codepage_byte=codepage_byte,
        write_cpg=not args.no_cpg,
    )
    if updates:
        print(f"\nYazıldı: {out_dbf} (toplam {len(updates)} kayıt güncellendi)")
    else:
        print(f"\nDeğişiklik yok, header/codepage/.cpg güncellendi: {out_dbf}")


if __name__ == "__main__":
    main()
