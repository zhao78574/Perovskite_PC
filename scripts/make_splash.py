"""生成启动画面候选稿。

用法：
    python scripts/make_splash.py                    # 渲染全部候选稿到 assets/_preview/
    python scripts/make_splash.py --variant light    # 只渲染一版

设计依据：assets/icon.ico（#17212B 深底 + 白 P + #2DD4BF 青点）。
图标只有 256px，这里拆成「圆角底 / 白 P / 青点」三张掩膜放大重建硬边，
再按品牌色填充，得到任意尺寸都锐利的矢量级结果。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PREVIEW = ASSETS / "_preview"

W, H = 2816, 1536
INK = (23, 33, 43)          # #17212B
TEAL = (45, 212, 191)       # #2DD4BF
TEAL_DARK = (15, 118, 110)  # #0F766E

FONT_SB = r"C:\Windows\Fonts\seguisb.ttf"
FONT_R = r"C:\Windows\Fonts\segoeui.ttf"


# --------------------------------------------------------------------------
# 图标重建
# --------------------------------------------------------------------------
def _crisp(mask: Image.Image, scale: int, sharpen: float = 2.4) -> Image.Image:
    m = mask.resize((mask.width * scale, mask.height * scale), Image.LANCZOS)
    a = np.asarray(m, dtype=np.float32) / 255.0
    a = np.clip((a - 0.5) * sharpen + 0.5, 0.0, 1.0)
    return Image.fromarray((a * 255).astype(np.uint8), "L")


def icon_layers(scale: int = 4):
    """返回 (圆角底, 白 P, 青点) 三张与源图等大的掩膜。"""
    src = np.array(Image.open(ASSETS / "icon.ico").convert("RGBA"))
    r, g, b, a = (src[:, :, i].astype(np.int16) for i in range(4))
    mk = lambda m: _crisp(Image.fromarray((m * 255).astype(np.uint8), "L"), scale)
    return {
        "tile": mk((a > 40).astype(np.uint8)),
        "glyph": mk(((r > 200) & (g > 200) & (b > 200) & (a > 40)).astype(np.uint8)),
        "dot": mk(((r < 120) & (g > 140) & (b > 130) & (a > 40)).astype(np.uint8)),
    }


def render_icon(size: int, with_tile: bool = True,
                tile_color=INK, glyph_color=(255, 255, 255),
                dot_color=TEAL) -> Image.Image:
    layers = icon_layers()
    w, h = layers["tile"].size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for key, color in (("tile", tile_color), ("glyph", glyph_color), ("dot", dot_color)):
        if key == "tile" and not with_tile:
            continue
        layer = Image.new("RGBA", (w, h), (*color, 255))
        layer.putalpha(layers[key])
        out = Image.alpha_composite(out, layer)

    if with_tile:
        out = out.resize((size, size), Image.LANCZOS)
    else:
        box = out.split()[3].getbbox()
        out = out.crop(box)
        k = size / out.height
        out = out.resize((max(1, round(out.width * k)), size), Image.LANCZOS)
    return out


# --------------------------------------------------------------------------
# 背景
# --------------------------------------------------------------------------
def _dot_grid(color, alpha: int, step: int = 56) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for py in range(0, H, step):
        for px in range(0, W, step):
            d.ellipse([px, py, px + 2, py + 2], fill=(*color, alpha))
    return layer


def backdrop_dark(top=(25, 35, 47), bot=(12, 18, 24)) -> Image.Image:
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    grad = np.array(top, np.float32) * (1 - y) + np.array(bot, np.float32) * y
    grad = np.repeat(grad[:, None, :], W, axis=1)
    img = Image.fromarray(np.clip(grad, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return Image.alpha_composite(img, _dot_grid((255, 255, 255), 10))


def backdrop_light(top=(252, 253, 254), bot=(230, 238, 245)) -> Image.Image:
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    grad = np.array(top, np.float32) * (1 - y) + np.array(bot, np.float32) * y
    grad = np.repeat(grad[:, None, :], W, axis=1)
    return Image.fromarray(np.clip(grad, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def add_glow(img, box, color=TEAL, strength=0.5, blur=110):
    """在给定区域背后铺一层柔光。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=(*color, 255))
    alpha = layer.filter(ImageFilter.GaussianBlur(blur)).split()[3]
    glow = Image.composite(Image.new("RGBA", (W, H), (*color, 255)),
                           Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                           alpha.point(lambda v: int(v * strength)))
    return Image.alpha_composite(img, glow)


def drop_shadow(icon: Image.Image, offset: int = 20, blur: int = 44, opacity=0.7) -> Image.Image:
    pad = blur * 3
    canvas = Image.new("RGBA", (icon.width + pad * 2, icon.height + pad * 2), (0, 0, 0, 0))
    canvas.paste(icon, (pad, pad + offset))
    alpha = canvas.filter(ImageFilter.GaussianBlur(blur)).split()[3]
    shadow = Image.composite(Image.new("RGBA", canvas.size, (0, 0, 0, 255)),
                             Image.new("RGBA", canvas.size, (0, 0, 0, 0)),
                             alpha.point(lambda v: int(v * opacity)))
    return shadow, pad


# --------------------------------------------------------------------------
# 文字
# --------------------------------------------------------------------------
def tracked(d, xy, text, font, fill, tracking):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + tracking
    return x - tracking - xy[0]


def tracked_width(d, text, font, tracking):
    return sum(d.textlength(c, font=font) for c in text) + tracking * (len(text) - 1)


def hairline(draw_img, cx, y, half, color, peak=235, height=3):
    xs = np.arange(-half, half + 1, dtype=np.float32)
    a = (peak * (1 - np.abs(xs) / half) ** 0.75).astype(np.uint8)
    seg = np.zeros((height, xs.size, 4), dtype=np.uint8)
    seg[:, :, 0], seg[:, :, 1], seg[:, :, 2] = color
    seg[:, :, 3] = a
    draw_img.alpha_composite(Image.fromarray(seg, "RGBA"), (cx - half, y))


def tag_row(d, cx, y, items, font, fill, gap=46):
    widths = [d.textlength(i, font=font) for i in items]
    x = cx - (sum(widths) + gap * (len(items) - 1)) / 2
    for w, item in zip(widths, items):
        d.text((x, y), item, font=font, fill=fill)
        x += w + gap


# --------------------------------------------------------------------------
# 候选稿
# --------------------------------------------------------------------------
def variant_dark(out: Path):
    """深色居中锁版：品牌标 + 标题 + 字距副标 + 能力标签。"""
    img = backdrop_dark()
    size = 600
    icon = render_icon(size)
    shadow, pad = drop_shadow(icon)
    cx = W // 2
    img.alpha_composite(shadow, (cx - shadow.width // 2, 296 - pad))
    img.alpha_composite(icon, (cx - size // 2, 296))

    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT_SB, 124)
    sub = ImageFont.truetype(FONT_SB, 33)
    t = "Perovskite Workstation"
    d.text((cx - d.textlength(t, font=title) / 2, 1024), t, font=title, fill=(255, 255, 255, 255))

    ly = 1024 + 172
    hairline(img, cx, ly, 300, TEAL)
    s = "LABORATORY EDITION"
    tracked(d, (cx - tracked_width(d, s, sub, 13) / 2, ly + 34), s, sub, (*TEAL, 235), 13)
    tag_row(d, cx, 1398, ["J–V", "TRPL", "UPS", "SCLC", "XRD"],
            ImageFont.truetype(FONT_SB, 26), (255, 255, 255, 52))
    img.convert("RGB").save(out, "PNG", optimize=True)


def vignette(img: Image.Image, strength: float = 0.028) -> Image.Image:
    """四角轻微压暗，避免大面积浅底显得平板。"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = (xx - W / 2) / (W / 2)
    ny = (yy - H / 2) / (H / 2)
    d = np.sqrt(nx ** 2 + ny ** 2) / np.sqrt(2)
    f = 1.0 - strength * np.clip(d, 0, 1) ** 2.2
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) * f[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def variant_light(out: Path):
    """浅色版：与应用浅色主题一致，深色圆角标做对比。"""
    img = backdrop_light()
    size = 600
    icon = render_icon(size)
    shadow, pad = drop_shadow(icon, offset=24, blur=52, opacity=0.22)
    cx = W // 2
    img.alpha_composite(shadow, (cx - shadow.width // 2, 296 - pad))
    img.alpha_composite(icon, (cx - size // 2, 296))

    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT_SB, 124)
    sub = ImageFont.truetype(FONT_SB, 33)
    t = "Perovskite Workstation"
    d.text((cx - d.textlength(t, font=title) / 2, 1024), t, font=title, fill=(*INK, 255))

    ly = 1024 + 172
    hairline(img, cx, ly, 300, TEAL_DARK, peak=200)
    s = "LABORATORY EDITION"
    tracked(d, (cx - tracked_width(d, s, sub, 13) / 2, ly + 34), s, sub, (*TEAL_DARK, 240), 13)
    tag_row(d, cx, 1398, ["J–V", "TRPL", "UPS", "SCLC", "XRD"],
            ImageFont.truetype(FONT_SB, 26), (*INK, 90))
    vignette(img.convert("RGB")).save(out, "PNG", optimize=True)


def variant_mark(out: Path):
    """纯标志版：不要圆角砖，只留白 P 和青点。"""
    img = backdrop_dark()
    mark = render_icon(400, with_tile=False)
    shadow, pad = drop_shadow(mark, offset=14, blur=60, opacity=0.5)
    cx = W // 2
    top = 300
    img.alpha_composite(shadow, (cx - shadow.width // 2, top - pad))
    img.alpha_composite(mark, (cx - mark.width // 2, top))

    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT_SB, 108)
    sub = ImageFont.truetype(FONT_SB, 30)
    t = "Perovskite Workstation"
    ty = 1010
    d.text((cx - d.textlength(t, font=title) / 2, ty), t, font=title, fill=(255, 255, 255, 255))
    hairline(img, cx, ty + 152, 260, TEAL, peak=150)
    s = "LABORATORY EDITION"
    tracked(d, (cx - tracked_width(d, s, sub, 16) / 2, ty + 186), s, sub, (255, 255, 255, 105), 16)
    tag_row(d, cx, 1398, ["J–V", "TRPL", "UPS", "SCLC", "XRD"],
            ImageFont.truetype(FONT_SB, 24), (255, 255, 255, 42))
    img.convert("RGB").save(out, "PNG", optimize=True)


def variant_split(out: Path):
    """横向错位版：左侧大标，右侧左对齐文字，画面更稳。"""
    img = backdrop_dark()
    size = 460
    icon = render_icon(size)
    shadow, pad = drop_shadow(icon, offset=18, blur=48, opacity=0.6)

    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT_SB, 96)
    sub = ImageFont.truetype(FONT_SB, 30)
    t = "Perovskite Workstation"
    tw = d.textlength(t, font=title)
    group_w = size + 96 + tw
    x0 = (W - group_w) / 2
    cy = H * 0.47

    img.alpha_composite(shadow, (int(x0 - pad), int(cy - size // 2 - pad)))
    img.alpha_composite(icon, (int(x0), int(cy - size // 2)))

    tx = x0 + size + 96
    ty = cy - 96
    d.text((tx, ty), t, font=title, fill=(255, 255, 255, 255))
    hairline(img, int(tx + tw / 2), int(ty + 138), int(tw / 2), TEAL)
    s = "LABORATORY EDITION"
    tracked(d, (tx + 4, ty + 172), s, sub, (*TEAL, 235), 13)
    tag_row(d, W // 2, 1398, ["J–V", "TRPL", "UPS", "SCLC", "XRD"],
            ImageFont.truetype(FONT_SB, 25), (255, 255, 255, 46))
    img.convert("RGB").save(out, "PNG", optimize=True)


def variant_glow(out: Path):
    """霓虹版：青色光晕更强，图标带一圈薄边框光。"""
    img = backdrop_dark((20, 30, 41), (9, 13, 18))
    img = add_glow(img, (W // 2 - 900, 60, W // 2 + 900, 1120), strength=0.26, blur=230)

    size = 600
    icon = render_icon(size)
    cx = W // 2
    top = 296

    # 外发光描边
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    r = size * (48 / 256)  # 源图标圆角半径
    rd.rounded_rectangle([cx - size // 2 - 1, top - 1, cx + size // 2 + 1, top + size + 1],
                         radius=r + 1, outline=(*TEAL, 70), width=2)
    img = Image.alpha_composite(img, ring.filter(ImageFilter.GaussianBlur(9)))

    shadow, pad = drop_shadow(icon, offset=22, blur=60, opacity=0.75)
    img.alpha_composite(shadow, (cx - shadow.width // 2, top - pad))
    img.alpha_composite(icon, (cx - size // 2, top))

    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT_SB, 124)
    sub = ImageFont.truetype(FONT_SB, 33)
    t = "Perovskite Workstation"
    d.text((cx - d.textlength(t, font=title) / 2, 1024), t, font=title, fill=(255, 255, 255, 255))
    ly = 1024 + 172
    hairline(img, cx, ly, 300, TEAL, peak=255)
    s = "LABORATORY EDITION"
    tracked(d, (cx - tracked_width(d, s, sub, 13) / 2, ly + 34), s, sub, (*TEAL, 255), 13)
    img.convert("RGB").save(out, "PNG", optimize=True)


VARIANTS = {
    "dark": variant_dark,
    "light": variant_light,
    "mark": variant_mark,
    "split": variant_split,
    "glow": variant_glow,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=list(VARIANTS), action="append")
    ap.add_argument("--out-dir", default=str(PREVIEW))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in (args.variant or list(VARIANTS)):
        full = out_dir / f"{name}.png"
        VARIANTS[name](full)
        prev = out_dir / f"{name}_1764.png"
        Image.open(full).resize((1764, 962), Image.LANCZOS).save(prev)
        print(f"wrote {full}  (+ {prev.name})")


if __name__ == "__main__":
    main()
