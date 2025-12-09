import geopandas as gpd
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, GEO


regions_shp_path = "../shapefiles/PH_Adm1_Regions.shp"
provinces_shp_path = "../shapefiles/PH_Adm2_ProvDists.shp"
municities_shp_path = "../shapefiles/PH_Adm3_MuniCities.shp"

gdf_regions = gpd.read_file(regions_shp_path, layer='PH_Adm1_Regions.shp')
gdf_provinces = gpd.read_file(provinces_shp_path, layer='PH_Adm2_ProvDists.shp')
gdf_municities = gpd.read_file(municities_shp_path, layer='PH_Adm3_MuniCities.shp')


g = Graph()
SKG = Namespace("https://sakuna.ph/")

g.bind("", SKG)

gdf_regions['geometry'] = gdf_regions.simplify(tolerance=0.001, preserve_topology=True)

# print(gpd.list_layers(regions_shp_path))

# ===================== REGIONS

for _, row in gdf_regions.iterrows():

    print(row['adm1_en'])
    print(row['adm1_psgc'])
    print("-----------------")

    name = row['adm1_en'].split(" (", 1)

    uri = URIRef(SKG[name[0].replace(" ", "_")]) # Location URI
    psgc = row['adm1_psgc']
    admLevel = "Region"

    g.add((uri, RDF.type, SKG["Region"]))
    g.add((uri, RDFS.label, Literal(row['adm1_en'])))
    g.add((uri, URIRef(SKG["psgc"]), Literal(psgc)))
    g.add((uri, URIRef(SKG["admLevel"]), Literal(admLevel)))


    # Too larege and unneccesary, just refer to an external file
    # geom_wkt = row['geometry'].wkt
    # geom_uri = URIRef(SKG[row['adm1_en'].replace(" ", "_")] + "_geom")

    # g.add((geom_uri, RDF.type, GEO.Geometry))
    # g.add((geom_uri, GEO.asWKT, Literal(geom_wkt)))

    # g.add((uri, GEO.hasGeometry, geom_uri))


# ===================== PROVINCES

for _, row in gdf_provinces.iterrows():

    if row["adm2_en"] is None:
        continue

    # print(row["adm2_en"])
    # print("-----------------")


    uri = URIRef(SKG[row['adm2_en'].replace(" ", "_")]) # Location URI
    psgc = row['adm2_psgc']
    admLevel = "Province" if row['geo_level'] == "Prov" else "District"

    g.add((uri, RDF.type, SKG["Province"]))
    g.add((uri, RDFS.label, Literal(row['adm2_en'])))
    g.add((uri, URIRef(SKG["psgc"]), Literal(psgc)))
    g.add((uri, URIRef(SKG["admLevel"]), Literal(admLevel)))

    parentRegion = Literal(row['adm1_psgc'])
    for s, p, o in g.triples((None, URIRef(SKG["psgc"]), parentRegion)):
        g.add((uri, URIRef(SKG["isPartOf"]), s))
        
    # Too larege and unneccesary, just refer to an external file

    # geom_wkt = row['geometry']
    # geom_uri = URIRef(SKG[row['adm2_en'].replace(" ", "_")] + "_geom")

    # g.add((geom_uri, RDF.type, GEO.Geometry))
    # g.add((geom_uri, GEO.asWKT, Literal(geom_wkt)))

    # g.add((uri, GEO.hasGeometry, geom_uri))

# ===================== MUNICIPALITIES/CITIES

for _, row in gdf_municities.iterrows():

    if row["adm3_en"] is None:
        continue

    # print(row["adm3_en"])
    # print("-----------------")

    uri = URIRef(SKG[row['adm3_en'].replace(" ", "_")]) # Location URI
    psgc = row['adm3_psgc']
    admLevel = "Municipality" if row['geo_level'] == "Mun" else "City"
    simURI = False
    parentProvName = ""

    # find location with similar URI, tag similar name
    similarName = g.value(predicate=RDFS.label, object=Literal(row['adm3_en']))


    # find parent province then attach province name if has similar name to URI to avoid duplication
    parentProvince = Literal(row['adm2_psgc'])
    for s, p, o in g.triples((None, URIRef(SKG["psgc"]), parentProvince)):

        if similarName:
            parentProvName = g.value(subject=s, predicate=RDFS.label)
            uri = URIRef(SKG[row['adm3_en'].replace(" ", "_") + f"_{parentProvName.replace(" ", "_")}"])

        g.add((uri, URIRef(SKG["isPartOf"]), s))

    # find parent region if city is note administratively under a province
    if row['adm2_psgc'] == row['adm3_psgc']:
        
        # parentRegion = Literal([row['adm1_psgc']])
        print(f"Finding parent region for {row['adm3_en']}, psgc: {row['adm1_psgc']}")

        parentRegion = g.value(predicate=URIRef(SKG['psgc']), object=Literal(row["adm1_psgc"]))
        print(parentRegion)
        if parentRegion:
            g.add((uri, URIRef(SKG["isPartOf"]), parentRegion))
            print(f"{row['adm3_en']} is part Of {parentRegion}")

    g.add((uri, RDF.type, SKG["Municipality"]))
    g.add((uri, RDFS.label, Literal(row['adm3_en'])))
    g.add((uri, URIRef(SKG["psgc"]), Literal(psgc)))
    g.add((uri, URIRef(SKG["admLevel"]), Literal(admLevel)))

g.serialize(destination='psgc_rdf.ttl')