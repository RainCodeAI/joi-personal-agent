"""Generate mouth-only overlay PNGs using soft-edge elliptical masking.

Takes the base face and each viseme image, composites them so only the
mouth region comes from the viseme while the rest stays as the base.
This eliminates the full-face popping during lip-sync animation.
"""

from PIL import Image, ImageDraw, ImageFilter
import os

# ── Config ─────────────────────────────────────────────────────────
BASE_FILE = "static/assets/Joi_Base.png"
OUT_DIR = "static/assets/mouth_overlays"
os.makedirs(OUT_DIR, exist_ok=True)

# Mouth region ellipse (center_x, center_y, radius_x, radius_y)
# Based on visual inspection of the 1024x1024 images
CX, CY = 512, 560
RX, RY = 170, 110
FEATHER = 45  # pixels of soft edge

# ── Load base ──────────────────────────────────────────────────────
base_img = Image.open(BASE_FILE).convert("RGBA")
W, H = base_img.size
print(f"Base image: {W}x{H}")

# ── Create soft elliptical mask ────────────────────────────────────
mask = Image.new("L", (W, H), 0)
draw = ImageDraw.Draw(mask)
draw.ellipse([CX - RX, CY - RY, CX + RX, CY + RY], fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(radius=FEATHER))
mask.save(os.path.join(OUT_DIR, "_debug_mask.png"))
print("Mask created and saved for debugging")

# ── Viseme map ─────────────────────────────────────────────────────
VISEMES = {
    "ah": "Joi_ah.png",
    "ee": "Joi_ee.png",
    "O":  "Joi_O.png",
    "Oh": "Joi_Oh.png",
    "M":  "Joi_M.png",
    "B":  "Joi_B.png",
    "F":  "Joi_F.png",
    "K":  "Joi_K.png",
    "L":  "Joi_L.png",
    "R":  "Joi_R.png",
    "S":  "Joi_S.png",
    "TH": "Joi_TH.png",
    "W":  "Joi_W.png",
}

# ── Generate composites ───────────────────────────────────────────
for name, filename in VISEMES.items():
    vis_path = os.path.join("static/assets", filename)
    vis_img = Image.open(vis_path).convert("RGBA")
    # Composite: mouth from viseme, everything else from base
    result = Image.composite(vis_img, base_img, mask)
    out_path = os.path.join(OUT_DIR, f"mouth_{name}.png")
    result.save(out_path, optimize=True)
    kb = os.path.getsize(out_path) // 1024
    print(f"  {name:5s} -> {out_path} ({kb}KB)")

# rest = just the base face (mouth closed)
rest_path = os.path.join(OUT_DIR, "mouth_rest.png")
base_img.save(rest_path, optimize=True)
kb = os.path.getsize(rest_path) // 1024
print(f"  rest  -> {rest_path} ({kb}KB)")
print("\nDone! All mouth overlays generated.")
