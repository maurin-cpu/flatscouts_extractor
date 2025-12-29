from flask import Flask, render_template, jsonify, send_from_directory, send_file, make_response, request
from pathlib import Path
import json
import os
import subprocess
import sys
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
# Erhöhe Timeout für große Dateien
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max

# Datenverzeichnis - verwende lokales data-Verzeichnis
DATA_DIR = Path(__file__).parent / "data"
# Lokales Datenverzeichnis für JSON-Dateien (gleich wie DATA_DIR)
LOCAL_DATA_DIR = Path(__file__).parent / "data"

@app.route('/')
def index():
    """Hauptseite"""
    return render_template('index.html')

def normalize_filename(filename):
    """Normalisiert Dateinamen für Vergleich (entfernt Umlaute, case-insensitive)"""
    # Entferne Umlaute und Sonderzeichen für Vergleich
    replacements = {
        'ä': 'a', 'ö': 'o', 'ü': 'u', 'Ä': 'A', 'Ö': 'O', 'Ü': 'U',
        'ß': 'ss', 'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a',
        'ç': 'c', 'ñ': 'n'
    }
    normalized = filename.lower()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized

def check_pdf_exists(filename):
    """Prüft ob eine PDF-Datei existiert (verschiedene Groß-/Kleinschreibungen und Umlaute)"""
    # Normalisiere den Dateinamen (entferne Pfad falls vorhanden)
    filename_only = Path(filename).name
    
    # Prüfe exakte Übereinstimmung
    pdf_path = DATA_DIR / filename_only
    if pdf_path.exists() and pdf_path.is_file():
        return True
    
    # Prüfe alle PDF-Dateien im Verzeichnis (case-insensitive und umlaut-tolerant)
    try:
        existing_pdfs = list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.PDF"))
        normalized_search = normalize_filename(filename_only)
        
        for existing_pdf in existing_pdfs:
            # Vergleiche normalisiert (case-insensitive und ohne Umlaute)
            normalized_existing = normalize_filename(existing_pdf.name)
            if normalized_existing == normalized_search:
                print(f"Gefunden via Normalisierung: {existing_pdf.name} -> {filename_only}")
                return True
    except Exception as e:
        print(f"Fehler beim Prüfen der PDF-Existenz für {filename}: {e}")
    
    return False

@app.route('/api/documents')
def get_documents():
    """API-Endpunkt: Lädt nur Dokumente die von parse_segments.py verarbeitet wurden"""
    # Verhindere Caching
    response = make_response(jsonify([]))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    daten = []
    
    # Versuche zuerst split_results.json zu laden (von split_document.py erstellt)
    split_results_path = DATA_DIR / "split_results.json"
    if not split_results_path.exists():
        split_results_path = LOCAL_DATA_DIR / "split_results.json"
    
    if split_results_path.exists():
        try:
            with open(split_results_path, "r", encoding="utf-8") as f:
                split_results = json.load(f)
                
                # split_results ist ein Dictionary (Dateiname -> Liste von Segmenten)
                if isinstance(split_results, dict):
                    for dateiname, segments in split_results.items():
                        exists = check_pdf_exists(dateiname)
                        print(f"Prüfe PDF (split_results): {dateiname} -> Existiert: {exists}")
                        
                        if not exists:
                            normalized_search = normalize_filename(dateiname)
                            existing_pdfs = list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.PDF"))
                            for existing_pdf in existing_pdfs:
                                normalized_existing = normalize_filename(existing_pdf.name)
                                if normalized_existing == normalized_search:
                                    print(f"Gefunden via Normalisierung: {existing_pdf.name} -> {dateiname}")
                                    exists = True
                                    break
                        
                        if exists:
                            daten.append({
                                "quelle": "Split-Results",
                                "datei": dateiname,
                                "daten": {"segments": segments}
                            })
                        else:
                            print(f"PDF nicht gefunden, überspringe: {dateiname} (Pfad: {DATA_DIR / dateiname})")
        except Exception as e:
            print(f"Fehler beim Laden von split_results.json: {e}")
    
    # Falls keine Daten aus split_results.json, versuche parsed_segments.json (von parse_segments.py)
    if not daten:
        parsed_segments_path = DATA_DIR / "parsed_segments.json"
        if not parsed_segments_path.exists():
            parsed_segments_path = LOCAL_DATA_DIR / "parsed_segments.json"
        
        if parsed_segments_path.exists():
            try:
                with open(parsed_segments_path, "r", encoding="utf-8") as f:
                    parsed_segments = json.load(f)
                    
                    # parsed_segments ist ein Dictionary (Dateiname -> Segmente)
                    if isinstance(parsed_segments, dict):
                        for dateiname, segments in parsed_segments.items():
                            exists = check_pdf_exists(dateiname)
                            print(f"Prüfe PDF (parsed_segments): {dateiname} -> Existiert: {exists}")
                            
                            if not exists:
                                normalized_search = normalize_filename(dateiname)
                                existing_pdfs = list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.PDF"))
                                for existing_pdf in existing_pdfs:
                                    normalized_existing = normalize_filename(existing_pdf.name)
                                    if normalized_existing == normalized_search:
                                        print(f"Gefunden via Normalisierung: {existing_pdf.name} -> {dateiname}")
                                        exists = True
                                        break
                            
                            if exists:
                                daten.append({
                                    "quelle": "Parsed-Segments",
                                    "datei": dateiname,
                                    "daten": {"segments": segments}
                                })
                            else:
                                print(f"PDF nicht gefunden, überspringe: {dateiname} (Pfad: {DATA_DIR / dateiname})")
            except Exception as e:
                print(f"Fehler beim Laden von parsed_segments.json: {e}")
        else:
            print("Weder split_results.json noch parsed_segments.json gefunden - keine verarbeiteten Dokumente")
    
    # Erstelle Response mit Cache-Control Headern
    response = make_response(jsonify(daten))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/json/<json_type>')
def get_json_data(json_type):
    """API-Endpunkt: Lädt verschiedene JSON-Dateien"""
    json_files = {
        'kategorisierte_dokumente': 'kategorisierte_dokumente.json',
        'dokumente_nach_quelle': 'dokumente_nach_quelle.json',
        'split_results': 'split_results.json',
        'parsed_segments': 'parsed_segments.json'
    }
    
    if json_type not in json_files:
        return jsonify({"error": "Ungültiger JSON-Typ"}), 400
    
    # Versuche zuerst im lokalen data-Verzeichnis, dann im DATA_DIR
    json_path = LOCAL_DATA_DIR / json_files[json_type]
    if not json_path.exists():
        json_path = DATA_DIR / json_files[json_type]
    
    if not json_path.exists():
        return jsonify({"error": f"JSON-Datei nicht gefunden: {json_files[json_type]}"}), 404
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Fehler beim Laden der JSON-Datei: {str(e)}"}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """API-Endpunkt: Listet alle PDF-Dateien im data-Ordner auf"""
    try:
        # Stelle sicher, dass das data-Verzeichnis existiert
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Finde alle PDF-Dateien (case-insensitive, um Duplikate zu vermeiden)
        pdf_files = list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.PDF"))
        
        # Entferne Duplikate basierend auf normalisiertem Dateinamen (case-insensitive)
        seen = set()
        unique_pdf_files = []
        for pdf_file in pdf_files:
            normalized_name = pdf_file.name.lower()
            if normalized_name not in seen:
                seen.add(normalized_name)
                unique_pdf_files.append(pdf_file)
        
        # Erstelle Liste mit Dateiinformationen
        files_list = []
        for pdf_file in unique_pdf_files:
            stat = pdf_file.stat()
            files_list.append({
                "filename": pdf_file.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "path": str(pdf_file.relative_to(DATA_DIR))
            })
        
        # Sortiere nach Dateiname
        files_list.sort(key=lambda x: x["filename"].lower())
        
        return jsonify({
            "success": True,
            "files": files_list,
            "count": len(files_list)
        }), 200
        
    except Exception as e:
        print(f"Fehler beim Auflisten der Dateien: {e}")
        return jsonify({"error": f"Fehler beim Auflisten: {str(e)}"}), 500

@app.route('/api/files/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    """API-Endpunkt: Löscht eine PDF-Datei aus dem data-Ordner"""
    try:
        # Sichere den Dateinamen
        filename = secure_filename(filename)
        file_path = DATA_DIR / filename
        
        # Prüfe ob Datei existiert
        if not file_path.exists():
            return jsonify({"error": "Datei nicht gefunden"}), 404
        
        # Prüfe ob es eine PDF-Datei ist
        if not filename.lower().endswith('.pdf'):
            return jsonify({"error": "Nur PDF-Dateien können gelöscht werden"}), 400
        
        # Lösche die Datei
        file_path.unlink()
        
        return jsonify({
            "success": True,
            "message": f"Datei {filename} erfolgreich gelöscht"
        }), 200
        
    except Exception as e:
        print(f"Fehler beim Löschen der Datei: {e}")
        return jsonify({"error": f"Fehler beim Löschen: {str(e)}"}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """API-Endpunkt: Lädt PDF-Dateien hoch"""
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei ausgewählt"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Keine Datei ausgewählt"}), 400
    
    # Prüfe ob es eine PDF-Datei ist
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Nur PDF-Dateien werden unterstützt"}), 400
    
    try:
        # Sichere den Dateinamen
        filename = secure_filename(file.filename)
        
        # Stelle sicher, dass das data-Verzeichnis existiert
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Speichere die Datei
        file_path = DATA_DIR / filename
        
        # Wenn Datei bereits existiert, füge einen Zähler hinzu
        counter = 1
        original_filename = filename
        while file_path.exists():
            name_part = Path(original_filename).stem
            ext_part = Path(original_filename).suffix
            filename = f"{name_part}_{counter}{ext_part}"
            file_path = DATA_DIR / filename
            counter += 1
        
        file.save(str(file_path))
        
        return jsonify({
            "success": True,
            "filename": filename,
            "message": f"Datei {filename} erfolgreich hochgeladen"
        }), 200
        
    except Exception as e:
        print(f"Fehler beim Hochladen der Datei: {e}")
        return jsonify({"error": f"Fehler beim Hochladen: {str(e)}"}), 500

@app.route('/api/process', methods=['POST'])
def process_documents():
    """API-Endpunkt: Startet split_document.py zur Verarbeitung der Dokumente"""
    try:
        # Pfad zu split_document.py
        script_path = Path(__file__).parent / "split_document.py"
        
        if not script_path.exists():
            return jsonify({"error": "split_document.py nicht gefunden"}), 404
        
        # Starte das Skript als Subprocess
        # Verwende das Python aus dem venv falls vorhanden
        venv_python = Path(__file__).parent / "venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        
        # Starte das Skript im Hintergrund
        # Auf Windows verwenden wir CREATE_NO_WINDOW um kein neues Konsolenfenster zu öffnen
        # Die Ausgabe wird in Dateien umgeleitet
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = int(time.time())
        stdout_file = log_dir / f"split_document_{timestamp}.log"
        stderr_file = log_dir / f"split_document_{timestamp}_error.log"
        
        # Öffne Dateien mit UTF-8 Kodierung und lasse sie offen für den Prozess
        stdout_f = open(stdout_file, "w", encoding="utf-8", buffering=1, errors='replace')
        stderr_f = open(stderr_file, "w", encoding="utf-8", buffering=1, errors='replace')
        
        # Stelle sicher, dass die Umgebungsvariablen UTF-8 verwenden
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        # Starte Prozess
        creation_flags = 0
        if sys.platform == "win32":
            # CREATE_NO_WINDOW verhindert ein neues Konsolenfenster
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        process = subprocess.Popen(
            [python_exe, str(script_path)],
            stdout=stdout_f,
            stderr=stderr_f,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=str(Path(__file__).parent),
            env=env,
            creationflags=creation_flags
        )
        
        # WICHTIG: Dateien NICHT schließen - der Prozess braucht sie
        # Sie werden automatisch geschlossen wenn der Prozess endet
        
        print(f"Split-Dokument-Prozess gestartet: PID {process.pid}")
        print(f"Log-Dateien: {stdout_file}, {stderr_file}")
        print(f"Stdout/Stderr bleiben offen für Prozess {process.pid}")
        
        return jsonify({
            "success": True,
            "message": "Verarbeitung gestartet",
            "pid": process.pid
        }), 200
        
    except Exception as e:
        print(f"Fehler beim Starten von split_document.py: {e}")
        return jsonify({"error": f"Fehler beim Starten der Verarbeitung: {str(e)}"}), 500

@app.route('/api/parse-documents', methods=['POST'])
def parse_documents():
    """API-Endpunkt: Startet parse_segments.py zur weiteren Verarbeitung der Dokumente"""
    try:
        # Pfad zu parse_segments.py
        script_path = Path(__file__).parent / "parse_segments.py"
        
        if not script_path.exists():
            return jsonify({"error": "parse_segments.py nicht gefunden"}), 404
        
        # Starte das Skript als Subprocess
        # Verwende das Python aus dem venv falls vorhanden
        venv_python = Path(__file__).parent / "venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        
        # Starte das Skript im Hintergrund
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = int(time.time())
        stdout_file = log_dir / f"parse_segments_{timestamp}.log"
        stderr_file = log_dir / f"parse_segments_{timestamp}_error.log"
        
        # Öffne Dateien mit UTF-8 Kodierung und lasse sie offen für den Prozess
        stdout_f = open(stdout_file, "w", encoding="utf-8", buffering=1, errors='replace')
        stderr_f = open(stderr_file, "w", encoding="utf-8", buffering=1, errors='replace')
        
        # Stelle sicher, dass die Umgebungsvariablen UTF-8 verwenden
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        # Starte Prozess
        creation_flags = 0
        if sys.platform == "win32":
            # CREATE_NO_WINDOW verhindert ein neues Konsolenfenster
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        process = subprocess.Popen(
            [python_exe, str(script_path)],
            stdout=stdout_f,
            stderr=stderr_f,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=str(Path(__file__).parent),
            env=env,
            creationflags=creation_flags
        )
        
        print(f"Parse-Segments-Prozess gestartet: PID {process.pid}")
        print(f"Log-Dateien: {stdout_file}, {stderr_file}")
        
        return jsonify({
            "success": True,
            "message": "Parsing gestartet",
            "pid": process.pid
        }), 200
        
    except Exception as e:
        print(f"Fehler beim Starten von parse_segments.py: {e}")
        return jsonify({"error": f"Fehler beim Starten des Parsing: {str(e)}"}), 500

@app.route('/api/process-status', methods=['GET'])
def process_status():
    """API-Endpunkt: Gibt den aktuellen Status jedes Dokuments zurück"""
    try:
        # Prüfe ob split_results.json existiert (von split_document.py erstellt)
        split_results_path = DATA_DIR / "split_results.json"
        if not split_results_path.exists():
            split_results_path = LOCAL_DATA_DIR / "split_results.json"
        
        # Lade Status-Datei für einzelne Dokumente (von split_document.py)
        status_data_file = DATA_DIR / "split_status.json"
        if not status_data_file.exists():
            status_data_file = LOCAL_DATA_DIR / "split_status.json"
        
        status_data = {}
        if status_data_file.exists():
            try:
                with open(status_data_file, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden der Status-Datei: {e}")
        
        # Prüfe ob split_document.py abgeschlossen ist
        split_completed = split_results_path.exists()
        
        # Prüfe ob parse_segments.py abgeschlossen ist
        parsed_segments_path = DATA_DIR / "parsed_segments.json"
        if not parsed_segments_path.exists():
            parsed_segments_path = LOCAL_DATA_DIR / "parsed_segments.json"
        
        parse_completed = parsed_segments_path.exists()
        
        # Lade Parse-Status-Datei falls vorhanden
        parse_status_file = DATA_DIR / "parse_status.json"
        if not parse_status_file.exists():
            parse_status_file = LOCAL_DATA_DIR / "parse_status.json"
        
        parse_status_data = {}
        if parse_status_file.exists():
            try:
                with open(parse_status_file, "r", encoding="utf-8") as f:
                    parse_status_data = json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden der Parse-Status-Datei: {e}")
        
        # Kombiniere beide Status-Daten
        combined_status = {}
        # Füge Split-Status hinzu
        for filename, status_info in status_data.items():
            combined_status[filename] = {
                "split_status": status_info.get("status", "pending"),
                "split_message": status_info.get("message", ""),
                "parse_status": parse_status_data.get(filename, {}).get("status", "pending"),
                "parse_message": parse_status_data.get(filename, {}).get("message", "")
            }
        
        # Füge Parse-Status für Dokumente hinzu, die nur in parse_status_data sind
        for filename, status_info in parse_status_data.items():
            if filename not in combined_status:
                combined_status[filename] = {
                    "split_status": "completed",
                    "split_message": "",
                    "parse_status": status_info.get("status", "pending"),
                    "parse_message": status_info.get("message", "")
                }
        
        all_completed = split_completed and parse_completed
        
        return jsonify({
            "completed": all_completed,
            "split_completed": split_completed,
            "parse_completed": parse_completed,
            "status": combined_status,
            "message": "Verarbeitung abgeschlossen" if all_completed else "Verarbeitung läuft noch"
        }), 200
            
    except Exception as e:
        print(f"Fehler beim Prüfen des Verarbeitungsstatus: {e}")
        return jsonify({"error": f"Fehler beim Prüfen des Status: {str(e)}"}), 500

@app.route('/api/pdf/<path:filename>')
def serve_pdf(filename):
    """Served PDF-Dateien mit Streaming für große Dateien"""
    # Versuche verschiedene Groß-/Kleinschreibungen
    pdf_path = DATA_DIR / filename
    if not pdf_path.exists():
        # Versuche verschiedene Varianten
        for ext in [".pdf", ".PDF"]:
            test_path = DATA_DIR / (Path(filename).stem + ext)
            if test_path.exists():
                pdf_path = test_path
                break
    
    if not pdf_path.exists():
        return jsonify({"error": "PDF nicht gefunden"}), 404
    
    try:
        # Verwende send_file mit Streaming für große Dateien
        return send_file(
            str(pdf_path),
            mimetype='application/pdf',
            as_attachment=False,
            download_name=pdf_path.name,
            conditional=True  # Unterstützt Range-Requests für besseres Streaming
        )
    except Exception as e:
        print(f"Fehler beim Senden der PDF-Datei {filename}: {e}")
        return jsonify({"error": f"Fehler beim Laden der PDF: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)





