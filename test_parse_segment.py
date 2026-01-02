"""Test-Skript zum Parsen einer einzelnen Seite mit LlamaParse"""
import json
from pathlib import Path
import fitz
import uuid
from llama_cloud_services import LlamaParse

# Konfiguration
DATA_DIR = Path(__file__).parent / "data_test"
TEST_PDF = "liegenschaft.PDF"
TEST_PAGE = 40

# LlamaParse Parameter - direkt anpassbar

parser = LlamaParse(
    parse_mode="parse_page_with_agent",
    model="openai-gpt-4-1-mini",
    high_res_ocr=True,
    language="de",
    api_key="llx-IWbVsP0maYq3OvP4VJg2MjM8jxqciXHA9Gx1SLYRB3O2rr8W",
)
'''
parser = LlamaParse(
    tier="premium",
    api_key="llx-IWbVsP0maYq3OvP4VJg2MjM8jxqciXHA9Gx1SLYRB3O2rr8W",
)

parser = LlamaParse(
    preset="invoice",
    api_key="llx-IWbVsP0maYq3OvP4VJg2MjM8jxqciXHA9Gx1SLYRB3O2rr8W",
)


parser = LlamaParse(
    parse_mode="parse_page_with_agent",  # The parsing mode
    model="anthropic-sonnet-4.0",  # The model to use
    high_res_ocr=True,  # Whether to use high resolution OCR (slower but more precise)
    adaptive_long_table=True,  # Adaptive long table. LlamaParse will try to detect long table and adapt the output
    outlined_table_extraction=True,  # Whether to try to extract outlined tables
    output_tables_as_HTML=False,  # Whether to output tables as HTML in the markdown output
    api_key="llx-IWbVsP0maYq3OvP4VJg2MjM8jxqciXHA9Gx1SLYRB3O2rr8W",
)

parser = LlamaParse(
    parse_mode="parse_page_with_agent",
    model="openai-gpt-4-1-mini",
    high_res_ocr=True,
    language="de",
    api_key="llx-IWbVsP0maYq3OvP4VJg2MjM8jxqciXHA9Gx1SLYRB3O2rr8W",
    description="Document-Agent mit GPT-4o (ganzes Dokument-Kontext)"
)

'''

def extract_page(pdf_path: Path, page_num: int) -> Path:
    """Extrahiert eine Seite aus dem PDF"""
    doc = fitz.open(pdf_path)
    temp_pdf = fitz.open()
    temp_pdf.insert_pdf(doc, from_page=page_num-1, to_page=page_num-1)
    temp_file = DATA_DIR / f"temp_page_{page_num}_{uuid.uuid4().hex[:8]}.pdf"
    temp_pdf.save(str(temp_file))
    doc.close()
    temp_pdf.close()
    return temp_file

def parse_pdf(pdf_path: Path) -> dict:
    """Parst ein PDF mit LlamaParse"""
    try:
        result = parser.parse(str(pdf_path))
        text = "\n\n".join(page.text for page in result.pages if hasattr(page, 'text') and page.text)
        markdown = "\n\n".join(page.md for page in result.pages if hasattr(page, 'md') and page.md)
        return {"success": True, "text": text.strip(), "markdown": markdown.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    print(f"🧪 Test: Seite {TEST_PAGE} von {TEST_PDF}\n")
    
    pdf_path = DATA_DIR / TEST_PDF
    if not pdf_path.exists():
        print(f"❌ PDF nicht gefunden: {pdf_path}")
        return
    
    # Seite extrahieren
    temp_file = extract_page(pdf_path, TEST_PAGE)
    print(f"✅ Seite extrahiert")
    
    # Parsen
    print(f"🔄 Parse...", end=" ", flush=True)
    result = parse_pdf(temp_file)
    
    if result["success"]:
        print("✅")
        text_len = len(result["text"])
        md_len = len(result["markdown"])
        
        print(f"\n📊 Statistik:")
        print(f"   Text: {text_len:,} Zeichen")
        print(f"   Markdown: {md_len:,} Zeichen")
        
        # Ergebnisse speichern
        output = {
            TEST_PDF: [{
                "name": f"test_page_{TEST_PAGE}",
                "pages": [TEST_PAGE],
                "parsed": result
            }]
        }
        
        json_file = DATA_DIR / "test_parsed_segment.json"
        md_file = DATA_DIR / "test_markdown.md"
        
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(result["markdown"])
        
        print(f"\n✅ Gespeichert:")
        print(f"   {json_file.name}")
        print(f"   {md_file.name}")
    else:
        print(f"❌ Fehler: {result.get('error')}")
    
    # Aufräumen
    if temp_file.exists():
        temp_file.unlink()

if __name__ == "__main__":
    main()
