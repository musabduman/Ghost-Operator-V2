import sys
import json
import os
import threading
import customtkinter as ctk

# Proje dizinini sys.path'e ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ui.diff_dialog import show_diff_dialog

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"approved": False, "reason": "Argüman eksik"}))
        return

    json_path = sys.argv[1]
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    app = ctk.CTk()
    app.withdraw() # Ana pencereyi gizle

    event = threading.Event()
    result_holder = {"approved": False, "reason": ""}

    def on_ready():
        show_diff_dialog(app, data["dosya_yolu"], data["eski_icerik"], data["yeni_icerik"], data["aciklama"], event, result_holder)
        wait_event()

    def wait_event():
        if event.is_set():
            app.quit()
        else:
            app.after(100, wait_event)

    app.after(0, on_ready)
    app.mainloop()

    # JSON çıktısı olarak stdout'a yaz
    print(json.dumps(result_holder))

if __name__ == "__main__":
    main()
