import requests
import time
import json
from pathlib import Path

API_KEY = "llx-IWbVsP0maYq3OvP4VJg2MjM8jxqciXHA9Gx1SLYRB3O2rr8W"
BASE_URL = "https://api.cloud.llamaindex.ai/api/v1"
DATA_DIR = Path(__file__).parent / "data"
STATUS_FILE = DATA_DIR / "split_status.json"

def update_status(filename, status, message=""):
    """Aktualisiert den Status in der Status-Datei"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        else:
            status_data = {}
        
        status_data[filename] = {
            "status": status,
            "message": message,
            "timestamp": time.time()
        }
        
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Fehler beim Aktualisieren des Status: {e}")

categories = [
    {
        "name": "Mietvertrag",
        "description": "Dokument, das die Vereinbarung zwischen Vermieter und Mieter über die Nutzung einer Immobilie regelt, einschließlich Vertragsänderungen oder -verlängerungen."
    },
    {
        "name": "Rechnung",
        "description": "Dokument, das Zahlungsverpflichtungen darstellt, wie z.B. Mietabrechnungen, Betriebskostenabrechnungen oder sonstige Rechnungen."
    },
    {
        "name": "Bewerbung",
        "description": "Dokumente, die von Interessenten eingereicht werden, um eine Immobilie zu mieten, einschließlich Bewerbungsformulare und Mietgesuche."
    },
    {
        "name": "Übergabeprotokoll",
        "description": "Dokumentation des Zustands einer Immobilie bei Ein- oder Auszug, einschließlich Inventar, Schäden und Vereinbarungen über Mängel."
    }
]

session = requests.Session()
session.headers.update({"Authorization": f"Bearer {API_KEY}"})

pdf_files = list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.PDF"))
pdf_files = list(dict.fromkeys(pdf_files))
ergebnisse = {}

# Initialisiere Status-Datei
initial_status = {}
for pdf_file in pdf_files:
    initial_status[pdf_file.name] = {
        "status": "pending",
        "message": "Wartend auf Verarbeitung",
        "timestamp": time.time()
    }
with open(STATUS_FILE, "w", encoding="utf-8") as f:
    json.dump(initial_status, f, indent=2, ensure_ascii=False)

for pdf_file in pdf_files:
    print(f"Verarbeite: {pdf_file.name}...", end=" ", flush=True)
    update_status(pdf_file.name, "processing", "Starte Verarbeitung...")
    
    try:
        # Datei hochladen
        update_status(pdf_file.name, "processing", "Lade Datei hoch...")
        with open(pdf_file, "rb") as f:
            files = {"upload_file": (pdf_file.name, f, "application/pdf")}
            response = session.post(f"{BASE_URL}/files", files=files)
            file_id = response.json()["id"]
        
        # Split-Job erstellen
        update_status(pdf_file.name, "processing", "Erstelle Split-Job...")
        payload = {
            "document_input": {"type": "file_id", "value": file_id},
            "categories": categories,
            "splitting_strategy": {"allow_uncategorized": True}
        }
        response = session.post(f"{BASE_URL}/beta/split/jobs", json=payload, headers={"Content-Type": "application/json"})
        job_id = response.json()["id"]
        
        # Auf Fertigstellung warten
        update_status(pdf_file.name, "processing", "Warte auf Llama Split...")
        while True:
            response = session.get(f"{BASE_URL}/beta/split/jobs/{job_id}")
            job_status = response.json()["status"]
            
            if job_status == "completed":
                segments = response.json().get("result", {}).get("segments", [])
                # Zähler pro Kategorie für eindeutige Segmentnamen
                category_counters = {}
                segment_list = []
                
                for segment in segments:
                    category = segment.get("category", "uncategorized")
                    # Zähler für diese Kategorie erhöhen
                    category_counters[category] = category_counters.get(category, 0) + 1
                    segment_name = f"{category}_{category_counters[category]}"
                    
                    segment_list.append({
                        "name": segment_name,
                        "category": category,
                        "pages": segment.get("pages"),
                        "confidence_category": segment.get("confidence_category")
                    })
                
                ergebnisse[pdf_file.name] = segment_list
                update_status(pdf_file.name, "completed", "Verarbeitung abgeschlossen")
                print("OK", flush=True)  # Verwende Text statt Emoji für Kompatibilität
                break
            elif job_status == "failed":
                ergebnisse[pdf_file.name] = []
                update_status(pdf_file.name, "failed", "Verarbeitung fehlgeschlagen")
                print("FEHLGESCHLAGEN", flush=True)  # Verwende Text statt Emoji
                break
            else:
                # Status ist "processing" oder ähnlich
                update_status(pdf_file.name, "processing", f"Status: {job_status}")
            
            time.sleep(2)
    
    except Exception as e:
        ergebnisse[pdf_file.name] = []
        try:
            update_status(pdf_file.name, "failed", f"Fehler: {str(e)}")
        except Exception as status_error:
            print(f"Warnung: Status-Update fehlgeschlagen: {status_error}", flush=True)
        print(f"FEHLER: {e}", flush=True)

# Ergebnisse speichern
with open(DATA_DIR / "split_results.json", "w", encoding="utf-8") as f:
    json.dump(ergebnisse, f, indent=2, ensure_ascii=False)

print(f"\n{len(ergebnisse)} Datei(en) verarbeitet", flush=True)
