import json
import argparse
from pathlib import Path
from collections import Counter


def parse_standard_line(line):
    """Standart metin log satırını ayrıştırır ve (seviye, mesaj) döndürür."""
    # Örnek: "[INFO] 2023-01-01 12:00:00 - Message"
    if line.startswith("["):
        end_bracket = line.find("]")
        if end_bracket != -1:
            level = line[1:end_bracket].strip().upper()
            rest = line[end_bracket+1:].strip()
            # Tarih ve saat kısmını ayıkla
            if " - " in rest:
                message = rest.split(" - ", 1)[1].strip()
            else:
                message = rest
            return level, message
    return None, None


def parse_json_line(line):
    """JSON satırını ayrıştırır ve (seviye, mesaj) döndürür."""
    try:
        data = json.loads(line)
        level = data.get("level", "").upper()
        message = data.get("message", "")
        return level, message
    except json.JSONDecodeError:
        return None, None


def analyze_log_file(file_path):
    """Log dosyasını analiz eder ve hata mesajlarının sayısını döndürür."""
    error_counter = Counter()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Önce JSON olarak dene
                level, message = parse_json_line(line)
                if level is None:
                    # JSON değilse standart formatı dene
                    level, message = parse_standard_line(line)
                if level == "ERROR" and message:
                    error_counter[message] += 1
    except FileNotFoundError:
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
    except PermissionError:
        raise PermissionError(f"Dosya okuma izni yok: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Dosya okunurken hata oluştu: {e}")
    return error_counter


def write_report(error_counter, output_path):
    """Hata sayılarını JSON rapor dosyasına yazar."""
    report_data = {
        "toplam_benzersiz_hata": len(error_counter),
        "hatalar": [
            {"mesaj": msg, "tekrar_sayisi": count}
            for msg, count in error_counter.most_common()
        ]
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Log dosyasını analiz eder ve hata mesajlarını raporlar.")
    parser.add_argument("log_dosyasi", type=str, help="Analiz edilecek log dosyasının yolu")
    parser.add_argument("-o", "--output", type=str, default="report.json", help="Çıktı rapor dosyasının adı (varsayılan: report.json)")
    args = parser.parse_args()

    try:
        error_counter = analyze_log_file(args.log_dosyasi)
    except (FileNotFoundError, PermissionError, RuntimeError) as e:
        print(f"HATA: {e}")
        return

    # Konsola yazdır
    print(f"\n=== Hata Analizi Raporu ===")
    print(f"Toplam benzersiz hata: {len(error_counter)}")
    print("-" * 50)
    for message, count in error_counter.most_common():
        print(f"[{count:4d}] {message}")

    # Rapor dosyasına yaz
    try:
        write_report(error_counter, args.output)
        print(f"\nRapor dosyaya kaydedildi: {args.output}")
    except Exception as e:
        print(f"HATA: Rapor dosyası yazılamadı: {e}")


if __name__ == "__main__":
    main()