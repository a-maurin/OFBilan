import os

def main():
    logo_svg_path = r"ref/hors_programme/logos/logo_ecusson_chasseur.svg"
    banner_svg_path = r"ref/hors_programme/logos/bandeau_ofbilan.svg"
    
    if not os.path.exists(logo_svg_path):
        print(f"Error: {logo_svg_path} not found.")
        return
        
    print("Reading logo SVG...")
    with open(logo_svg_path, "r", encoding="utf-8") as f:
        logo_content = f.read()
        
    # Extract everything inside the <svg> tag of the logo
    # Find definition blocks and paths
    defs_start = logo_content.find("<defs>")
    defs_end = logo_content.find("</defs>") + len("</defs>")
    defs_str = logo_content[defs_start:defs_end] if defs_start != -1 else ""
    
    # Get all elements except the main <svg> outer shell and defs
    elements_start = logo_content.find("</defs>") + len("</defs>") if defs_start != -1 else logo_content.find(">") + 1
    elements_end = logo_content.rfind("</svg>")
    elements_str = logo_content[elements_start:elements_end].strip()
    
    # Dimensions based on the generate_banner.py design:
    # Canvas: 1200 x 300
    # Logo height: 220, vertically centered at y = 40 (y_offset = (300 - 220) / 2)
    # Original logo viewBox is 0 0 880 1182 (w=880, h=1182)
    # scale = 220 / 1182 = 0.18612521
    scale = 220.0 / 1182.0
    logo_x = 40.0
    logo_y = 40.0
    
    # Calculate title text offset (x = logo_x + logo_w + 40)
    # logo_w = 880 * scale = 163.79
    logo_w = 880.0 * scale
    text_x = logo_x + logo_w + 40.0
    
    # Segoe UI text width metrics estimation from generate_banner.py
    # 'OFBilan' at size 80 is ~290px wide
    title_w = 290.0
    sep_x = text_x + title_w + 30.0
    sub_x = sep_x + 30.0
    
    # Build the combined SVG
    svg_elements = []
    svg_elements.append(defs_str)
    
    # Group the logo elements with scaling and translation
    svg_elements.append(f'  <!-- Scaled Logo -->')
    svg_elements.append(f'  <g transform="translate({logo_x:.2f}, {logo_y:.2f}) scale({scale:.8f})">')
    svg_elements.append(elements_str)
    svg_elements.append(f'  </g>')
    
    # Title Text 'OFBilan' (Font: Segoe UI Bold, color #2c406e, size 80px)
    svg_elements.append(f'  <!-- Title -->')
    svg_elements.append(f'  <text x="{text_x:.2f}" y="170" font-family="Segoe UI, sans-serif" font-weight="bold" font-size="80" fill="#2c406e">OFBilan</text>')
    
    # Vertical Separator (color #86b872, stroke-width 4px)
    svg_elements.append(f'  <!-- Separator -->')
    svg_elements.append(f'  <line x1="{sep_x:.2f}" y1="70" x2="{sep_x:.2f}" y2="230" stroke="#86b872" stroke-width="4" />')
    
    # Subtitle Text (Font: Segoe UI Regular, color #2c406e, size 44px, line-height ~50px)
    svg_elements.append(f'  <!-- Subtitle -->')
    svg_elements.append(f'  <text x="{sub_x:.2f}" y="132" font-family="Segoe UI, sans-serif" font-size="44" fill="#2c406e">')
    svg_elements.append(f'    <tspan x="{sub_x:.2f}" dy="0">Bilans d\'activité &amp;</tspan>')
    svg_elements.append(f'    <tspan x="{sub_x:.2f}" dy="54">Indicateurs de pilotage</tspan>')
    svg_elements.append(f'  </text>')
    
    # Write the banner SVG file
    with open(banner_svg_path, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 300" width="1200" height="300">\n')
        f.write("\n".join(svg_elements))
        f.write("\n</svg>\n")
        
    print(f"Successfully generated banner SVG at: {banner_svg_path}")

if __name__ == "__main__":
    main()
