import requests
import sys
import re
import os
import json
from osm_changeset import OSMChangeset
import overpass
import webbrowser

def get_flock_camera_details(agency_uuid, use_cache=False):
  if (use_cache):
    cache_file_path = os.path.join(os.getcwd(), f"{agency_uuid}.json")
    if os.path.isfile(cache_file_path):
      print("Using cached response")
      with open(cache_file_path, 'r') as cache_file:
        return json.load(cache_file)

  flock_details_url_prefix = "https://beefeater.flocksafety.com/api/v1/public/deployments/"
  response = requests.get(flock_details_url_prefix + agency_uuid)
  if response.status_code == 200:
    if (use_cache):
      print("Cache miss. Caching response")
      with open(f"{agency_uuid}.json", 'w') as cache_file:
        json.dump(response.json(), cache_file)
    return response.json()
  else:
    return None

def get_agency_uuid():
  flock_planner_url_regex = r"^https:\/\/planner.flocksafety.com\/public\/([a-z0-9-]+)$"
  flock_planner_url = None

  if len(sys.argv) > 1:
    flock_planner_url = sys.argv[1]
    is_valid_url = re.match(flock_planner_url_regex, flock_planner_url)
    if (not is_valid_url):
      print("Invalid Flock Planner URL")
      sys.exit(1)
  else:
    print("Usage: python import.py \"<flock-planner-url>\"")
    sys.exit(1)

  agency_uuid = re.search(flock_planner_url_regex, flock_planner_url).group(1)
  return agency_uuid

def convert_to_north_reference(angle):
    north_angle = (90 - angle) % 360
    return round(north_angle)

if (__name__ == "__main__"):  
  is_dev = os.environ.get('ENV') == 'dev'
  print(f"Running in {'dev' if is_dev else 'prod'} environment")

  if not is_dev:
    ack = input("\033[1mWARNING: This script will make changes to OSM. Are you sure you want to continue? [y/N]:\033[0m ")
    if ack.lower() != 'y':
      print("User did not approve. Exiting.")
      sys.exit(1)

  agency_uuid = get_agency_uuid()
  flock_camera_details = get_flock_camera_details(agency_uuid, use_cache=is_dev)

  resolved_cameras = flock_camera_details['resolvedCameras']
  alpr_nodes = []

  for camera in resolved_cameras:
    if camera['status'] == 'Decommissioned':
      continue

    alpr_nodes.append({
      "name": camera['name'],
      "lat": camera['lat'],
      "lng": camera['lng'],
      "direction": convert_to_north_reference(camera['rotationAngle']),
      "status": camera['status'],
    })

  dupes = overpass.detect_duplicates(alpr_nodes)

  if len(dupes) > 0:
    cont = input("\033[1mOnce you've confirmed there are no duplicates, do you want to continue? [y/N]:\033[0m ")
    if cont.lower() != 'y':
      print("User did not approve. Exiting.")
      sys.exit(1)

  cs = OSMChangeset(dev_mode=is_dev)

  changeset_id = cs.create_changeset()
  if changeset_id is None:
    print("Failed to create changeset")
    sys.exit(1)

  cs.upload_nodes(changeset_id, alpr_nodes)

  input("\033[1mPlease review changes before submitting. Press Enter to open changeset in browser.\033[0m")
  changeset_url = f"{cs.OSM_API_BASE_URL}/browse/changeset/{changeset_id}"
  webbrowser.open(changeset_url)

  does_approve = input("\033[1mDo you approve these changes? [y/N]:\033[0m ")

  if does_approve.lower() == 'y':
    cs.close_changeset(changeset_id)
  else:
    print("User did not approve changeset. Not submitting.")
