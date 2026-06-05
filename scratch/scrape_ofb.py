import urllib.request
import json

url = 'https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration/records?limit=10&q=%22Office+fran%C3%A7ais+de+la+biodiversit%C3%A9%22+%22Service+d%C3%A9partemental%22'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    results = data.get('results', [])
    print(f"Total count: {data.get('total_count', 0)}")
    for r in results:
        nom = r.get('nom', '')
        adresse = r.get('adresse', '')
        print(f"NOM: {nom}")
        print(f"ADRESSE: {adresse}")
        print("---")
except Exception as e:
    print('Error:', e)
