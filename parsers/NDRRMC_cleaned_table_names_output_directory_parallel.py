import os
import pdfplumber
import pandas as pd
import re
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed

# --------------------------
# CONFIGURATION
# --------------------------

INPUT_FOLDER = "NDRRMC/NDRRMC"            # folder that contains PDFs
OUTPUT_FOLDER = "NDRRMC_PARSED_VER1"    # where parsed folders will be created
FOLDER_LENGTH = 0
HEADER_SEARCH_DISTANCE = 80
ALIGNMENT_TOLERANCE = 5

@dataclass
class Event:
    eventName : str = ""
    startDate : str = ""
    endDate : str = ""
    lastUpdateDate : str = ""
    reportName : str = ""
    recordedBy : str = "NDRRMC"
    obtainedDate : str = ""
    reportLink : str = ""

# -----------------------------------------------------------------------
# Helper function → sanitize titles into safe filenames → update LastUpdateDate
# -----------------------------------------------------------------------
def get_lastUpdateDateTime(event, lastUpdateDateTime):
    # Possible formats (with and without time)
    formats = [
        "%b %d, %Y",        # e.g. Nov 10, 2025
        "%B %d %Y",         # e.g. November 10 2025
        "%B %d, %Y %H:%M",  # e.g. December 08, 2023 08:00
        "%b %d, %Y %H:%M"   # e.g. Nov 10, 2025 08:00
    ]
    parsed_date = None
    for fmt in formats:
        try:
            FormatDate = datetime.strptime(lastUpdateDateTime, fmt)
            event.lastUpdateDateTime = FormatDate.strftime("%Y-%m-%d %H:%M:%S")             # Save in ISO format (YYYY-MM-DD HH:MM:SS)
            parsed_date = True
            break
        except ValueError:
            continue

    # If none of the formats matched, keep the raw string
    if not parsed_date:
        event.lastUpdateDate = lastUpdateDateTime

def clean_tablename(event: Event, table_title: str) -> str:
    # Get the table title for csv
    if not table_title:
        return "Unknown_Section"
    title_split = table_title.split("as of")
    # print(title_split)
    table_title = title_split[0]
    table_title = table_title.strip().replace(" ", "_").lower()

    # Update the lastUpdateDate for Event    
    lastUpdateDate = title_split[1].replace("(","").replace(")","").removeprefix(" ")
    get_lastUpdateDateTime(event, lastUpdateDate )
    # formats = ["%b %d, %Y", "%B %d %Y"] # possible date formats in the pdf
    # for fmt in formats:
    #     try:
    #         FormatDate = datetime.strptime(lastUpdateDate, fmt)
    #         event.lastUpdateDate = FormatDate.strftime("%Y-%m-%d")
    #     except ValueError:
    #         event.lastUpdateDate = lastUpdateDate 
    
    return "".join(c for c in table_title if c.isalnum() or c in "._-")


# Dictionary of replacements for normalization
abbrev_map = {
    "Tropical Storm": "TS",
    "Typhoon": "TY",
    "Tropical Cyclone": "TC",
    "Situational Report": "SitRep",
    "Southwest Monsoon": "SWM",
    "Low Pressure Area": "LPA",
    "Terminal Report": "TR",
    "Final Report": "FR"
}

def normalize_subject(text):
    for full, abbr in abbrev_map.items():
        text = re.sub(full, abbr, text, flags=re.IGNORECASE)
    return text

def clean_filename(filename):
    name = filename.replace(".pdf", "") # Remove extension
    name = re.sub(r"(Breakdown|Final_Report|SitRep|Situational_Report|Terminal_Report|Table)", "", name, flags=re.IGNORECASE) # Remove common prefixes
    name = name.replace("_", " ") # Replace underscores with spaces
    
    # Extract after "for"
    match = re.search(r"for (.+)", name, flags=re.IGNORECASE)
    if match:
        subject = match.group(1).strip()
    else:
        subject = name.strip()
    
    # Remove trailing "Breakdown" or similar and "the"
    subject = re.sub(r"(Breakdown.*)$", "", subject, flags=re.IGNORECASE).strip().replace("the","").replace(" -", "").removeprefix(" ").replace("(","").replace(")","")
    subject = normalize_subject(subject) # Normalize abbreviations
    
    return subject

def generate_json(event, output_dir):
    event_dict = asdict(event)     # Convert to dictionary
    metadata = {                   # Separate metadata vs. source
        "eventName": event.eventName,
        "startDate": event.startDate,
        "endDate": event.endDate
    }
    source = {k: v for k, v in event_dict.items() if k not in metadata}

    # Save JSON files in the correct path
    metadata_path = os.path.join(output_dir, "metadata.json")
    source_path = os.path.join(output_dir, "source.json")

    # Save to JSON files
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    with open(source_path, "w") as f:
        json.dump(source, f, indent=4)

    print(f"✔ Saved metadata: {metadata_path}")
    print(f"✔ Saved source: {source_path}")

# -----------------------------------------------------------------------
# Detect alignment + casing of a cell in a table
# -----------------------------------------------------------------------
def get_text_alignment_and_case(page, cell_bbox):
    """Analyze the text geometry and casing inside a table cell."""
    if not cell_bbox:
        return None, None, ""

    # Crop around the cell
    try:
        cell_crop = page.crop(cell_bbox)
        words = cell_crop.extract_words()
    except ValueError:
        return None, None, ""

    if not words:
        return None, None, ""

    # join words into a full text string
    text = " ".join(w["text"] for w in words).strip()

    # cell geometry
    cell_x0, _, cell_x1, _ = cell_bbox
    cell_width = cell_x1 - cell_x0

    # text bounding box
    text_x0 = min(w["x0"] for w in words)
    text_x1 = max(w["x1"] for w in words)

    left_margin = text_x0 - cell_x0
    right_margin = cell_x1 - text_x1

    # Determine alignment
    alignment = "UNKNOWN"
    if abs(left_margin - right_margin) < ALIGNMENT_TOLERANCE:
        alignment = "CENTER"
    elif left_margin < ALIGNMENT_TOLERANCE * 2:
        alignment = "LEFT"
    elif right_margin < ALIGNMENT_TOLERANCE * 2:
        alignment = "RIGHT"

    # Determine casing
    case_type = "MIXED"
    if text.isupper():
        case_type = "UPPER"
    elif text.istitle():
        case_type = "TITLE"

    return alignment, case_type, text


# -----------------------------------------------------------------------
# MAIN PROCESSOR FOR ONE PDF
# -----------------------------------------------------------------------
def process_pdf(pdf_event = Event, file_counter = int, pdf_path = str):
    print(f"\n📄{file_counter} Processing PDF: {pdf_path}")

    # folder name = base file name without .pdf
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_dir = os.path.join(OUTPUT_FOLDER, pdf_event.eventName)
    
    # create the folder for this specific PDF
    os.makedirs(output_dir, exist_ok=True)

    current_title = "Unknown_Section"
    all_tables_buffer = {}  # title → list of row dicts

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):

            # detect table structures
            tables_found = page.find_tables(
                {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 5,
                }
            )

            if not tables_found:
                continue  # skip pages with no tables

            for table_obj in tables_found:
                # extract possible header title above this table
                x0, top, x1, bottom = table_obj.bbox

                try:
                    header_text = page.crop(
                        (0, max(0, top - HEADER_SEARCH_DISTANCE), page.width, top)
                    ).extract_text() or ""

                    lines = [l.strip() for l in header_text.split("\n") if l.strip()]
                    if lines:
                        potential_title = lines[-1]
                        if potential_title.isupper() or len(potential_title) < 100:
                            current_title = clean_tablename(pdf_event, potential_title)
                except Exception:
                    pass

                # prepare buffer for this title if not existing
                if current_title not in all_tables_buffer:
                    all_tables_buffer[current_title] = []

                # extract rows
                extracted_rows = table_obj.extract()
                row_geometries = table_obj.rows

                # state variables for hierarchy
                current_region = None
                current_province = None
                current_muni = None
                current_barangay = None

                for row_obj, row_text in zip(row_geometries, extracted_rows):
                    if not row_obj.cells:
                        continue

                    loc_bbox = row_obj.cells[0]
                    align, casing, text = get_text_alignment_and_case(page, loc_bbox)

                    # classify hierarchical location levels
                    if text and "REGION" in text and "PROVINCE" in text:
                        continue

                    if text:
                        if align == "CENTER" and casing == "UPPER":
                            current_region = text
                            current_province = None
                            current_muni = None
                            current_barangay = None

                        elif align == "LEFT" and casing == "UPPER":
                            current_province = text
                            current_muni = None
                            current_barangay = None

                        elif align == "CENTER" and casing != "UPPER":
                            current_muni = text
                            current_barangay = None

                        elif align == "RIGHT":
                            current_barangay = text

                    # build row dict
                    rd = {
                        "Page": page_index,
                        "Region": current_region,
                        "Province": current_province,
                        "City_Muni": current_muni,
                        "Barangay": current_barangay,
                    }

                    # add column text
                    for col_idx, cell in enumerate(row_text):
                        if col_idx == 0:
                            continue
                        rd[f"Column_{col_idx}"] = (cell or "").replace("\n", " ").strip()

                    # add to table buffer
                    all_tables_buffer[current_title].append(rd)

    # ------------------------------
    # SAVE ALL TABLES FOR THIS PDF
    # ------------------------------

    for title, rows in all_tables_buffer.items():
        if not rows:
            continue

        df = pd.DataFrame(rows)

        csv_path = os.path.join(output_dir, f"{title}.csv")
        df.to_csv(csv_path, index=False)

        print(f"   ✔ Saved table: {csv_path}")
    
    generate_json(pdf_event, output_dir)



# -----------------------------------------------------------------------
# PROCESS ALL PDFS IN INPUT FOLDER
# -----------------------------------------------------------------------
def process_all_pdfs():
    print("🔎 Scanning folder for PDFs...")

    FILES =  os.listdir(INPUT_FOLDER)
    FOLDER_LENGTH = len(FILES)
    file_counter = 0
    for filename in FILES:
        if filename.lower().endswith(".pdf"):
            file_counter += 1
            fullpath = os.path.join(INPUT_FOLDER, filename)
            event = Event(reportName = filename, eventName = clean_filename(filename))
            process_pdf(event, file_counter, fullpath)

    print(f"\n🎉 Finished parsing all PDFs ! {file_counter}/{FOLDER_LENGTH}")

def process_all_pdfs_parallel():
    print("🔎 Scanning folder for PDFs...")

    FILES = os.listdir(INPUT_FOLDER)
    pdf_files = [f for f in FILES if f.lower().endswith(".pdf")]
    FOLDER_LENGTH = len(pdf_files)

    # Use ProcessPoolExecutor for parallel processing
    with ProcessPoolExecutor() as executor:
        # Submit tasks
        futures = {
            executor.submit(
                process_pdf, 
                Event(reportName=filename, eventName=clean_filename(filename)), 
                idx+1, 
                os.path.join(INPUT_FOLDER, filename)
            ): filename
            for idx, filename in enumerate(pdf_files)
        }

        # Collect results
        for future in as_completed(futures):
            filename = futures[future]
            try:
                future.result()
                print(f"✔ Finished {filename}")
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")

    print(f"\n🎉 Finished parsing all PDFs ! {FOLDER_LENGTH}/{FOLDER_LENGTH}")

# -----------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------
if __name__ == "__main__":
    # process_all_pdfs_parallel()
    process_all_pdfs_parallel()
