import os
from PIL import Image, ImageDraw, ImageFont

def generate():
    logo_path = r"ref/programme/logos/logo_ecusson_sobre.png"
    output_path = r"ref/programme/logos/bandeau_ofbilan.png"

    if not os.path.exists(logo_path):
        print(f"Error: {logo_path} does not exist.")
        return

    # Canvas dimensions
    canvas_w, canvas_h = 1200, 300
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # Load and resize logo
    logo = Image.open(logo_path)
    aspect_ratio = logo.width / logo.height
    logo_h = 220
    logo_w = int(logo_h * aspect_ratio)
    logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

    # Paste logo vertically centered
    logo_x = 40
    logo_y = (canvas_h - logo_h) // 2
    canvas.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Load system font (Segoe UI on Windows)
    font_path_bold = r"C:\Windows\Fonts\segoeuib.ttf"
    font_path_regular = r"C:\Windows\Fonts\segoeui.ttf"

    if os.path.exists(font_path_bold) and os.path.exists(font_path_regular):
        font_title = ImageFont.truetype(font_path_bold, 80)
        font_subtitle = ImageFont.truetype(font_path_regular, 44)
    else:
        # Fallback to default
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()

    # Draw text 'OFBilan'
    text_x = logo_x + logo_w + 40
    text_color = (44, 64, 110, 255) # #2c406e (OFB Dark Blue)
    
    # Calculate title size and position
    title_text = "OFBilan"
    draw.text((text_x, 90), title_text, fill=text_color, font=font_title)
    
    # Text width estimate
    try:
        title_w = font_title.getlength(title_text)
    except AttributeError:
        # Fallback for old pillow versions
        title_w = draw.textbbox((0, 0), title_text, font=font_title)[2]

    # Draw vertical separator
    sep_x = text_x + title_w + 30
    sep_color = (134, 184, 114, 255) # #86b872 (OFB Green)
    draw.line([(sep_x, 70), (sep_x, 230)], fill=sep_color, width=4)

    # Draw subtitle 'Bilans d'activité & Indicateurs de pilotage'
    sub_x = sep_x + 30
    subtitle_text = "Bilans d'activité &\nIndicateurs de pilotage"
    draw.text((sub_x, 95), subtitle_text, fill=text_color, font=font_subtitle, spacing=10)

    # Save output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG")
    print(f"Bandeau successfully created at: {output_path}")

if __name__ == "__main__":
    generate()
