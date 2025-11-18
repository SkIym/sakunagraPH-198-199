import pdfplumber
import pandas as pd

# --- FILE NAMES SAMPLE ---
pdf_file = "NDRRMC/NDRRMC/Breakdown_Final_Report_for_Severe_Tropical_Storm_MARING_.pdf"
pdf_file = "NDRRMC/NDRRMC/_Breakdown__Final_Report_for_Taal_Volcano_Eruption_2020.pdf"

# How far up to look for a title (in points).
HEADER_SEARCH_DISTANCE = 80  # This is to search for header titles before tables

print(f"Processing {pdf_file}...")
all_tables = []
current_title = "Unknown_Section" # Default start since no tables have been read

with pdfplumber.open(pdf_file) as pdf:
    for i, page in enumerate(pdf.pages):
        # 1. Find tables based on LINES (fixes alignment)
        tables_found = page.find_tables(
            table_settings={
                "vertical_strategy": "lines", 
                "horizontal_strategy": "lines",
                "snap_tolerance": 5,
            }
        )
        
        if tables_found:
            print(f"Page {i+1}: Found {len(tables_found)} table(s)")
        
        for table_obj in tables_found:
            # 2. Get the table's location
            x0, top, x1, bottom = table_obj.bbox
            
            # 3. Define the "Header Search Area" above the table
            search_top = max(0, top - HEADER_SEARCH_DISTANCE)
            
            try:
                header_crop = page.crop((0, search_top, page.width, top))
                header_text = header_crop.extract_text()
            except ValueError:
                header_text = ""

            # 4. Determine the Title
            if header_text and header_text.strip():
                lines = [line.strip() for line in header_text.split('\n') if line.strip()]
                if lines:
                    potential_title = lines[-1]
                    # Check if it looks like a title (e.g. Uppercase or short)
                    if potential_title.isupper() or len(potential_title) < 100:
                        current_title = potential_title
            else:
                pass   # If no text found above, assume continuation -> Keep current_title

            # 5. Extract the actual data
            table_data = table_obj.extract()
            if table_data:
                df = pd.DataFrame(table_data)
                
                # Clean up: Drop rows that are completely empty
                df = df.dropna(how='all')
                
                # Add our tracking columns
                df['Detected_Title'] = current_title
                df['Page_Num'] = i + 1
                
                all_tables.append(df)

# --- SAVE RESULTS ---
if all_tables:
    final_df = pd.concat(all_tables, ignore_index=True)
    
    # --- REORDER COLUMNS ---
    # We create a list of columns starting with Page_Num and Detected_Title
    # Then we add whatever other columns exist in the data
    cols = ['Page_Num', 'Detected_Title'] + [c for c in final_df.columns if c not in ['Page_Num', 'Detected_Title']]
    final_df = final_df[cols]
    
    output_filename = "_Breakdown__Final_Report_for_Taal_Volcano_Eruption_2020.csv"
    final_df.to_csv(output_filename, index=False)
    print(f"\n🎉 SUCCESS! Processed {len(pdf.pages)} pages.")
    print(f"Extracted {len(final_df)} rows.")
    print(f"Data saved to: {output_filename}")
else:
    print("No tables found. Check if the PDF actually has gridlines.")
