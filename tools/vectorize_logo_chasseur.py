import os
import numpy as np
from PIL import Image, ImageFilter
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

def rdp_iterative(points, epsilon):
    """Iterative Ramer-Douglas-Peucker algorithm to simplify paths accurately."""
    if len(points) < 3:
        return points
    
    stack = [(0, len(points) - 1)]
    keep = np.zeros(len(points), dtype=bool)
    keep[0] = True
    keep[-1] = True
    
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
            
        p0 = points[start]
        p1 = points[end]
        segment = p1 - p0
        norm_sq = np.sum(segment**2)
        
        dmax = 0
        idx = start
        
        for i in range(start + 1, end):
            p = points[i]
            if norm_sq < 1e-8:
                d = np.sqrt(np.sum((p - p0)**2))
            else:
                t = np.dot(p - p0, segment) / norm_sq
                t = np.clip(t, 0, 1)
                projection = p0 + t * segment
                d = np.sqrt(np.sum((p - projection)**2))
                
            if d > dmax:
                dmax = d
                idx = i
                
        if dmax > epsilon:
            keep[idx] = True
            stack.append((start, idx))
            stack.append((idx, end))
            
    return points[keep]

def get_background_mask(arr, tolerance=25):
    """Flood fill from corners to find the background outside the shield."""
    h, w, _ = arr.shape
    visited = np.zeros((h, w), dtype=bool)
    stack = [(0, 0), (0, w-1), (h-1, 0), (h-1, w-1)]
    bg_mask = np.zeros((h, w), dtype=bool)
    target_color = arr[0, 0].astype(float)
    
    for r, c in stack:
        visited[r, c] = True
        
    while stack:
        r, c = stack.pop()
        dist = np.sqrt(np.sum((arr[r, c] - target_color)**2))
        if dist <= tolerance:
            bg_mask[r, c] = True
            for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w:
                    if not visited[nr, nc]:
                        visited[nr, nc] = True
                        stack.append((nr, nc))
    return bg_mask

def get_components(mask):
    """Find connected components in a binary mask (pure numpy BFS)."""
    h, w = mask.shape
    labeled = np.zeros((h, w), dtype=int)
    label_id = 1
    for r in range(h):
        for c in range(w):
            if mask[r, c] and labeled[r, c] == 0:
                queue = [(r, c)]
                labeled[r, c] = label_id
                head = 0
                while head < len(queue):
                    curr_r, curr_c = queue[head]
                    head += 1
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nr, nc = curr_r + dr, curr_c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            if mask[nr, nc] and labeled[nr, nc] == 0:
                                labeled[nr, nc] = label_id
                                queue.append((nr, nc))
                label_id += 1
    return labeled, label_id - 1

def fill_holes(mask):
    """Fill holes in a binary mask (pure numpy flood fill on inverted mask)."""
    h, w = mask.shape
    inv = (mask == 0)
    visited = np.zeros((h, w), dtype=bool)
    stack = []
    for r in [0, h-1]:
        for c in range(w):
            if inv[r, c]:
                stack.append((r, c))
                visited[r, c] = True
    for c in [0, w-1]:
        for r in range(1, h-1):
            if inv[r, c]:
                stack.append((r, c))
                visited[r, c] = True
                
    while stack:
        r, c = stack.pop()
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                if inv[nr, nc] and not visited[nr, nc]:
                    visited[nr, nc] = True
                    stack.append((nr, nc))
                    
    filled_mask = mask.copy()
    filled_mask[inv & ~visited] = True
    return filled_mask

def trace_mask_to_svg_path(mask, blur_radius=2.0, epsilon=0.4, scale_x=1.0, scale_y=1.0, tx=0.0, ty=0.0):
    """Convert a binary mask to smoothed SVG path data using Gaussian blur and RDP."""
    fig = Figure()
    ax = fig.subplots()
    
    # Smooth the mask
    mask_img = Image.fromarray((mask * 255).astype(np.uint8))
    blurred_img = mask_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    blurred_arr = np.array(blurred_img) / 255.0
    
    cs = ax.contour(blurred_arr, levels=[0.5])
    paths_svg = []
    for path in cs.get_paths():
        verts = path.vertices
        if len(verts) < 3:
            continue
        simplified_verts = rdp_iterative(verts, epsilon=epsilon)
        if len(simplified_verts) < 3:
            continue
        # Apply scale and translation
        transformed_verts = simplified_verts * np.array([scale_x, scale_y]) + np.array([tx, ty])
        d = f"M {transformed_verts[0][0]:.2f} {transformed_verts[0][1]:.2f} "
        for v in transformed_verts[1:]:
            d += f"L {v[0]:.2f} {v[1]:.2f} "
        d += "Z"
        paths_svg.append(d)
    return " ".join(paths_svg)

def scale_translate_path(d_str, scale_x, scale_y, tx, ty):
    """Scale and translate SVG path commands dynamically."""
    d_str = d_str.replace(",", " ")
    tokens = d_str.split()
    new_tokens = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ["M", "L", "C", "A"]:
            new_tokens.append(tok)
            i += 1
            if tok in ["M", "L"]:
                x = float(tokens[i]) * scale_x + tx
                y = float(tokens[i+1]) * scale_y + ty
                new_tokens.append(f"{x:.2f}")
                new_tokens.append(f"{y:.2f}")
                i += 2
            elif tok == "C":
                x1 = float(tokens[i]) * scale_x + tx
                y1 = float(tokens[i+1]) * scale_y + ty
                x2 = float(tokens[i+2]) * scale_x + tx
                y2 = float(tokens[i+3]) * scale_y + ty
                x3 = float(tokens[i+4]) * scale_x + tx
                y3 = float(tokens[i+5]) * scale_y + ty
                new_tokens.extend([f"{x1:.2f}", f"{y1:.2f}", f"{x2:.2f}", f"{y2:.2f}", f"{x3:.2f}", f"{y3:.2f}"])
                i += 6
            elif tok == "A":
                rx = float(tokens[i]) * scale_x
                ry = float(tokens[i+1]) * scale_y
                rot = tokens[i+2]
                large_arc = tokens[i+3]
                sweep = tokens[i+4]
                x = float(tokens[i+5]) * scale_x + tx
                y = float(tokens[i+6]) * scale_y + ty
                new_tokens.extend([f"{rx:.2f}", f"{ry:.2f}", rot, large_arc, sweep, f"{x:.2f}", f"{y:.2f}"])
                i += 7
        elif tok == "Z":
            new_tokens.append(tok)
            i += 1
        else:
            new_tokens.append(tok)
            i += 1
    return " ".join(new_tokens)

def main():
    img_path = r"ref/hors_programme/logos/logo_ecusson_sobre.png"
    svg_path = r"ref/hors_programme/logos/logo_ecusson_chasseur.svg"
    
    if not os.path.exists(img_path):
        print(f"Error: {img_path} not found.")
        return
        
    print("Loading image...")
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    arr = np.array(img)
    
    print("Detecting background...")
    bg_mask = get_background_mask(arr)
    
    # Define exact colors
    target_colors = {
        "white": np.array([255.0, 255.0, 255.0]),
        "blue": np.array([31.0, 124.0, 184.0]),
        "lime": np.array([125.0, 185.0, 68.0]),
        "light_green": np.array([38.0, 111.0, 61.0]),
        "dark_green": np.array([27.0, 83.0, 45.0]),
    }
    
    print("Classifying pixels...")
    flat_arr = arr.reshape(-1, 3).astype(float)
    dists = []
    names = list(target_colors.keys())
    for name in names:
        ref_color = target_colors[name]
        dist = np.sqrt(np.sum((flat_arr - ref_color)**2, axis=1))
        dists.append(dist)
    
    dists = np.array(dists)
    flat_labels = np.argmin(dists, axis=0)
    labels = flat_labels.reshape(h, w)
    labels[bg_mask] = -1
    
    # Extract white components first
    print("Extracting white components...")
    white_mask = (labels == names.index("white"))
    labeled_white, num_white = get_components(white_mask)
    
    white_components = []
    for label_id in range(1, num_white + 1):
        comp_mask = (labeled_white == label_id)
        area = comp_mask.sum()
        if area < 30: # Filter noise
            continue
        rows, cols = np.where(comp_mask)
        ymin, ymax = rows.min(), rows.max()
        xmin, xmax = cols.min(), cols.max()
        aspect_ratio = (xmax - xmin + 1) / (ymax - ymin + 1)
        white_components.append({
            "label_id": label_id,
            "area": area,
            "xmin": xmin, "xmax": xmax,
            "ymin": ymin, "ymax": ymax,
            "aspect_ratio": aspect_ratio,
            "mask": comp_mask
        })
        
    # Sort by area descending
    white_components.sort(key=lambda x: x["area"], reverse=True)
    
    # Identify the river mask
    river_mask = (labels == names.index("blue")).copy()
    
    # Find fish and human white components (ymin > 500 and xmax < 500)
    # and add their masks to the river mask to make the river solid under them
    print("Making river solid under overlapping white icons...")
    for comp in white_components[1:]:
        if comp["ymin"] > 500 and comp["xmax"] < 500:
            river_mask[comp["mask"]] = True
            
    # Also fill any remaining holes in the river mask
    river_mask = fill_holes(river_mask)
    
    # SVG Elements accumulator
    svg_elements = []
    
    # 1. Tracing the outer shield contour to define a perfect clip-path
    print("Tracing shield boundary...")
    shield_mask = (~bg_mask)
    shield_path = trace_mask_to_svg_path(shield_mask, blur_radius=2.0, epsilon=0.5)
    
    svg_elements.append("<defs>")
    svg_elements.append(f'  <clipPath id="shield">')
    svg_elements.append(f'    <path d="{shield_path}" />')
    svg_elements.append(f'  </clipPath>')
    svg_elements.append("</defs>")
    
    # 2. Perfect background vertical split using the clip-path
    mid_x = w / 2
    svg_elements.append(f'  <!-- Background Shield Split -->')
    svg_elements.append(f'  <rect x="0" y="0" width="{mid_x}" height="{h}" fill="#26753f" clip-path="url(#shield)" />')
    svg_elements.append(f'  <rect x="{mid_x}" y="0" width="{mid_x}" height="{h}" fill="#1b532d" clip-path="url(#shield)" />')
    
    # 3. Tracing the River (now completely solid and smooth)
    print("Tracing river...")
    labeled_river, num_river = get_components(river_mask)
    if num_river > 0:
        areas = [np.sum(labeled_river == label_id) for label_id in range(1, num_river + 1)]
        largest_id = np.argmax(areas) + 1
        river_mask = (labeled_river == largest_id)
        
    river_path = trace_mask_to_svg_path(river_mask, blur_radius=6.0, epsilon=1.2)
    if river_path:
        svg_elements.append(f'  <!-- River -->')
        svg_elements.append(f'  <path d="{river_path}" fill="#1f7cb8" fill-rule="evenodd" />')
        
    # 4. Hunter Icon from attached image (replacing the graph bars)
    print("Vectorizing hunter icon from attached image...")
    hunter_img_path = r"C:\Users\aguirre.maurin\.gemini\antigravity-ide\brain\480453d9-e1f9-4432-acb6-77f2a1c78755\media__1782053495091.png"
    if os.path.exists(hunter_img_path):
        hunter_img = Image.open(hunter_img_path)
        if hunter_img.mode == "RGBA":
            r, g, b, a = hunter_img.split()
            r_arr = np.array(r)
            g_arr = np.array(g)
            b_arr = np.array(b)
            a_arr = np.array(a)
            h_arr = np.ones_like(a_arr) * 255
            stroke_mask = (a_arr > 127) & ((r_arr.astype(float) + g_arr + b_arr)/3.0 < 127)
            h_arr[stroke_mask] = 0
        else:
            hunter_img_l = hunter_img.convert("L")
            h_arr = np.array(hunter_img_l)
            
        h_img, w_img = h_arr.shape
        visited = np.zeros((h_img, w_img), dtype=bool)
        stack = [(0, 0), (0, w_img-1), (h_img-1, 0), (h_img-1, w_img-1)]
        bg_mask_hunter = np.zeros((h_img, w_img), dtype=bool)
        target_val = h_arr[0, 0]
        
        for row, col in stack:
            visited[row, col] = True
            
        while stack:
            row, col = stack.pop()
            if abs(float(h_arr[row, col]) - target_val) <= 10:
                bg_mask_hunter[row, col] = True
                for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                    nr, nc = row + dr, col + dc
                    if 0 <= nr < h_img and 0 <= nc < w_img:
                        if not visited[nr, nc]:
                            visited[nr, nc] = True
                            stack.append((nr, nc))
                            
        h_mask = ~bg_mask_hunter
        rows, cols = np.where(h_mask)
        if len(rows) > 0:
            ymin, ymax = rows.min(), rows.max()
            xmin, xmax = cols.min(), cols.max()
            mask_w = xmax - xmin + 1
            mask_h = ymax - ymin + 1
            
            # Target height is 150 pixels (matches bird and tractor sizes)
            target_h = 150.0
            scale = target_h / mask_h
            
            # Position harmoniously: shifted slightly right to x = 670, y = 455
            target_cx = 670.0
            target_cy = 455.0
            mask_cx = (xmin + xmax) / 2.0
            mask_cy = (ymin + ymax) / 2.0
            tx = target_cx - mask_cx * scale
            ty = target_cy - mask_cy * scale
            
            # Trace and scale/translate (using a slightly stronger blur for smooth solid silhouette)
            hunter_path = trace_mask_to_svg_path(h_mask, blur_radius=2.5, epsilon=0.4,
                                                 scale_x=scale, scale_y=scale, tx=tx, ty=ty)
            if hunter_path:
                svg_elements.append(f'  <!-- Hunter (White, Solid Silhouette) -->')
                svg_elements.append(f'  <path d="{hunter_path}" fill="#ffffff" fill-rule="evenodd" />')
        else:
            print("Warning: Hunter mask is empty.")
    else:
        print(f"Warning: {hunter_img_path} not found.")
        
    # 5. White Inner Border
    border_comp = white_components[0]
    print("Tracing white border ring...")
    border_path = trace_mask_to_svg_path(border_comp["mask"], blur_radius=2.0, epsilon=0.4)
    svg_elements.append(f'  <!-- White Inner Border -->')
    svg_elements.append(f'  <path d="{border_path}" fill="#ffffff" fill-rule="evenodd" />')
    
    # 6. Process remaining white elements
    svg_elements.append(f'  <!-- White Icons -->')
    for comp in white_components[1:]:
        if comp["aspect_ratio"] > 10 and comp["ymin"] > 400 and comp["xmin"] > 400:
            print("Skipping graph baseline...")
            continue
        else:
            icon_path = trace_mask_to_svg_path(comp["mask"], blur_radius=2.5, epsilon=0.3)
            if icon_path:
                svg_elements.append(f'  <path d="{icon_path}" fill="#ffffff" fill-rule="evenodd" />')
                
    # Write SVG file
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n')
        f.write("\n".join(svg_elements))
        f.write("\n</svg>\n")
        
    print(f"Successfully generated hunter version SVG at: {svg_path}")

if __name__ == "__main__":
    main()
