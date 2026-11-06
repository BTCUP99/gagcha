#!/usr/bin/env python3
"""Build a looping GIF from one generated sheet (sheet) or one still image (light)."""
import argparse
import math
from pathlib import Path
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat

from pack_gif import pack

BORDER_TOLERANCE = 24      # Max per-channel spread for a border to count as a flat background.
FOREGROUND_DELTA = 28      # How far from the background color a pixel must be to count as subject.
SUBJECT_MARGIN = 0.06      # Breathing room around the union of all poses.
STABILIZE_SEARCH = 8       # Search radius, in pixels of the small analysis image.
STABILIZE_WIDTH = 128
DEFAULT_SHORT_EDGE = 512
OVERSCAN = 1.12            # Light motion on a photo enlarges it so no edge ever enters the frame.
FLOOD_MARK = (1, 254, 3)

# Each preset maps loop phase t in [0, 1) to (dx, dy, scale_x, scale_y, degrees); all are periodic.
PRESETS = {
    "breathe": lambda t: (0, 0.006 * math.sin(2 * math.pi * t), 1 + 0.012 * math.sin(2 * math.pi * t),
                          1 + 0.018 * math.sin(2 * math.pi * t), 0),
    "nod": lambda t: (0, 0.028 * max(0, math.sin(4 * math.pi * t)), 1, 1 - 0.018 * max(0, math.sin(4 * math.pi * t)), 0),
    "bounce": lambda t: (0, -0.075 * abs(math.sin(2 * math.pi * t)),
                         1 + 0.035 * (1 - abs(math.sin(2 * math.pi * t))) ** 4,
                         1 - 0.045 * (1 - abs(math.sin(2 * math.pi * t))) ** 4, 0),
    "sway": lambda t: (0.022 * math.sin(2 * math.pi * t), 0, 1, 1, 3.2 * math.sin(2 * math.pi * t)),
    "shake": lambda t: (0.016 * math.sin(10 * math.pi * t), 0, 1, 1, 0),
    "tremble": lambda t: (0.006 * math.sin(16 * math.pi * t), 0.004 * math.sin(22 * math.pi * t), 1, 1, 0),
    "pop": lambda t: (0, 0, 1 + 0.07 * math.exp(-5 * t) * math.cos(10 * math.pi * t) * (1 - t),
                      1 + 0.07 * math.exp(-5 * t) * math.cos(10 * math.pi * t) * (1 - t), 0),
    "lean": lambda t: (0.03 * math.sin(2 * math.pi * t), 0.008 * abs(math.sin(2 * math.pi * t)), 1, 1,
                       1.6 * math.sin(2 * math.pi * t)),
}


def dimensions(value):
    try:
        width, height = (int(part) for part in value.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError("须为 WIDTHxHEIGHT，例如 512x512") from None
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("宽高须为正数")
    return width, height


def border_color(cell):
    """Return the background color if the cell's outer border is one flat color, else None."""
    width, height = cell.size
    rgb = cell.convert("RGB")
    pixels = [rgb.getpixel((x, y)) for x in range(0, width, max(1, width // 40)) for y in (0, height - 1)]
    pixels += [rgb.getpixel((x, y)) for y in range(0, height, max(1, height // 40)) for x in (0, width - 1)]
    channels = list(zip(*pixels))
    if any(max(c) - min(c) > BORDER_TOLERANCE for c in channels):
        return None
    return tuple(sorted(c)[len(c) // 2] for c in channels)


def default_size(source):
    """Keep the source's shape, with the short edge at 512, so portrait photos aren't cropped square."""
    scale = DEFAULT_SHORT_EDGE / min(source)
    return round(source[0] * scale), round(source[1] * scale)


def split_cells(sheet, grid, inset):
    columns, rows = grid
    cells = []
    for row in range(rows):
        for column in range(columns):
            box = (column * sheet.width // columns + inset, row * sheet.height // rows + inset,
                   (column + 1) * sheet.width // columns - inset, (row + 1) * sheet.height // rows - inset)
            if box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError("格子太小，检查 --grid 和 --inset。")
            cells.append(sheet.crop(box))
    return cells


def subject_box(cell, background):
    """Bounding box of what isn't background, or None when the cell is empty."""
    alpha = cell.getchannel("A")
    if alpha.getextrema()[0] < 128:
        return alpha.point(lambda a: 255 if a >= 128 else 0).getbbox()
    flat = Image.new("RGB", cell.size, background)
    difference = ImageChops.difference(cell.convert("RGB"), flat).convert("L")
    return difference.point(lambda v: 255 if v >= FOREGROUND_DELTA else 0).getbbox()


def union(boxes):
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def shared_crop(box, cell_size, aspect):
    """Grow the union box by a margin and to the output aspect, staying inside the cell."""
    cell_w, cell_h = cell_size
    margin = SUBJECT_MARGIN * max(box[2] - box[0], box[3] - box[1])
    width, height = box[2] - box[0] + 2 * margin, box[3] - box[1] + 2 * margin
    if width / height < aspect:
        width = height * aspect
    else:
        height = width / aspect
    if width > cell_w:
        width, height = cell_w, cell_w / aspect
    if height > cell_h:
        width, height = cell_h * aspect, cell_h
    center_x, center_y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    left = min(max(0, center_x - width / 2), cell_w - width)
    top = min(max(0, center_y - height / 2), cell_h - height)
    return round(left), round(top), round(left + width), round(top + height)


def key_background(cell, background):
    """Clear only the background reachable from the border, so a white shirt survives a white backdrop."""
    filled = cell.convert("RGB")
    width, height = filled.size
    seeds = [(x, y) for x in range(0, width, max(1, width // 40)) for y in (0, height - 1)]
    seeds += [(x, y) for y in range(0, height, max(1, height // 40)) for x in (0, width - 1)]
    for seed in seeds:
        pixel = filled.getpixel(seed)
        if pixel != FLOOD_MARK and all(abs(a - b) <= FOREGROUND_DELTA for a, b in zip(pixel, background)):
            ImageDraw.floodfill(filled, seed, FLOOD_MARK, thresh=FOREGROUND_DELTA)
    mark = Image.new("RGB", filled.size, FLOOD_MARK)
    keep = ImageChops.difference(filled, mark).convert("L").point(lambda v: 255 if v > 0 else 0)
    keyed = cell.convert("RGBA")
    keyed.putalpha(ImageChops.multiply(keyed.getchannel("A"), keep))
    return keyed


def stabilizing_offsets(cells):
    """Whole-pixel camera shift of each cell against the first, for sheets with a fixed background."""
    height = max(1, round(cells[0].height * STABILIZE_WIDTH / cells[0].width))
    small = [cell.convert("L").resize((STABILIZE_WIDTH, height), Image.Resampling.BILINEAR) for cell in cells]
    ratio = cells[0].width / STABILIZE_WIDTH
    inner = (STABILIZE_SEARCH, STABILIZE_SEARCH, STABILIZE_WIDTH - STABILIZE_SEARCH, height - STABILIZE_SEARCH)
    reference = small[0].crop(inner)
    offsets = [(0, 0)]
    for image in small[1:]:
        best, best_score = (0, 0), None
        for dy in range(-STABILIZE_SEARCH, STABILIZE_SEARCH + 1):
            for dx in range(-STABILIZE_SEARCH, STABILIZE_SEARCH + 1):
                moved = image.crop((inner[0] + dx, inner[1] + dy, inner[2] + dx, inner[3] + dy))
                score = ImageStat.Stat(ImageChops.difference(reference, moved)).mean[0]
                if best_score is None or score < best_score:
                    best, best_score = (dx, dy), score
        offsets.append((round(best[0] * ratio), round(best[1] * ratio)))
    return offsets


def sheet_frames(args):
    with Image.open(args.sheet) as source:
        sheet = source.convert("RGBA")
    inset = args.inset if args.inset is not None else max(1, min(sheet.size) // 300)
    cells = split_cells(sheet, args.grid, inset)
    # Measure the grid cell, not the inset crop, so a 512x768 cell stays exactly 512x768.
    size = args.size or default_size((sheet.width // args.grid[0], sheet.height // args.grid[1]))
    if args.order:
        cells = [cells[index] for index in args.order]
    aspect = size[0] / size[1]
    has_alpha = sheet.getchannel("A").getextrema()[0] < 128
    background = None if has_alpha else border_color(cells[0])
    if has_alpha or background:
        boxes = [subject_box(cell, background) for cell in cells]
        empty = [index + 1 for index, box in enumerate(boxes) if box is None]
        if empty:
            raise ValueError(f"第 {empty} 格是空的；检查 --grid 或分界，只用已有可用帧本地导出；无法恢复则报告该款失败，不自动再次生成。")
        crop = shared_crop(union(boxes), cells[0].size, aspect)
        if args.key and background:
            cells = [key_background(cell, background) for cell in cells]
        frames = [cell.crop(crop) for cell in cells]
        mode = "主体"
    else:
        # A photographic sheet has no flat border: keep the framing and only remove camera drift.
        offsets = stabilizing_offsets(cells) if args.stabilize else [(0, 0)] * len(cells)
        pad_x, pad_y = max(abs(o[0]) for o in offsets), max(abs(o[1]) for o in offsets)
        frames = []
        for cell, (dx, dy) in zip(cells, offsets):
            box = (pad_x + dx, pad_y + dy, cell.width - pad_x + dx, cell.height - pad_y + dy)
            frames.append(ImageOps.fit(cell.crop(box), size, method=Image.Resampling.LANCZOS))
        mode = "写实全幅"
    resample = Image.Resampling.NEAREST if args.pixel else Image.Resampling.LANCZOS
    frames = [frame if frame.size == size else ImageOps.fit(frame, size, method=resample) for frame in frames]
    print(f"{len(frames)} 格 · {mode}模式 · 统一裁切")
    return frames


def light_frames(args):
    with Image.open(args.image) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    size = args.size or default_size(image.size)
    transparent = image.getchannel("A").getextrema()[0] < 128
    if transparent:
        # Contain inside the canvas with room for the movement.
        scale = 0.82 * min(size[0] / image.width, size[1] / image.height)
        base = Image.new("RGBA", size, (0, 0, 0, 0))
        fitted = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
        base.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    else:
        over = (round(size[0] * OVERSCAN), round(size[1] * OVERSCAN))
        base = ImageOps.fit(image, over, method=Image.Resampling.LANCZOS)
    motion = PRESETS[args.preset]
    frames = []
    for index in range(args.frames):
        dx, dy, sx, sy, degrees = motion(index / args.frames)
        frames.append(transform(base, size, dx * args.amount, dy * args.amount, 1 + (sx - 1) * args.amount,
                                1 + (sy - 1) * args.amount, degrees * args.amount))
    return frames


def transform(base, size, dx, dy, sx, sy, degrees):
    """Render base onto a size canvas, moved about the canvas center (lower center for scale)."""
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    out_cx, out_cy = size[0] / 2 + dx * size[0], size[1] / 2 + dy * size[1]
    in_cx, in_cy = base.width / 2, base.height / 2
    a, b = cos / sx, sin / sx
    d, e = -sin / sy, cos / sy
    c = in_cx - a * out_cx - b * out_cy
    f = in_cy - d * out_cx - e * out_cy
    return base.transform(size, Image.Transform.AFFINE, (a, b, c, d, e, f), resample=Image.Resampling.BICUBIC)


def write_gif(frames, args):
    if len(frames) < 2:
        raise ValueError("至少需要两帧。")
    delays = args.delay_ms
    if "," in delays and len(delays.split(",")) != len(frames):
        raise ValueError(f"--delay-ms 列了 {len(delays.split(','))} 个时长，但共有 {len(frames)} 帧。")
    with tempfile.TemporaryDirectory() as staging:
        for index, frame in enumerate(frames, 1):
            frame.save(Path(staging) / f"frame-{index:03d}.png")
        pack(argparse.Namespace(frames=Path(staging), append=[], output=args.output, fps=None, delay_ms=delays,
                                size=None, matte=None, dither=args.dither, max_bytes=args.max_bytes, force=args.force))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--size", type=dimensions, help="默认沿用素材比例，短边 512")
    shared.add_argument("--dither", action="store_true", help="照片渐变建议开启")
    shared.add_argument("--max-bytes", type=int)
    shared.add_argument("--force", action="store_true")

    sheet = commands.add_parser("sheet", parents=[shared], help="一张帧表 → 统一裁切的 GIF")
    sheet.add_argument("sheet", type=Path)
    sheet.add_argument("output", type=Path)
    sheet.add_argument("--grid", type=dimensions, required=True, help="列数x行数，例如 4x3")
    sheet.add_argument("--delay-ms", default="120", help="单一时长或逐帧时长，10 毫秒的倍数")
    sheet.add_argument("--order", type=lambda v: [int(p) - 1 for p in v.split(",")],
                       help="播放顺序，从 1 数，可重复，例如 1,2,3,4,3,2")
    sheet.add_argument("--inset", type=int, help="每格向内裁多少像素，默认按图片大小估算")
    sheet.add_argument("--key", action="store_true", help="去掉与边缘连通的纯色背景，得到透明贴纸")
    sheet.add_argument("--stabilize", action="store_true", help="写实全幅帧表：消除格子间的镜头漂移")
    sheet.add_argument("--pixel", action="store_true", help="像素风：最近邻缩放")

    light = commands.add_parser("light", parents=[shared], help="一张静图 → 轻动 GIF，人物不会走样")
    light.add_argument("image", type=Path)
    light.add_argument("output", type=Path)
    light.add_argument("--preset", choices=sorted(PRESETS), default="breathe")
    light.add_argument("--frames", type=int, default=16)
    light.add_argument("--delay-ms", default="100")
    light.add_argument("--amount", type=float, default=1.0, help="动作幅度倍数")

    args = parser.parse_args()
    try:
        if args.command == "sheet":
            if args.order and min(args.order) < 0:
                raise ValueError("--order 从 1 开始。")
            frames = sheet_frames(args)
        else:
            if args.frames < 2 or args.amount <= 0:
                raise ValueError("--frames 至少为 2，--amount 须为正数。")
            frames = light_frames(args)
        write_gif(frames, args)
    except (OSError, ValueError, IndexError) as error:
        parser.exit(2, f"build_gif: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
