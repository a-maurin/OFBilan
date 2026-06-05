import xml.etree.ElementTree as ET

tree = ET.parse(r'c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\ref\programme\sig\modele_mise_en_page.qpt')
root = tree.getroot()

for item in root.findall('.//LayoutItem'):
    item_id = item.get('id')
    item_type = item.get('type')
    label = item.get('labelText', '')
    if item_id:
        print(f"ID: '{item_id}' | Type: {item_type} | LabelText: {label[:30]}...")
