import re
import pandas as pd
from dateutil.parser import parse

COLUMN_MAPPING = {
    "Main Event Disaster Type": "hasType",
    "Disaster Name": "eventName",
    "Date/Period": "date",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Main Area/s Affected / Location": "hasLocation",  
    "Additional Perils/Disaster Sub-Type Occurences (Compound Disaster, e.g. Typhoon Haiyan = rain + wind + storm surge)": "hasSubtype",
    "PREPAREDNESS_Announcements_Warnings Released / Status Alert or Alert/ State of Calamity": "declarationOfCalamity",
    "PREPAREDNESS_Evacuation_LGU Evacuation Plan": "evacuationPlan",
    "PREPAREDNESS_Evacuation_No. of Evacuation Centers": "evacuationCenters",
    "PREPAREDNESS_Rescue_Rescue Operating Unit/Team": "rescueUnit",
    "PREPAREDNESS_Rescue_Available Rescue Equipment": "rescueEquipment",
    "IMPACT_Number of Affected Areas_Barangays": "affectedBarangays",
    "IMPACT_Casualties_Dead_Total": "dead",
    "IMPACT_Casualties_Injured_Total": "injured",
    "IMPACT_Casualties_Missing_Total": "missing",
    "IMPACT_Affected_Families": "affectedFamilies",
    "IMPACT_Affected_Persons": "affectedPersons",
    "IMPACT_Evacuated_Families": "displacedFamilies",
    "IMPACT_Evacuated_Persons": "displacedPersons",
    "IMPACT_Damages to Properties_Houses_Fully": "totallyDamagedHouses",
    "IMPACT_Damages to Properties_Houses_Partially": "partiallyDamagedHouses",
    "IMPACT_Damages to Properties_Infrastructure (in Millions)": "infraDamageAmount",
    "IMPACT_Damages to Properties_Agriculture (in Millions)": "agricultureDamageAmount",
    "IMPACT_Damages to Properties_Private/Commercial (in Millions)": "commercialDamageAmount",
    "IMPACT_Status of Lifelines_Electricity or Power Supply": "powerAffected",
    "IMPACT_Status of Lifelines_Communication Lines": "communicationAffected",
    "IMPACT_Status of Lifelines_Transportation_Roads and Bridges": "roadAndBridgesAffected",
    "IMPACT_Status of Lifelines_Transportation_Seaports": "seaportsAffected",
    "IMPACT_Status of Lifelines_Transportation_Airports": "airportsAffected",
    "IMPACT_Status of Lifelines_Water_Dams and other Reservoirs": "areDamsAffected",
    "IMPACT_Status of Lifelines_Water_Tap": "isTapAffected",
    "RESPONSE AND RECOVERY_Allocated Funds for the Affected Area/s": "allocatedFunds",
    "RESPONSE AND RECOVERY_NGO-LGU Support Units Present": "agencyLGUsPresent",
    "RESPONSE AND RECOVERY_International Organizations Present": "internationalOrgsPresent",
    "RESPONSE AND RECOVERY_Amount of Donation from International Organizations (including local NGOs)": "amoungNGOs",
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Canned Goods, Rice, etc._Cost": "itemCostGoods",    # itemTypeOrNeeds: Canned Goods, Rice
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Canned Goods, Rice, etc._Quantity": "itemQtyGoods", # itemTypeOrNeeds: Canned Goods, Rice
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Water_Cost": "itemCostWater",    # itemTypeOrNeeds: Water
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Water_Quantity": "itemQtyWater", # itemTypeOrNeeds: Water
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Clothing_Cost": "itemCostClothing",    # itemTypeOrNeeds: Clothing
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Clothing_Quantity": "itemQtyClothing", # itemTypeOrNeeds: Clothing
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Medicine_Cost": "itemCostMedicine",    # itemTypeOrNeeds: Medicine
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Medicine_Quantity": "itemQtyMedicine", # itemTypeOrNeeds: Medicine
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Items Not Specified (Cost)": "itemCostOthers1", # itemTypeOrNeeds: Others
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Total Cost": "itemCostOthers2", # itemTypeOrNeeds: Others
    "RESPONSE AND RECOVERY_Supply of Relief Goods_Total Cost": "itemCostOthers2",
    "RESPONSE AND RECOVERY_Search, Rescue and Retrieval": "srrDone",
    "RESPONSE AND RECOVERY_City-Municipal Policy Changes": "policyChanges",
    "RESPONSE AND RECOVERY_Cost of Structure Built post-disaster": "postStructureCost",
    "RESPONSE AND RECOVERY_Post-Disaster Training": "postTraining",
    "REFERENCES (Authors. Year. Title. Journal/Book/Newspaper. Publisher, Place published. Pages. Website, Date Accessed)": "reference",
    "Detailed Description of Disaster Event": "otherDescription"

}

COLUMNS_TO_CLEAN = {
    "date": "normalize_date",
    "location": "resolve_location",
}

DASH = r"[-–—]"   # hyphen, en dash, em dash

def normalize_one_date(text):
    """Parse a single date fragment → YYYY-MM-DD or None."""
    try:
        return parse(text, dayfirst=False).strftime("%Y-%m-%d")
    except:
        try:
            return parse(text, dayfirst=True).strftime("%Y-%m-%d")
        except:
            return None

def clean_date_range(value):
    """
    Handles normalized dates, date ranges, ambiguous ranges, 
    long-form dates, month ranges, year ranges, etc.
    """

    if pd.isna(value):
        return (None, None)

    text = str(value).strip()

    # --------------------------------------------------------
    # ⚡ CASE 0 — Already normalized machine date "YYYY-MM-DD"
    # --------------------------------------------------------
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return (text, text)

    # machine timestamp "YYYY-MM-DD HH:MM:SS"
    if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$", text):
        only_date = text.split()[0]
        return (only_date, only_date)

    # strip known bad timezone names
    text = re.sub(r"\b[A-Z]{2,4}\b", "", text).strip()

    # strip time
    text = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM|am|pm)?\b", "", text).strip()
    
    # --------------------------------------------------------
    # 1: YEAR RANGE: "1918–1919"
    # --------------------------------------------------------
    yr_rng = re.match(rf"^\s*(\d{{4}})\s*{DASH}\s*(\d{{4}})\s*$", text)
    if yr_rng:
        y1, y2 = yr_rng.groups()
        return (f"{y1}-01-01", f"{y2}-12-31")

    # --------------------------------------------------------
    # 2: LONG DATE RANGE:  
    #    "August 10, 2008 – July 14, 2009"
    # --------------------------------------------------------
    long_range = re.match(
        rf"^\s*([A-Za-z]+\s+\d{{1,2}},?\s*\d{{4}})\s*{DASH}\s*([A-Za-z]+\s+\d{{1,2}},?\s*\d{{4}})\s*$",
        text
    )
    if long_range:
        left, right = long_range.groups()
        return (normalize_one_date(left), normalize_one_date(right))

    # --------------------------------------------------------
    # 3: MONTH–MONTH YEAR: "April–June 1957"
    # --------------------------------------------------------
    my_rng = re.match(rf"^\s*([A-Za-z]+)\s*{DASH}\s*([A-Za-z]+)\s+(\d{{4}})", text)
    if my_rng:
        m1, m2, year = my_rng.groups()
        start = normalize_one_date(f"1 {m1} {year}")
        end   = normalize_one_date(f"1 {m2} {year}")

        if end:
            end = (pd.to_datetime(end) + pd.tseries.offsets.MonthEnd()).strftime("%Y-%m-%d")
        return (start, end)
    
    # --------------------------------------------------------
    # 3: MONTH–MONTH YEAR: "April–June 1957"
    # --------------------------------------------------------
    my_rng = re.match(rf"^\s*([A-Za-z]+)\s*{DASH}\s*([A-Za-z]+)\s+(\d{{4}})", text)
    if my_rng:
        m1, m2, year = my_rng.groups()
        start = normalize_one_date(f"1 {m1} {year}")
        end   = normalize_one_date(f"1 {m2} {year}")

        if end:
            end = (pd.to_datetime(end) + pd.tseries.offsets.MonthEnd()).strftime("%Y-%m-%d")
        return (start, end)
    
    # --------------------------------------------------------
    # 3.5: MONTH YEAR–MONTH YEAR: "April 1965–June 1957"
    # --------------------------------------------------------
    my_rng = re.match(rf"^\s*([A-Za-z]+)\s*(\d{{4}})\s*{DASH}\s*([A-Za-z]+)\s+(\d{{4}})", text)
    if my_rng:
        m1, y1, m2, y2 = my_rng.groups()
        start = normalize_one_date(f"1 {m1} {y1}")
        end   = normalize_one_date(f"1 {m2} {y2}")

        if end:
            end = (pd.to_datetime(end) + pd.tseries.offsets.MonthEnd()).strftime("%Y-%m-%d")
        return (start, end)

    # --------------------------------------------------------
    # 4: DAY–DAY MONTH YEAR (2–7 July 2001)
    # --------------------------------------------------------
    day_month_year = re.match(
        rf"^\s*(\d{{1,2}})\s*{DASH}\s*(\d{{1,2}})\s+([A-Za-z]+)\s*,?\s*(\d{{4}})\s*$",
        text
    )
    if day_month_year:
        d1, d2, month, year = day_month_year.groups()
        return (
            normalize_one_date(f"{d1} {month} {year}"),
            normalize_one_date(f"{d2} {month} {year}")
        )

    # --------------------------------------------------------
    # 5: MONTH DAY–DAY YEAR (Nov 12–15 2003)
    # --------------------------------------------------------
    month_day_day = re.match(
        rf"^\s*([A-Za-z]+)\s+(\d{{1,2}})\s*{DASH}\s*(\d{{1,2}})\s*,?\s*(\d{{4}})\s*$",
        text
    )
    if month_day_day:
        month, d1, d2, year = month_day_day.groups()
        return (
            normalize_one_date(f"{d1} {month} {year}"),
            normalize_one_date(f"{d2} {month} {year}")
        )

    # --------------------------------------------------------
    # 6: Month Day – Month Day Year  
    #    ("August 31 – September 4, 1984")
    # --------------------------------------------------------
    month_to_month = re.match(
        rf"^\s*([A-Za-z]+\s+\d{{1,2}})\s*{DASH}\s*([A-Za-z]+\s+\d{{1,2}})\s*,?\s*(\d{{4}})\s*$",
        text,
    )
    if month_to_month:
        left, right, year = month_to_month.groups()
        return (
            normalize_one_date(f"{left} {year}"),
            normalize_one_date(f"{right} {year}")
        )

    # --------------------------------------------------------
    # 7: YEAR ONLY
    # --------------------------------------------------------
    if re.match(r"^\d{4}$", text):
        year = text
        return (f"{year}-01-01", f"{year}-12-31")
    
    # --------------------------------------------------------
    # 8: SINGLE DATE (fallback)
    # --------------------------------------------------------
    single = normalize_one_date(text)
    if single:
        return (single, single)
    
    

    return (None, None)


def load_with_tiered_headers(path):
    """
    Load XLSX with 3–4 tier headers.
    Automatically stops merging deeper levels when columns become 'Unnamed' (merged rows problem).
    """
    df = pd.read_excel(path, header=[3,4,5,6])

    new_cols = []
    for col_tuple in df.columns:

        cleaned = []
        for level in col_tuple:
            s = str(level).strip()

            if s.lower().startswith("unnamed") or s == "" or s == "nan":
                break  

            cleaned.append(s)

        merged = "_".join(cleaned)

        new_cols.append(merged)

    df.columns = new_cols
    return df

df = load_with_tiered_headers("../../data/geog-archive-cleaned.xlsx")
df = df.rename(columns=COLUMN_MAPPING)

# print("\n=== XLSX column names ===")
# for col in df.columns:
#     print(col)

df = df[list(COLUMN_MAPPING.values())]
df = df.dropna(how='all')
df = df.dropna(axis=1, how='all')
df = df.dropna(subset=['date'])

if "date" in df.columns:
    df[["startDate", "endDate"]] = df["date"].apply(lambda v: pd.Series(clean_date_range(v)))

df = df.dropna(subset=['startDate'])

df.to_csv('gda.csv')