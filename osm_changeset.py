import requests
from requests_oauthlib import OAuth2Session
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import os
import webbrowser
import json

class OSMChangeset:
  def __init__(self, dev_mode=False):
    load_dotenv()
    self.OSM_API_BASE_URL = "https://master.apis.dev.openstreetmap.org" if dev_mode else "https://www.openstreetmap.org"
    self.CLIENT_ID = os.getenv("CLIENT_ID")
    self.CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    self.REDIRECT_URI = "https://cdn.deflock.me/echo.html"
    self.AUTH_URL = f"{self.OSM_API_BASE_URL}/oauth2/authorize"
    self.TOKEN_URL = f"{self.OSM_API_BASE_URL}/oauth2/token"
    self.scope = ["write_api"]
    self.token_file = "token.json"
    self.token = self.get_access_token()

  def get_access_token(self, force_refresh=False):
    if force_refresh:
      print("Forcing refresh of access token...")
      os.remove(self.token_file)
    elif (os.path.exists(self.token_file)):
      with open(self.token_file, "r") as file:
        print("Using cached access token")
        return json.load(file)

    print("No cached access token found. Generating new token...")
    oauth = OAuth2Session(client_id=self.CLIENT_ID, redirect_uri=self.REDIRECT_URI, scope=self.scope)
    authorization_url, state = oauth.authorization_url(self.AUTH_URL)

    print("Opening browser to authorize access to OSM API...")
    webbrowser.open(authorization_url)

    # After authorizing, copy the code from the redirect URL
    authorization_response = input("Paste the authorization code here: ")
    token = oauth.fetch_token(
      self.TOKEN_URL,
      include_client_id=True,
      client_secret=self.CLIENT_SECRET,
      code=authorization_response,
    )

    with open(self.token_file, "w") as file:
      json.dump(token, file)

    return token

  def create_changeset(self):
    changeset = ET.Element("osm", version="0.6", generator="ALPR Script")
    changeset_tag = ET.SubElement(changeset, "changeset")
    ET.SubElement(changeset_tag, "tag", k="comment", v="Adding ALPR nodes")
    ET.SubElement(changeset_tag, "tag", k="created_by", v="ALPR Script")
    payload = ET.tostring(changeset, encoding="utf-8")
    headers = {"Authorization": f"Bearer {self.token['access_token']}", "Content-Type": "text/xml"}
    response = requests.put(
      f"{self.OSM_API_BASE_URL}/api/0.6/changeset/create",
      data=payload,
      headers=headers
    )
    if response.status_code == 200:
      print(f"Changeset created with ID: {response.text.strip()}")
      return response.text.strip()
    elif response.status_code == 401:
      print("Access token expired. Requesting new token and re-attempting.")
      self.token = self.get_access_token(force_refresh=True)
      return self.create_changeset()
    else:
      print(f"Failed to create changeset: {response.status_code} {response.text}")
      return None
    
  def upload_nodes(self, changeset_id, alpr_data):
    osm_change = ET.Element("osmChange", version="0.6", generator="ALPR Script")
    create = ET.SubElement(osm_change, "create")
    node_id = -1  # Start with a negative ID for new nodes
    for alpr in alpr_data:
      lat, lon = alpr["lat"], alpr["lng"]
      tags = {
        "name": alpr["name"],
        "man_made": "surveillance",
        "surveillance:type": "ALPR",
        "camera:mount": "pole",
        "camera:type": "fixed",
        "surveillance": "public",
        "surveillance:zone": "traffic",
        "manufacturer": "Flock Safety",
        "manufacturer:wikidata": "Q108485435",
      }

      # sometimes direction can be undefined on the beefeater response
      if alpr["direction"] is not None:
        tags["direction"] = str(alpr["direction"])

      # TODO: add operator from Flock Safety API
      node = ET.SubElement(create, "node", id=str(node_id), lat=str(lat), lon=str(lon), changeset=str(changeset_id))
      node_id -= 1  # Decrement the ID for the next new node
      for key, value in tags.items():
        ET.SubElement(node, "tag", k=key, v=value)
    payload = ET.tostring(osm_change, encoding="utf-8")
    headers = {"Authorization": f"Bearer {self.token['access_token']}", "Content-Type": "text/xml"}
    response = requests.post(
      f"{self.OSM_API_BASE_URL}/api/0.6/changeset/{changeset_id}/upload",
      data=payload,
      headers=headers
    )
    if response.status_code == 200:
      print("Nodes uploaded successfully.")
    elif response.status_code == 401:
      print("Access token expired. Requesting new token and re-attempting.")
      self.token = self.get_access_token(force_refresh=True)
      return self.upload_nodes(changeset_id, alpr_data)
    else:
      print(f"Failed to upload nodes: {response.status_code} {response.text}")

  def close_changeset(self, changeset_id):
    headers = {"Authorization": f"Bearer {self.token['access_token']}"}
    response = requests.put(
      f"{self.OSM_API_BASE_URL}/api/0.6/changeset/{changeset_id}/close",
      headers=headers
    )
    if response.status_code == 200:
      print(f"Changeset {changeset_id} closed successfully.")
    elif response.status_code == 401:
      print("Access token expired. Requesting new token and re-attempting.")
      self.token = self.get_access_token(force_refresh=True)
      return self.close_changeset(changeset_id)
    else:
      print(f"Failed to close changeset: {response.status_code} {response.text}")
