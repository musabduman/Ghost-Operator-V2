# 👻 Ghost Operator v2

Yapay zeka destekli, RAG (Retrieval-Augmented Generation) hafızasına sahip, masaüstünüzü yöneten, kendi kodunu yazıp düzeltebilen otonom kişisel asistan.

## 🚀 Öne Çıkan Özellikler

- **🧠 Uzun Vadeli Hafıza (RAG):** ChromaDB ve yerel embedding (Nomic-embed) altyapısı sayesinde kendisine söylenenleri (şifreler, kişisel bilgiler, API keyler) vektörel olarak kaydeder. İhtiyaç anında bu bilgileri hatırlar ve bağlama uygun cevaplar üretir.
- **📂 Akıllı Klasör Röntgeni:** Yanlış dosya/klasör yollarını tolere eder. Eğer aranan dosya bulunamazsa çökmez; klasörün içine "röntgen çekerek" mevcut dosyaları listeler ve kullanıcıya alternatifler sunar.
- **🛠️ Otonom Kod Çalıştırma ve Oto-Düzeltme:** - İstenen Python betiklerini yazar ve doğrudan sistemde çalıştırır.
  - Eğer kod hata verirse, hatayı okur, kendi yazdığı dosyayı inceler, düzeltir ve tekrar test eder.
- **🎵 Spotify Entegrasyonu:** Belirli şarkıları veya çalma listelerini anında çalar. Cihaz uyku modundaysa otomatik uyandırma protokollerini devreye sokar.
- **👁️ Ekran Analizi (Vision):** Tek tuşla ekran görüntüsü alıp ekranda ne olduğunu analiz edebilir ve yorumlayabilir.
- **💻 Sistem Kontrolü:** Klasörleri açar, uygulamaları (Cursor, Discord, WhatsApp vb.) başlatır ve hızlı Google aramaları yapar.
- **✨ Dinamik Ghost Arayüzü:** CustomTkinter ile tasarlanmış karanlık modlu (Dark Mode) arayüz. Uygulama kullanılmadığında şeffaflaşarak (%60) ekranda yer kaplamaz, fare üzerine geldiğinde netleşir (%98) ve her zaman en üstte (topmost) kalır.

## 🛠️ Teknolojiler ve Altyapı

- **Dil:** Python
- **Yapay Zeka:** Yerel LLM (Ollama/Gemma tabanlı GhostController)
- **Hafıza:** ChromaDB (Vektör Veritabanı)
- **Arayüz:** CustomTkinter
- **Sistem Kontrolü:** Regex, Subprocess, OS modülleri

## 👨‍💻 Geliştirici
**Musab Duman** *Bilgisayar Mühendisliği 1. Sınıf Öğrencisi & Proje Tutkunu*