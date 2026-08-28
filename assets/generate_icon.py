from PIL import Image, ImageDraw
import os

# Brand colors
DEEP_BLUE = "#0D2241"
BLUE = "#018ADE"
ORANGE = "#FF9F08"
WHITE = "#FFFFFF"

SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Corner radius
    r = max(2, size // 6)
    # Padding
    pad = max(1, size // 12)

    # Background rounded square (deep blue)
    draw.rounded_rectangle(
        [(pad, pad), (size - pad, size - pad)],
        radius=r,
        fill=DEEP_BLUE
    )

    # Chart line: goes from lower-left to upper-right
    inner = size - 2 * pad
    left = pad + max(2, inner // 6)
    bottom = size - pad - max(2, inner // 4)
    mid_x = pad + inner // 2
    mid_y = pad + inner // 2
    right = size - pad - max(2, inner // 6)
    top = pad + max(2, inner // 4)

    line_width = max(2, size // 16)

    # White line segments (step-up chart)
    draw.line([(left, mid_y), (mid_x, mid_y), (mid_x, top), (right, top)],
              fill=WHITE, width=line_width)

    # Orange arrow head at the end, pointing upper-right
    arrow_len = max(3, size // 8)
    arrow_w = max(2, size // 12)
    tip = (right, top)
    draw.polygon([
        tip,
        (right - arrow_len, top + arrow_w),
        (right - arrow_len, top - arrow_w),
    ], fill=ORANGE)

    # Small orange dot accent at bottom right
    dot_r = max(1, size // 24)
    dot_cx = size - pad - inner // 5
    dot_cy = size - pad - inner // 5
    draw.ellipse(
        [(dot_cx - dot_r, dot_cy - dot_r), (dot_cx + dot_r, dot_cy + dot_r)],
        fill=ORANGE
    )

    return img


def main():
    images = [draw_icon(s) for s in SIZES]
    # Convert to RGB with transparent background for ICO
    # ICO supports alpha, keep RGBA
    out_path = os.path.join(os.path.dirname(__file__), "icon.ico")
    images[0].save(
        out_path,
        format="ICO",
        append_images=images[1:]
    )
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
