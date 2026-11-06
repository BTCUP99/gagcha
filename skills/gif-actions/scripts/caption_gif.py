#!/usr/bin/env python3
"""Stamp exact Chinese text onto a finished GIF, then re-encode and verify it with pack_gif."""
import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from pack_gif import pack

FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)


def find_font(explicit):
    if explicit:
        if not Path(explicit).is_file():
            raise ValueError(f"字体文件不存在：{explicit}")
        return explicit
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise ValueError("没有找到中文字体，请用 --font 指定字体文件。")


def fit_font(path, text, width, height, stroke_ratio):
    """Largest font whose text and outline fit the caption box."""
    for size in range(max(int(height), 8), 7, -1):
        font = ImageFont.truetype(path, size)
        stroke = max(1, round(size * stroke_ratio))
        box = ImageDraw.Draw(Image.new("RGB", (1, 1))).multiline_textbbox(
            (0, 0), text, font=font, stroke_width=stroke, align="center", spacing=size // 8)
        if box[2] - box[0] <= width and box[3] - box[1] <= height:
            return font, stroke, box
    raise ValueError("文字放不下：缩短文案、换行，或调大 --box-height。")


def caption_layer(size, text, font_path, position, box_height, fill, outline):
    width, height = size
    margin = max(4, width // 32)
    limit = round(height * box_height)
    font, stroke, box = fit_font(font_path, text, width - 2 * margin, limit, 0.1)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    y = margin if position == "top" else height - margin - text_h
    if position == "center":
        y = (height - text_h) // 2
    ImageDraw.Draw(layer).multiline_text(
        ((width - text_w) // 2 - box[0], y - box[1]), text, font=font, fill=fill, align="center",
        stroke_width=stroke, stroke_fill=outline, spacing=font.size // 8)
    # GIF has one-bit transparency, so soft glyph edges become either solid or empty.
    alpha = layer.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    layer.putalpha(alpha)
    return layer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gif", type=Path)
    parser.add_argument("text", help=r"字幕，用 \n 换行")
    parser.add_argument("output", type=Path)
    parser.add_argument("--position", choices=("top", "center", "bottom"), default="bottom")
    parser.add_argument("--box-height", type=float, default=0.22, help="字幕最多占画面高度的比例，默认 0.22")
    parser.add_argument("--from-ms", type=int, default=0, help="从第几毫秒开始显示，可让字幕卡在爆点出现")
    parser.add_argument("--to-ms", type=int, help="显示到第几毫秒，默认到结尾")
    parser.add_argument("--fill", default="#FFFFFF", help="文字颜色")
    parser.add_argument("--outline", default="#000000", help="描边颜色")
    parser.add_argument("--font", help="字体文件路径；默认查找系统中文字体")
    parser.add_argument("--dither", action="store_true")
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    text = args.text.replace("\\n", "\n").strip()
    try:
        if not text:
            raise ValueError("字幕不能为空。")
        if not 0 < args.box_height <= 1:
            raise ValueError("--box-height 须在 0–1 之间。")
        fill, outline = ImageColor.getrgb(args.fill), ImageColor.getrgb(args.outline)
        font_path = find_font(args.font)
        with Image.open(args.gif) as source, tempfile.TemporaryDirectory() as staging:
            if source.format != "GIF":
                raise ValueError(f"输入不是 GIF：实际格式为 {source.format}")
            layer = caption_layer(source.size, text, font_path, args.position, args.box_height, fill, outline)
            delays, elapsed, shown = [], 0, 0
            for index in range(getattr(source, "n_frames", 1)):
                source.seek(index)
                frame = source.convert("RGBA")
                delay = source.info.get("duration", 0) or 100
                if elapsed + delay > args.from_ms and (args.to_ms is None or elapsed < args.to_ms):
                    frame.alpha_composite(layer)
                    shown += 1
                frame.save(Path(staging) / f"frame-{index + 1:05d}.png")
                delays.append(delay)
                elapsed += delay
            if not shown:
                raise ValueError(f"显示时间段不在 GIF 时长（{elapsed} 毫秒）之内。")
            pack(argparse.Namespace(frames=Path(staging), append=[], output=args.output, fps=None,
                                    delay_ms=",".join(map(str, delays)), size=None, matte=None,
                                    dither=args.dither, max_bytes=args.max_bytes, force=args.force))
    except (OSError, ValueError) as error:
        parser.exit(2, f"caption_gif: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
