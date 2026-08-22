# ENGLİSH 

# Ghost

Ghost (a.k.a. Ghost Operator) is a personal, local-first AI assistant built on LangGraph. It is the primary, ongoing development focus of the project — an agent that runs on your own machine, keeps its own memory, and can act on your behalf across voice, chat, and (eventually) other tools like Spotify.

## Architecture

- **Supervisor / worker graph** — built on LangGraph's `StateGraph`, with a supervisor node that routes tasks to specialized worker nodes via conditional edges.
- **Critic node** — after a task is marked complete (`GOREV_BITTI`), a self-critique step re-checks whether the task was actually done correctly using the same supervisor model (no tools). If not, it injects a correction message and routes back to the supervisor instead of trusting completion blindly.
- **Tool registry** — a single source of truth (`core/tool_registry.py`) for tool schemas, replacing older manually duplicated tool/arg-map lists.
- **Compact memory** — after each graph run, a one-line summary of tool activity is appended to a lightweight running log.

## Memory pipeline

Ghost separates raw activity from durable knowledge:

1. **EpisodicDB** — a raw buffer of chat/tool logs, each row flagged `is_analyzed`.
2. **LibrarianAgent** — a background thread (runs every ~30s) that sends unanalyzed rows to an LLM, which extracts durable facts and proposes save/update actions.
3. **Bellek (RAG vector store)** — where extracted facts land, with confidence scoring: each fact gets a confidence score (0–1) and a `confirmation_count` that increases on repeated confirmation. A proposed update that contradicts a fact is rejected if the existing fact is well-confirmed (`confirmation_count >= 3`) and the new claim has low confidence (`< 0.8`).
4. **CommandHandler** — the tool dispatcher (file read/write, folder inspection, code execution, etc.), currently stateless between calls.
5. **Project L2 Memory** — A structured, file-based memory (`.ghost/project_memory.json`) that travels with each project's repository. It stores static architectural rules, decisions, constraints, and known errors, which are injected directly into the system prompt when the agent works on that project.

A planned addition is a **"durum hafızası"** (working/state memory) layer — tracking the active project, open files, and in-progress task when switching between projects, separate from long-term RAG memory.

## Voice / UI

- Custom desktop UI built with **CustomTkinter**.
- A PIL-based animated orb, rebuilt with Pillow supersampling for smooth anti-aliased rendering.
- Vosk-based voice activity detection for speech recognition (earlier milestone).

## Notable fixes and milestones

- Migrated from a custom agentic loop to LangGraph/StateGraph.
- Integrated ChromaDB-based RAG memory (with `nomic-embed` in an earlier iteration).
- Removed `planner.py` from the active loop (kept, unused) after finding it added a synchronous LLM call before every command, even trivial ones — a major performance win.
- Fixed infinite tool-call loops caused by the supervisor reading stale message history.
- Fixed a `GOREV_BITTI` tag-stripping bug that silently dropped responses.
- Fixed a "format imitation" bug where accumulated Spotify success strings in context taught the model to fake tool calls instead of making them.
- Built a Spotify integration with proper device wakeup handling.
- Refactored from a single monolithic file into a modular structure (`ui/`, `handlers/`, `core/`, `ai/`, etc.).
- Currently resolving a **format drift bug**: the model imitates natural-language patterns from prior conversation instead of maintaining structured routing tags.

## Roadmap

- **Digital twin repositioning** — evolving Ghost from an assistant into an agent that can handle personal tasks on the user's behalf (reviewing notes, filling out scholarship applications, accessing documents).
- **Dual-memory architecture** — splitting memory into:
  - *General memory*: existing EpisodicDB/SQLite + LibrarianAgent + vector DB, for chat and daily tasks.
  - *Project memory* (new): `ProjeKodBellek`/ChromaDB + an AST-based symbol map (JSON) + code search tools, for coding/project-specific tasks — with the supervisor routing between the two and a light SQL-level link so general memory can still reference recent project context without duplicating code-level detail.
- **Portable project detection** — moving from hardcoded folder-name heuristics to an "ask once, then remember" path-to-name mapping, so the approach stays usable if Ghost becomes a product for other users (all local projects currently live under a fixed path on the developer's machine).
- **Human-in-the-loop confirmation** — having Ghost ask a clarifying question when context is missing (e.g., before acting on unseen code) rather than assuming.
- **Core/frontend split** — splitting Ghost into a persistent core backend (LangGraph brain, memory, tool dispatch) with thin frontend adapters (desktop UI, Telegram bot) sharing one central session store, so switching UIs shows the same conversation. Considering hosting the core remotely (Render/Docker) with a local-agent bridge process for machine-bound tools (screen capture, local Ollama, local files, WhatsApp browser session).

## Status

Under active development since before early 2026. Performance improved significantly after removing planner/queue overhead from the main loop.

# TÜRKCE

# Ghost

Ghost (diğer adıyla Ghost Operator), LangGraph üzerine kurulu, yerel öncelikli (local-first) kişisel bir AI asistanı. Projenin ana geliştirme odağı — kendi bilgisayarında çalışan, kendi hafızasını tutan, sesli/yazılı arayüzler ve (ileride) Spotify gibi araçlar üzerinden kullanıcı adına işlem yapabilen bir ajan.

## Mimari

- **Supervisor / worker graph** — LangGraph'ın `StateGraph` yapısı üzerine kurulu; supervisor node, koşullu kenarlar (conditional edges) üzerinden görevleri özel worker node'lara yönlendiriyor.
- **Critic node** — bir görev `GOREV_BITTI` ile tamamlandı işaretlendikten sonra, aynı supervisor modelini (araçsız) kullanan bir öz-eleştiri adımı görevin gerçekten doğru yapılıp yapılmadığını kontrol ediyor. Değilse, düzeltme mesajı enjekte edip supervisor'a geri yönlendiriyor — tamamlanma bilgisine körü körüne güvenmek yerine.
- **Tool registry** — araç şemaları için tek doğruluk kaynağı (`core/tool_registry.py`), eskiden elle tekrarlanan TOOLS/TOOL_ARG_MAP listelerinin yerini aldı.
- **Kompakt hafıza** — her graph çalışmasından sonra, araç aktivitesinin tek satırlık özeti hafif bir log'a ekleniyor.

## Hafıza pipeline'ı

Ghost, ham aktiviteyi kalıcı bilgiden ayırıyor:

1. **EpisodicDB** — her satırı `is_analyzed` bayraklı, ham sohbet/araç log'u tamponu.
2. **LibrarianAgent** — yaklaşık 30 saniyede bir çalışan bir arka plan thread'i; analiz edilmemiş satırları bir LLM'e gönderip kalıcı bilgileri çıkarıyor ve save/update aksiyonları öneriyor.
3. **Bellek (RAG vektör deposu)** — çıkarılan bilgilerin düştüğü yer; her bilgi 0-1 arası bir güven skoru (confidence) ve tekrar teyitlerde artan bir `confirmation_count` alıyor. Var olan bir bilgiyle çelişen bir güncelleme önerisi, eğer mevcut bilgi iyi teyit edilmişse (`confirmation_count >= 3`) ve yeni iddia düşük güvenliyse (`< 0.8`) reddediliyor.
4. **CommandHandler** — dosya okuma/yazma, klasör inceleme, kod çalıştırma gibi araçları dispatch eden katman; şu an çağrılar arasında stateless.
5. **Project L2 Memory (Proje L2 Hafızası)** — Her projenin kendi klasöründe (repository) tutulan ve kodla birlikte taşınabilen yapısal bir dosya hafızası (`.ghost/project_memory.json`). Mimari kuralları, alınan kararları, kısıtlamaları ve bilinen hataları saklar. Ajan o projede çalışırken bu kurallar doğrudan sistem promptuna (System Prompt) enjekte edilir.

Planlanan bir ek, **"durum hafızası"** (working/state memory) katmanı — projeler arası geçişte aktif proje, açık dosyalar ve devam eden görevi, uzun vadeli RAG hafızasından ayrı olarak takip etmek için.

## Ses / Arayüz

- **CustomTkinter** ile yazılmış özel masaüstü arayüzü.
- PIL tabanlı animasyonlu bir orb; yumuşak anti-aliased render için Pillow supersampling ile yeniden yapıldı.
- Konuşma tanıma için Vosk tabanlı ses aktivitesi algılama (VAD) (önceki bir aşamada).

## Öne çıkan düzeltmeler ve kilometre taşları

- Özel bir agentic loop'tan LangGraph/StateGraph'a geçiş.
- ChromaDB tabanlı RAG hafızasının entegrasyonu (önceki bir iterasyonda `nomic-embed` ile).
- `planner.py`'nin aktif loop'tan çıkarılması (dosya duruyor, kullanılmıyor) — her komuttan önce, en basit olanlarda bile, senkron bir LLM çağrısı eklediği fark edildikten sonra; büyük bir performans kazanımı.
- Supervisor'ın eski (stale) mesaj geçmişini okumasından kaynaklanan sonsuz tool-call döngülerinin düzeltilmesi.
- Yanıtları sessizce düşüren bir `GOREV_BITTI` tag-stripping hatasının düzeltilmesi.
- Context'te biriken Spotify başarı mesajlarının modele sahte tool call yapmayı "öğrettiği" bir format taklidi (format imitation) hatasının düzeltilmesi.
- Doğru cihaz uyandırma (device wakeup) yönetimiyle Spotify entegrasyonu.
- Tek parça monolitik dosyadan modüler bir yapıya (`ui/`, `handlers/`, `core/`, `ai/` vb.) geçiş.
- Şu anda üzerinde çalışılan: bir **format drift hatası** — model, yapılandırılmış routing tag'lerini korumak yerine önceki konuşmadaki doğal dil kalıplarını taklit ediyor.

## Yol haritası

- **"Dijital ikiz" (digital twin) yönlendirmesi** — Ghost'u bir asistandan, kullanıcı adına kişisel görevler yürütebilen bir ajana (notları gözden geçirme, burs başvurularını doldurma, belgelere erişim) evriltmek.
- **İkili hafıza mimarisi** — hafızayı ikiye bölmek:
  - *Genel hafıza*: mevcut EpisodicDB/SQLite + LibrarianAgent + vektör DB, sohbet ve günlük görevler için.
  - *Proje hafızası* (yeni): `ProjeKodBellek`/ChromaDB + AST tabanlı sembol haritası (JSON) + kod arama araçları, kodlama/proje görevleri için — supervisor ikisi arasında yönlendirme yapacak ve genel hafızanın kod düzeyindeki detayı tekrar etmeden yakın proje bağlamına referans verebilmesi için hafif bir SQL-seviyesi bağlantı olacak.
- **Taşınabilir proje algılama** — sabit kodlanmış klasör adı sezgilerinden, "bir kere sor, sonra hatırla" mantığıyla path-to-name eşlemesine geçiş; böylece Ghost başka kullanıcılar için bir ürüne dönüşürse yaklaşım taşınabilir kalır (şu an tüm yerel projeler geliştiricinin makinesinde sabit bir yol altında duruyor).
- **İnsan onaylı (human-in-the-loop) doğrulama** — bağlam eksik olduğunda (örn. görülmemiş bir kod üzerinde işlem yapmadan önce) Ghost'un varsayımda bulunmak yerine netleştirici bir soru sorması.
- **Core/frontend ayrımı** — Ghost'u kalıcı bir core backend'e (LangGraph beyni, hafıza, araç dispatch) ve ince frontend adaptörlerine (masaüstü arayüzü, Telegram botu) bölmek; hepsi tek bir merkezi session store paylaşacak, böylece arayüz değiştirildiğinde aynı konuşma görünecek. Core'u uzaktan (Render/Docker) barındırıp, makineye bağlı araçlar (ekran yakalama, yerel Ollama, yerel dosyalar, WhatsApp tarayıcı oturumu) için yerel bir agent-bridge süreci kullanmak değerlendiriliyor.

## Durum

2026'nın başından önce başlayan, aktif geliştirme sürecinde. Ana loop'tan planner/queue yükünün kaldırılmasının ardından performans belirgin şekilde arttı.