#!/usr/bin/env python3
"""Encode and verify one looping GIF from a directory of rendered frames."""

import argparse
import hashlib
import os
from fractions import Fraction
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageColor, ImageOps, __version__ as pillow_version

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_DELAY_MS = 655350


def natural_key(path):
    parts = re.split(r"([0-9]+)", path.name.casefold())
    return tuple(int(part) if i % 2 else part for i, part in enumerate(parts)), path.name


def frame_delays(count, fps, explicit):
    if explicit is not None:
        delays = [int(part) for part in explicit.split(",")]
        if len(delays) == 1:
            delays *= count
        if len(delays) != count or any(d % 10 for d in delays):
            raise ValueError("时长须为 10 毫秒的整数倍；可给一个时长，或按帧数逐项列出。")
    else:
        rate = Fraction(fps or "10")
        if not 0 < rate <= 100:
            raise ValueError("FPS 须大于 0，且最多为 100。")
        # Round timestamps, then subtract, so 12 fps doesn't drift to 12.5 fps.
        times = [round(i * 100 / rate) * 10 for i in range(count + 1)]
        delays = [end - start for start, end in zip(times, times[1:])]
    if any(d < 10 or d > MAX_DELAY_MS for d in delays):
        raise ValueError("每帧时长须在 10–655350 毫秒内。")
    return delays


def canvas(value, original):
    if value is None:
        size = original
    else:
        match = re.fullmatch(r"(\d+)[xX×](\d+)", value)
        if not match:
            raise ValueError("尺寸示例：--size 320x320。")
        size = tuple(map(int, match.groups()))
        w, h = original
        if abs(size[0] * h - size[1] * w) > max(w, h):
            raise ValueError("输出比例与原帧不符；请先裁剪或补边，再统一打包。")
    if not all(1 <= side <= 65535 for side in size):
        raise ValueError("GIF 画布每边须在 1–65535 像素内。")
    return size


def load_frame(path, original, size, matte):
    with Image.open(path) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError(f"{path.name} 含多帧，请先拆为独立静帧。")
        image = ImageOps.exif_transpose(image)
        if image.size != original:
            raise ValueError(f"{path.name} 为 {image.size}，与第一帧 {original} 的尺寸不一致。")
        image = image.convert("RGBA")
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    if matte:
        background = Image.new("RGBA", size, matte + (255,))
        return Image.alpha_composite(background, image)
    return image


def global_palette(paths, original, size, matte):
    # All frames vote on the palette, with equal weight and fixed sampling.
    samples = Image.new("RGB", (96, 96 * len(paths)))
    transparent = False
    for i, path in enumerate(paths):
        frame = load_frame(path, original, size, matte)
        transparent |= frame.getchannel("A").getextrema()[0] < 128
        sample = frame.resize((96, 96), Image.Resampling.NEAREST)
        visible = sample.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
        samples.paste(sample.convert("RGB"), (0, 96 * i), visible)
    ref = samples.quantize(colors=255 if transparent else 256, method=Image.Quantize.MEDIANCUT)
    colors = ref.getpalette()
    colors = (colors + colors[:3] * 256)[:768]
    if transparent:
        colors[-3:] = colors[:3]  # Opaque colors must never resolve to index 255.
    ref.putpalette(colors)
    return ref, transparent


def visual_digest(frame):
    # GIF transparent pixels may decode with arbitrary RGB underneath.
    rgba = frame.copy().convert("RGBA")
    canonical = Image.new("RGBA", rgba.size)
    canonical.alpha_composite(rgba)
    return hashlib.sha256(canonical.tobytes()).digest()


def quantized_frames(paths, original, size, matte, dither, delays):
    ref, transparent = global_palette(paths, original, size, matte)
    quantized, times, digests = [], [], []
    for path, delay in zip(paths, delays):
        rgba = load_frame(path, original, size, matte)
        frame = rgba.convert("RGB").quantize(palette=ref, dither=dither)
        if transparent:
            frame = frame.point(list(range(255)) + [0])
            frame.putpalette(ref.getpalette())
            mask = rgba.getchannel("A").point(lambda a: 255 if a < 128 else 0)
            frame.paste(255, mask=mask)
            frame.info["transparency"] = 255
        digest = visual_digest(frame)
        if digests and digest == digests[-1]:
            times[-1] += delay
            if times[-1] > MAX_DELAY_MS:
                raise ValueError("相邻相同画面的合并停顿超过 GIF 的单帧时长上限。")
        else:
            quantized.append(frame)
            times.append(delay)
            digests.append(digest)
    if len(quantized) < 2:
        raise ValueError("量化后只剩一幅画面；请提供至少两帧肉眼可辨的动作。")
    return quantized, times, digests, transparent


def verify(encoded, size, times, digests):
    with Image.open(encoded) as result:
        if result.format != "GIF" or result.size != size or result.info.get("loop") != 0:
            raise ValueError("解码校验失败：格式、尺寸或循环标记不符。")
        if result.n_frames != len(times):
            raise ValueError("解码校验失败：帧数不符。")
        for i, expected in enumerate(digests):
            result.seek(i)
            if result.info.get("duration") != times[i] or visual_digest(result) != expected:
                raise ValueError(f"解码校验失败：第 {i+1} 帧的时长、透明度或画面不符。")


def pack(args):
    paths = []
    for directory in [args.frames, *args.append]:
        if not directory.is_dir():
            raise ValueError(f"帧目录不存在：{directory}")
        entries = sorted((p for p in directory.iterdir() if p.is_file()
                          and not p.name.startswith(".") and p.suffix.lower() in EXTENSIONS),
                         key=natural_key)
        if not entries:
            raise ValueError(f"帧目录中没有支持的静帧：{directory}")
        paths.extend(entries)
    if len(paths) < 2:
        raise ValueError("请提供至少两张 PNG、JPEG 或静态 WebP 帧。")
    output = args.output
    if output.suffix.lower() != ".gif":
        raise ValueError("输出文件须使用 .gif 扩展名。")
    if output.exists() and not args.force:
        raise FileExistsError(f"输出已存在：{output}；另选文件名，或显式使用 --force。")
    with Image.open(paths[0]) as image:
        original = ImageOps.exif_transpose(image).size
    size = canvas(args.size, original)
    delays = frame_delays(len(paths), args.fps, args.delay_ms)
    matte = ImageColor.getrgb(args.matte) if args.matte else None
    if matte is not None and len(matte) != 3:
        raise ValueError("--matte 需要不透明 RGB 色，例如 '#FFFFFF'。")
    dither = Image.Dither.FLOYDSTEINBERG if args.dither else Image.Dither.NONE
    frames, times, digests, transparent = quantized_frames(paths, original, size, matte, dither, delays)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        temporary = Path(staging) / "verified.gif"
        options = dict(transparency=255, background=255, disposal=2) if transparent else dict(disposal=1)
        frames[0].save(temporary, format="GIF", save_all=True, append_images=frames[1:],
                       duration=times, loop=0, optimize=False, **options)
        verify(temporary, size, times, digests)
        byte_count = temporary.stat().st_size
        if args.max_bytes is not None and byte_count > args.max_bytes:
            raise ValueError(f"文件共 {byte_count} 字节，超过 --max-bytes {args.max_bytes}。")
        if not args.force:
            # Exclusive claim prevents concurrent encoders from overwriting one another.
            with output.open("xb"):
                pass
        try:
            os.replace(temporary, output)
        except OSError:
            if not args.force:
                output.unlink()
            raise
    print(f"{output} | {size[0]}×{size[1]} | {len(paths)} 张输入 → {len(times)} 帧 | "
          f"{sum(times)/1000:.2f} 秒 | 无限循环 | {byte_count} 字节 | Pillow {pillow_version} | 解码校验通过")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path, help="独立帧目录，按文件名自然排序")
    parser.add_argument("output", type=Path, help="目标 .gif 路径")
    parser.add_argument("--append", metavar="FRAMES_DIR", type=Path, action="append", default=[],
                        help="按给出顺序接入另一镜头的帧目录，可重复")
    timing = parser.add_mutually_exclusive_group()
    timing.add_argument("--fps", help="平均 FPS，默认 10")
    timing.add_argument("--delay-ms", help="单一时长或逐帧时长，例如 80,80,240")
    parser.add_argument("--size", help="按比例缩放到 WIDTHxHEIGHT")
    parser.add_argument("--matte", help="合成到指定底色；默认保留二值透明")
    parser.add_argument("--dither", action="store_true", help="开启 Floyd–Steinberg 抖动")
    parser.add_argument("--max-bytes", type=int, help="限制输出字节数，超过则不写入")
    parser.add_argument("--force", action="store_true", help="允许替换已存在的目标 GIF")
    args = parser.parse_args()
    try:
        pack(args)
    except (OSError, ValueError, ZeroDivisionError) as exc:
        parser.exit(2, f"pack_gif: {exc}\n")


if __name__ == "__main__":
    main()
