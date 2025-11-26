import pandas as pd

COLUMN_MAPPING = {
    "Main Event Disaster Type": "hasType",
    "Disaster Name": "eventName",
    "Date/Period": "startDate",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Main Area/s Affected / Location": "hasLocation",  
    "Additional Perils/Disaster Sub-Type Occurences (Compound Disaster, e.g. Typhoon Haiyan = rain + wind + storm surge)": "hasSubtype",
    "PREPAREDNESS_No.ofEvacuationCenters": "evacuationCenters",
    "IMPACT_NumberofAffectedAreas_Barangays": "affectedBarangays",
    "IMPACT_Casualties_Dead_Total": "dead",
    "IMPACT_Casualties_Injured_Total": "injured",
    "IMPACT_Casualties_Missing_Total": "missing",
    "IMPACT_Affected_Families": "affectedFamilies",
    "IMPACT_Affected_Persons": "affectedPersons",
    "IMPACT_Evacuated_Families": "displacedFamilies",
    "IMPACT_Evacuated_Persons": "displacedPersons",
    "IMPACT_DamagetoProperties_Houses_Fully": "totallyDamagedHouses",
    "IMPACT_DamagetoProperties_Houses_Partially": "partiallyDamagedHouses",
    "IMPACT_DamagetoProperties_Infrastructure(inMillions)": "infraDamageAmount",
    "IMPACT_DamagetoProperties_Agriculture(inMillions)": "agricultureDamageAmount",
    "IMPACT_DamagetoProperties_Private/Commercial(inMillions)": "commercialDamageAmount",
    "IMPACT_StatusofLifelines_ElectricityorPowerSupply": "isPowerDisrupted",
    "IMPACT_StatusofLifelines_CommunicationLines": "isCommunicationDisrupted",
    


}

COLUMNS_TO_CLEAN = {
    "date": "normalize_date",
    "location": "resolve_location",
}

def load_with_tiered_headers(path):
    # Read first 3 rows as headers (0,1,2)
    df = pd.read_excel(path, header=[0, 1, 2])

    # Build merged header strings
    df.columns = [
        "_".join([str(x) for x in col if str(x) != "nan"]).strip()
        for col in df.columns
    ]

    return df

df = load_with_tiered_headers("disaster_report.xlsx")
df = df.rename(columns=COLUMN_MAPPING)