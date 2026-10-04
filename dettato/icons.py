from PIL import Image, ImageDraw

# Background colour per state; the white microphone glyph stays the same
# so the icon is recognisable in every state.
STATE_COLORS = {
    "loading": (120, 120, 120),
    "idle": (37, 99, 235),
    "recording": (220, 38, 38),
    "transcribing": (217, 160, 6),
}


def make_icon(color, size: int = 256) -> Image.Image:
    """A white microphone on a coloured circle, drawn at 4x and downsampled
    so it stays crisp at tray (16-32px) sizes."""
    s = size * 4
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    white = (255, 255, 255, 255)

    draw.ellipse((0, 0, s - 1, s - 1), fill=color)

    # Capsule
    cw, top, bottom = s * 0.20, s * 0.17, s * 0.58
    cx = s / 2
    draw.rounded_rectangle((cx - cw / 2, top, cx + cw / 2, bottom), radius=cw / 2, fill=white)

    # U-shaped holder around the capsule
    stroke = max(1, int(s * 0.055))
    hw = s * 0.19
    draw.arc((cx - hw, s * 0.30, cx + hw, s * 0.68), start=0, end=180, fill=white, width=stroke)
    draw.line((cx - hw + stroke / 2, s * 0.44, cx - hw + stroke / 2, s * 0.49), fill=white, width=stroke)
    draw.line((cx + hw - stroke / 2, s * 0.44, cx + hw - stroke / 2, s * 0.49), fill=white, width=stroke)

    # Stand
    draw.line((cx, s * 0.68, cx, s * 0.78), fill=white, width=stroke)
    draw.rounded_rectangle((cx - s * 0.12, s * 0.77, cx + s * 0.12, s * 0.77 + stroke), radius=stroke / 2, fill=white)

    return image.resize((size, size), Image.LANCZOS)


def state_icon(state: str, size: int = 64) -> Image.Image:
    return make_icon(STATE_COLORS[state], size)
