import requests
import urllib.parse
import webbrowser

def get_overpass_turbo_link(conflicting_node_ids):
  ids_query = "".join([f"node({node_id});" for node_id in conflicting_node_ids])
  query = f"""
  [out:json];
  (
    {ids_query}
  );
  out body;
  """
  encoded_query = urllib.parse.quote(query)
  return f"https://overpass-turbo.eu/?Q={encoded_query}&R"

def get_bounding_box_for_nodes(nodes):
  min_lat = 90
  max_lat = -90
  min_lon = 180
  max_lon = -180

  for node in nodes:
    min_lat = min(min_lat, node['lat'])
    max_lat = max(max_lat, node['lat'])
    min_lon = min(min_lon, node['lng'])
    max_lon = max(max_lon, node['lng'])

  return (min_lat, min_lon, max_lat, max_lon)

def overpass_request(query):
  url = "http://overpass-api.de/api/interpreter"
  response = requests.get(
    url, params={"data": query}, headers={"User-Agent": "DeFlock/1.0"}
  )
  response.raise_for_status()
  return response.json()["elements"]

def get_alprs_in_bounding_box(bbox):
  min_lat, min_lon, max_lat, max_lon = bbox
  query = f"""
  [out:json][bbox:{min_lat},{min_lon},{max_lat},{max_lon}];
  node["man_made"="surveillance"]["surveillance:type"="ALPR"];
  out body;
  """
  return overpass_request(query)

def detect_duplicates(nodes):
  conflicting_node_ids = set()
  conflicting_imported_names = set()

  bbox = get_bounding_box_for_nodes(nodes)
  alprs = get_alprs_in_bounding_box(bbox)

  for node in nodes:
    for alpr in alprs:
      if (
        abs(node['lat'] - alpr['lat']) < 0.0001 and
        abs(node['lng'] - alpr['lon']) < 0.0001
      ):
        conflicting_node_ids.add(alpr['id'])
        conflicting_imported_names.add(node['name'])

  print(f"\033[1m\033[91mFound {len(conflicting_node_ids)} conflicting nodes in OSM.\033[0m")
  print(f"Detected as Duplicates:")
  for name in conflicting_imported_names:
    print(f"  - {name}")
  
  input("\033[1mPress Enter to view potential duplicates in OSM...\033[0m")
  webbrowser.open(get_overpass_turbo_link(conflicting_node_ids))

  return conflicting_node_ids
