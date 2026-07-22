"""Fetch a single post and all its locations from the RescueMate KG."""

import json
import requests

SPARQL_ENDPOINT = "https://node-1.net.uhh.rescue-mate.de/sparql"
KEYCLOAK_URL    = "https://node-1.net.uhh.rescue-mate.de/auth"
USERNAME        = "uhh"
PASSWORD        = "vi2DieghohD8BeeM"

POST_URI = "http://rescue-mate.de/resource/c9a4bd30-452a-4f91-91e8-198c88c3695e"


def get_token() -> str:
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    r = requests.post(url, data={
        "grant_type": "password",
        "client_id":  "uhh",
        "username":   USERNAME,
        "password":   PASSWORD,
    })
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_post(token: str) -> list[dict]:
    query = f"""
        PREFIX rm:     <http://rescue-mate.de/resource/>
        PREFIX rmo:    <http://rescue-mate.de/ontology/>
        PREFIX obo:    <http://purl.obolibrary.org/obo/>
        PREFIX schema: <http://schema.org/>
        PREFIX geo:    <http://www.opengis.net/ont/geosparql#>
        PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>

        SELECT * WHERE {{
            BIND(<{POST_URI}> AS ?post)

            ?post schema:text ?text ;
                  schema:dateCreated ?date ;
                  rmo:hasDetectedCategory ?category ;
                  rm:predictedRelevance ?relevance .

            OPTIONAL {{ ?post schema:url ?url }}
            OPTIONAL {{
                ?post schema:author ?user .
                OPTIONAL {{ ?user schema:name        ?username }}
                OPTIONAL {{ ?user schema:identifier  ?user_identifier }}
                OPTIONAL {{ ?user rm:socialMediaServiceName ?platform }}
            }}
            OPTIONAL {{
                ?post rm:hasMentionedLocation ?mention_node .
                ?mention_node schema:text ?mention_text .
                OPTIONAL {{
                    ?mention_node obo:IAO_0000136 ?location .
                    ?location rm:osm_type   ?osm_type ;
                              rm:osm_id     ?osm_id ;
                              rm:latitude   ?lat ;
                              rm:longitude  ?lon ;
                              rdfs:label    ?loc_name .
                    OPTIONAL {{
                        ?location geo:hasGeometry ?geom .
                        ?geom geo:asWKT ?wkt .
                    }}
                }}
            }}
        }}
    """
    r = requests.post(
        SPARQL_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/sparql-results+json",
        },
        data={"query": query},
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def val(row: dict, key: str) -> str | None:
    return row[key]["value"] if key in row else None


if __name__ == "__main__":
    print("Authenticating...")
    token = get_token()

    print(f"Fetching post {POST_URI}\n")
    rows = fetch_post(token)

    if not rows:
        print("No results returned.")
        exit(1)

    first = rows[0]
    print("=== POST ===")
    print(f"  text:      {val(first, 'text')}")
    print(f"  date:      {val(first, 'date')}")
    print(f"  url:       {val(first, 'url')}")
    print(f"  platform:  {val(first, 'platform')}")
    print(f"  username:  {val(first, 'username') or val(first, 'user_identifier')}")
    print(f"  relevance: {val(first, 'relevance')}")
    categories = {val(r, 'category') for r in rows if val(r, 'category')}
    print(f"  categories: {categories}")

    print("\n=== LOCATIONS ===")
    seen_mentions: set[str] = set()
    for row in rows:
        mention = val(row, 'mention_text')
        if not mention or mention in seen_mentions:
            continue
        seen_mentions.add(mention)

        print(f"\n  mention:   '{mention}'")
        print(f"  loc_name:  {val(row, 'loc_name')}")
        print(f"  osm_type:  {val(row, 'osm_type')}")
        print(f"  osm_id:    {val(row, 'osm_id')}")
        print(f"  lat:       {val(row, 'lat')}")
        print(f"  lon:       {val(row, 'lon')}")
        wkt = val(row, 'wkt')
        if wkt:
            preview = wkt[:120] + ("..." if len(wkt) > 120 else "")
            print(f"  wkt:       {preview}")
        else:
            print(f"  wkt:       (none)")