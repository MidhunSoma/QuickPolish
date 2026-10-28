"""
Generates clean, modern 64x64 and multi-resolution .ico/.png icons for QuickPolish.
Features a rounded dark indigo gradient shield with a vibrant cyan-white magic polish star.
"""

import os
import math
from PIL import Image, ImageDraw

def create_quickpolish_icon(size=256) -> Image.Image:
    """Creates a high-resolution 256x256 master icon for QuickPolish."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Draw smooth rounded rectangle background (Squircle)
    margin = int(size * 0.06)
    radius = int(size * 0.24)
    rect = [margin, margin, size - margin, size - margin]

    # Create background with gradient effect
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    bg_draw.rounded_rectangle(rect, radius=radius, fill=(30, 27, 75, 255)) # Deep Indigo

    # Diagonal gradient overlay
    for y in range(margin, size - margin):
        ratio = (y - margin) / float(size - 2 * margin)
        r = int(30 + ratio * 45)    # 30 -> 75
        g = int(27 + ratio * 55)    # 27 -> 82
        b = int(75 + ratio * 160)   # 75 -> 235
        # Draw gradient slice bounded by the rounded rectangle
        slice_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        slice_draw = ImageDraw.Draw(slice_img)
        slice_draw.line([(margin, y), (size - margin, y)], fill=(r, g, b, 255), width=1)
        # Mask with rounded rect
        bg = Image.alpha_composite(bg, slice_img)

    # Re-apply rounded rectangle mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(rect, radius=radius, fill=255)
    
    final_bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final_bg.paste(bg, (0, 0), mask)

    # 2. Draw subtle glowing outer border
    border_draw = ImageDraw.Draw(final_bg)
    border_draw.rounded_rectangle(rect, radius=radius, outline=(99, 102, 241, 180), width=int(size * 0.02))

    # 3. Draw Polishing Magic Sparkle / 4-Point Star
    star_center_x = size * 0.50
    star_center_y = size * 0.48
    star_radius_outer = size * 0.28
    star_radius_inner = size * 0.07

    points = []
    num_points = 4
    for i in range(num_points * 2):
        angle = i * (math.pi / num_points) - (math.pi / 2)
        r = star_radius_outer if i % 2 == 0 else star_radius_inner
        px = star_center_x + r * math.cos(angle)
        py = star_center_y + r * math.sin(angle)
        points.append((px, py))

    # Draw star with bright cyan/white gradient
    star_draw = ImageDraw.Draw(final_bg)
    star_draw.polygon(points, fill=(56, 189, 248, 255)) # Cyan 400

    # Draw smaller inner white star for intense core polish shine
    inner_points = []
    for i in range(num_points * 2):
        angle = i * (math.pi / num_points) - (math.pi / 2)
        r = (star_radius_outer * 0.55) if i % 2 == 0 else (star_radius_inner * 0.5)
        px = star_center_x + r * math.cos(angle)
        py = star_center_y + r * math.sin(angle)
        inner_points.append((px, py))

    star_draw.polygon(inner_points, fill=(255, 255, 255, 255))

    # 4. Add small companion sparkle dots (magic polish essence)
    dots = [
        (size * 0.76, size * 0.28, size * 0.045, (255, 255, 255, 240)),
        (size * 0.26, size * 0.70, size * 0.035, (56, 189, 248, 220)),
        (size * 0.74, size * 0.72, size * 0.025, (244, 244, 245, 200)),
    ]
    for dx, dy, dr, color in dots:
        star_draw.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=color)

    return final_bg

def ensure_icons(output_dir: str = None) -> tuple:
    """
    Ensures icon.png and icon.ico exist in the target directory.
    Generates them if missing.
    Returns (png_path, ico_path).
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
        
    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "icon.png")
    ico_path = os.path.join(output_dir, "icon.ico")
    
    master_icon = create_quickpolish_icon(size=256)
    
    # Save standard 64x64 PNG
    icon_64 = master_icon.resize((64, 64), Image.Resampling.LANCZOS)
    icon_64.save(png_path, format="PNG")
    
    # Save multi-resolution Windows ICO (16, 24, 32, 48, 64, 128, 256)
    master_icon.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    
    return png_path, ico_path

if __name__ == "__main__":
    assets_dir = os.path.dirname(os.path.abspath(__file__))
    png_p, ico_p = ensure_icons(assets_dir)
    print(f"[QuickPolish] Successfully generated:\n - PNG: {png_p}\n - ICO: {ico_p}")
