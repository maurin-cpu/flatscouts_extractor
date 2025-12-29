import json
from pathlib import Path
import fitz  # PyMuPDF
from llama_cloud_services import LlamaParse
import time
import uuid

# Konfiguration
DATA_DIR = Path(__file__).parent / "data"
SPLIT_RESULTS_FILE = DATA_DIR / "split_results.json"
OUTPUT_FILE = DATA_DIR / "parsed_segments.json"
STATUS_FILE = DATA_DIR / "parse_status.json"

def update_parse_status(filename, status, message=""):
    """Aktualisiert den Parse-Status in der Status-Datei"""
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
        print(f"Fehler beim Aktualisieren des Parse-Status: {e}", flush=True)

# LlamaParse Konfiguration
# Optimiert für bessere Tabellenerkennung und vollständiges Markdown:
# - parse_mode="parse_page_with_layout_agent": Speziell für Layout- und Tabellenerkennung optimiert
# - model="openai-gpt4o": Leistungsstärkeres Modell für präzisere Extraktion (ohne Bindestrich!)
# - high_res_ocr=True: Hohe OCR-Auflösung für bessere Texterkennung
# - language="de": Deutsch für bessere Erkennung deutscher Dokumente
# 
# HINWEIS: Falls Markdown unvollständig ist, teste verschiedene Konfigurationen mit test_configurations.py
parser = LlamaParse(
    parse_mode="parse_page_with_agent",
    model="openai-gpt-4-1-mini",
    high_res_ocr=True,
    language="de",
    api_key="llx-IWbVsP0maYq3OvP4VJg2MjM8jxqciXHA9Gx1SLYRB3O2rr8W",
    description="Document-Agent mit GPT-4o (ganzes Dokument-Kontext)"
)


def extract_pages_from_pdf(pdf_path: Path, page_numbers: list[int], segment_name: str) -> Path:
    """
    Extrahiert spezifische Seiten aus einem PDF und erstellt ein temporäres PDF.
    
    Args:
        pdf_path: Pfad zum ursprünglichen PDF
        page_numbers: Liste der Seitennummern (1-basiert)
        segment_name: Name des Segments für eindeutigen Dateinamen
    
    Returns:
        Pfad zum temporären PDF mit den extrahierten Seiten
    """
    # PDF öffnen
    doc = fitz.open(pdf_path)
    
    # Neues temporäres PDF erstellen
    temp_pdf = fitz.open()
    
    # Gewünschte Seiten hinzufügen (Seiten sind 0-basiert in PyMuPDF)
    for page_num in page_numbers:
        if 1 <= page_num <= len(doc):
            temp_pdf.insert_pdf(doc, from_page=page_num-1, to_page=page_num-1)
    
    doc.close()
    
    # Temporäres PDF im data-Ordner speichern (nicht im System-Temp)
    # Eindeutiger Dateiname basierend auf Segment-Name und UUID
    safe_segment_name = "".join(c for c in segment_name if c.isalnum() or c in ('_', '-'))
    temp_filename = f"temp_segment_{safe_segment_name}_{uuid.uuid4().hex[:8]}.pdf"
    temp_file_path = DATA_DIR / temp_filename
    
    temp_pdf.save(str(temp_file_path))
    temp_pdf.close()
    
    return temp_file_path

def parse_segment_with_llamaparse(segment_pdf_path: Path) -> dict:
    """
    Parst ein Segment-PDF mit LlamaParse.
    
    Args:
        segment_pdf_path: Pfad zum Segment-PDF
    
    Returns:
        Dictionary mit geparsten Daten
    """
    try:
        # Überprüfen, dass die Datei existiert
        if not segment_pdf_path.exists():
            return {
                "success": False,
                "error": f"Datei nicht gefunden: {segment_pdf_path}"
            }
        
        # Überprüfen, dass es eine PDF-Datei ist
        temp_doc = fitz.open(segment_pdf_path)
        expected_pages = len(temp_doc)
        temp_doc.close()
        
        result = parser.parse(str(segment_pdf_path))
        
        # Alle Seiten zusammenführen
        full_text = ""
        markdown_content = ""
        
        # Debug: Prüfe verfügbare Attribute
        if result.pages:
            first_page = result.pages[0]
            available_attrs = [attr for attr in dir(first_page) if not attr.startswith('_')]
            # print(f"      Debug: Verfügbare Attribute: {available_attrs}")
        
        for i, page in enumerate(result.pages):
            # Text extrahieren
            if hasattr(page, 'text') and page.text:
                full_text += page.text + "\n\n"
            elif hasattr(page, 'text_blocks') and page.text_blocks:
                # Alternative: Text aus Text-Blöcken extrahieren
                for block in page.text_blocks:
                    if hasattr(block, 'text'):
                        full_text += block.text + "\n"
            
            # Markdown extrahieren
            if hasattr(page, 'md') and page.md:
                markdown_content += page.md + "\n\n"
            elif hasattr(page, 'markdown') and page.markdown:
                # Alternative: Markdown-Attribut
                markdown_content += page.markdown + "\n\n"
        
        parsed_pages = len(result.pages)
        
        # Warnung, wenn nicht alle Seiten geparst wurden
        if parsed_pages != expected_pages:
            print(f"      ⚠️  Warnung: Erwartet {expected_pages} Seite(n), aber {parsed_pages} geparst")
        
        return {
            "success": True,
            "text": full_text.strip(),
            "markdown": markdown_content.strip(),
            "num_pages": parsed_pages,
            "expected_pages": expected_pages
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def main():
    """Hauptfunktion zum Parsen aller Segmente."""
    print("=" * 60)
    print("Starte Parsing der Segmente mit LlamaParse")
    print("=" * 60)
    
    # Split-Ergebnisse laden
    if not SPLIT_RESULTS_FILE.exists():
        print(f"FEHLER: {SPLIT_RESULTS_FILE} nicht gefunden!", flush=True)
        print("Bitte zuerst split_document.py ausführen.", flush=True)
        return
    
    with open(SPLIT_RESULTS_FILE, "r", encoding="utf-8") as f:
        split_results = json.load(f)
    
    parsed_results = {}
    total_segments = sum(len(segments) for segments in split_results.values())
    current_segment = 0
    temp_files_to_cleanup = []  # Liste der temporären Dateien zum Aufräumen
    
    # Für jede PDF-Datei
    # Initialisiere Parse-Status für alle Dokumente
    initial_parse_status = {}
    for pdf_filename in split_results.keys():
        initial_parse_status[pdf_filename] = {
            "status": "pending",
            "message": "Wartend auf Parsing",
            "timestamp": time.time()
        }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_parse_status, f, indent=2, ensure_ascii=False)
    
    for pdf_filename, segments in split_results.items():
        pdf_path = DATA_DIR / pdf_filename
        
        update_parse_status(pdf_filename, "processing", f"Starte Parsing für {pdf_filename}...")
        
        if not pdf_path.exists():
            print(f"WARNUNG: PDF {pdf_filename} nicht gefunden, überspringe...", flush=True)
            update_parse_status(pdf_filename, "failed", f"PDF-Datei nicht gefunden: {pdf_filename}")
            parsed_results[pdf_filename] = []
            continue
        
        print(f"\n📄 Verarbeite: {pdf_filename}")
        print(f"   Anzahl Segmente: {len(segments)}")
        
        parsed_segments = []
        
        # Für jedes Segment
        for segment in segments:
            current_segment += 1
            segment_name = segment["name"]
            category = segment["category"]
            pages = segment["pages"]
            confidence = segment.get("confidence_category", "unknown")
            
            print(f"\n   [{current_segment}/{total_segments}] Segment: {segment_name}")
            print(f"      Kategorie: {category}")
            print(f"      Seiten: {pages}")
            print(f"      Confidence: {confidence}")
            print(f"      Parsing...", end=" ", flush=True)
            
            try:
                # Seiten aus PDF extrahieren
                temp_pdf_path = extract_pages_from_pdf(pdf_path, pages, segment_name)
                temp_files_to_cleanup.append(temp_pdf_path)
                
                # Mit LlamaParse parsen
                parse_result = parse_segment_with_llamaparse(temp_pdf_path)
                
                # Segment-Daten zusammenstellen
                segment_data = {
                    "name": segment_name,
                    "category": category,
                    "pages": pages,
                    "confidence_category": confidence,
                    "parsed": {
                        "text": parse_result.get("text", ""),
                        "markdown": parse_result.get("markdown", ""),
                        "num_pages_parsed": parse_result.get("num_pages", 0)
                    } if parse_result["success"] else {"error": parse_result.get("error", "Unbekannter Fehler")}
                }
                
                print("OK" if parse_result["success"] else f"FEHLER: {parse_result.get('error', 'Unbekannter Fehler')}", flush=True)
                parsed_segments.append(segment_data)
                update_parse_status(pdf_filename, "processing", f"Segment {current_segment}/{total_segments} geparst: {segment_name}")
                    
            except Exception as e:
                parsed_segments.append({
                    "name": segment_name,
                    "category": category,
                    "pages": pages,
                    "confidence_category": confidence,
                    "parsed": {"error": str(e)}
                })
                print(f"FEHLER: {e}", flush=True)
                update_parse_status(pdf_filename, "processing", f"Fehler bei Segment {segment_name}: {str(e)}")
        
        parsed_results[pdf_filename] = parsed_segments
        update_parse_status(pdf_filename, "completed", f"Parsing abgeschlossen für {pdf_filename}")
    
    # Temporäre Dateien aufräumen
    print("\n🧹 Räume temporäre Dateien auf...")
    cleaned_count = 0
    for temp_file in temp_files_to_cleanup:
        if temp_file.exists():
            for attempt in range(5):
                try:
                    temp_file.unlink()
                    cleaned_count += 1
                    break
                except PermissionError:
                    if attempt < 4:
                        time.sleep(2)
                    else:
                        print(f"   ⚠️  Konnte {temp_file.name} nicht löschen")
    
    print(f"   ✅ {cleaned_count}/{len(temp_files_to_cleanup)} temporäre Dateien gelöscht")
    
    # Ergebnisse speichern
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("✅ Parsing abgeschlossen!")
    print(f"📁 Ergebnisse gespeichert in: {OUTPUT_FILE}")
    print("=" * 60)
    
    # Zusammenfassung
    total_parsed = sum(
        sum(1 for seg in segs if "text" in seg.get("parsed", {}))
        for segs in parsed_results.values()
    )
    
    print(f"\nZusammenfassung:", flush=True)
    print(f"   Gesamt Segmente: {total_segments}", flush=True)
    print(f"   Erfolgreich geparst: {total_parsed}", flush=True)
    print(f"   Fehlgeschlagen: {total_segments - total_parsed}", flush=True)

if __name__ == "__main__":
    main()

