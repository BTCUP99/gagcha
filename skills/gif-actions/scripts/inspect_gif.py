#!/usr/bin/env python3
"""Inspect a finished GIF: report playback facts, flag problems, and write review sheets."""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

THUMB = 96
# Mean per-channel change (0-255) below which two frames read as "the same picture".
STILL = 0.5
# Mean change between the last and first frame above which the loop seam is worth a look.
SEAM = 18.0


def decode(path):
    with Image.open(path) as image:
        if image.format != "GIF":
            raise ValueError(f"不是 GIF 文件：实际格式为 {image.format}")
        frames, delays = [], []
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            frames.append(image.convert("RGBA"))
            delays.append(image.info.get("duration", 0))
        return frames, delays, image.info.get("loop"), image.size


def flatten(frame, color):
    base = Image.new("RGBA", frame.size, color)
    base.alpha_composite(frame)
    return base.convert("RGB")


def change(a, b, color=(128, 128, 128, 255)):
    return sum(ImageStat.Stat(ImageChops.difference(flatten(a, color), flatten(b, color))).mean) / 3


def report(path):
    frames, delays, loop, size = decode(path)
    moves = [change(a, b) for a, b in zip(frames, frames[1:])]
    transparent = any(frame.getchannel("A").getextrema()[0] < 128 for frame in frames)
    total = sum(delays)
    still = sum(1 for move in moves if move < STILL)
    seam = change(frames[-1], frames[0]) if len(frames) > 1 else 0.0
    peak = max(range(len(moves)), key=moves.__getitem__) + 1 if moves else 0
    issues = []
    if len(frames) < 2:
        issues.append("只有一帧，不是动图")
    if loop != 0:
        issues.append(f"没有设置无限循环（loop={loop}）")
    if any(delay < 20 for delay in delays):
        issues.append("存在短于 20 毫秒的帧，部分客户端会放慢播放")
    if moves and max(moves) < 2:
        issues.append("相邻帧变化极小，动作可能看不出来")
    if total > 6000:
        issues.append(f"时长 {total/1000:.1f} 秒偏长，聊天里不容易看完")
    return {"file": str(path), "size": list(size), "frames": len(frames), "duration_ms": total,
            "fps": round(len(frames) * 1000 / total, 1) if total else 0, "loop": loop,
            "bytes": path.stat().st_size, "transparent": transparent, "still_pairs": still,
            "largest_jump_at_frame": peak, "loop_seam_change": round(seam, 1),
            "seam_is_hard_cut": seam > SEAM, "issues": issues}


def contact_sheet(frames, output, cell=192, columns=6, count=12):
    picks = sorted({round(i * (len(frames) - 1) / max(count - 1, 1)) for i in range(count)})
    rows = (len(picks) + columns - 1) // columns
    scale = cell / max(frames[0].size)
    tile = (max(1, round(frames[0].width * scale)), max(1, round(frames[0].height * scale)))
    sheet = Image.new("RGB", (tile[0] * columns, tile[1] * rows), "white")
    for slot, index in enumerate(picks):
        sheet.paste(flatten(frames[index], (255, 255, 255, 255)).resize(tile, Image.Resampling.LANCZOS),
                    ((slot % columns) * tile[0], (slot // columns) * tile[1]))
    sheet.save(output)


def chat_preview(frames, output):
    """The first frame and the biggest change at chat size, on light and dark backgrounds."""
    moves = [change(a, b) for a, b in zip(frames, frames[1:])]
    peak = max(range(len(moves)), key=moves.__getitem__) + 1 if moves else 0
    scale = THUMB / max(frames[0].size)
    tile = (max(1, round(frames[0].width * scale)), max(1, round(frames[0].height * scale)))
    sheet = Image.new("RGB", (tile[0] * 2, tile[1] * 2))
    for row, color in enumerate(((255, 255, 255, 255), (32, 32, 32, 255))):
        for column, index in enumerate((0, peak)):
            sheet.paste(flatten(frames[index], color).resize(tile, Image.Resampling.LANCZOS),
                        (column * tile[0], row * tile[1]))
    sheet.save(output)


def compare_sheet(frames, reference, output, height=384):
    """Reference, first frame and biggest change side by side, for judging likeness and style."""
    moves = [change(a, b) for a, b in zip(frames, frames[1:])]
    peak = max(range(len(moves)), key=moves.__getitem__) + 1 if moves else 0
    white = (255, 255, 255, 255)
    with Image.open(reference) as source:
        panels = [flatten(source.convert("RGBA"), white), flatten(frames[0], white), flatten(frames[peak], white)]
    panels = [p.resize((max(1, round(p.width * height / p.height)), height), Image.Resampling.LANCZOS) for p in panels]
    sheet = Image.new("RGB", (sum(p.width for p in panels), height), "white")
    x = 0
    for panel in panels:
        sheet.paste(panel, (x, 0))
        x += panel.width
    sheet.save(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gif", type=Path)
    parser.add_argument("--sheet", type=Path, help="写出 12 帧联系表 PNG，用来查看动作和走样")
    parser.add_argument("--chat", type=Path, help="写出聊天尺寸预览 PNG：首帧和变化最大帧，浅底与深底各一行")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("REFERENCE", "OUTPUT"),
                        help="写出对比图：参考图、首帧、变化最大帧，用来判断像不像、画风变没变")
    parser.add_argument("--extract", type=Path, help="把每帧写入一个新目录，配合 pack_gif.py 重新编码")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        info = report(args.gif)
        frames, delays, _, _ = decode(args.gif)
        if args.extract:
            args.extract.mkdir(parents=True, exist_ok=False)
            for index, frame in enumerate(frames, 1):
                frame.save(args.extract / f"frame-{index:03d}.png")
            info["delays_ms"] = ",".join(map(str, delays))
        if args.sheet:
            contact_sheet(frames, args.sheet)
        if args.chat:
            chat_preview(frames, args.chat)
        if args.compare:
            compare_sheet(frames, *args.compare)
    except (OSError, ValueError) as error:
        parser.exit(2, f"inspect_gif: {error}\n")
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"{info['file']} | {info['size'][0]}×{info['size'][1]} | {info['frames']} 帧 | "
              f"{info['duration_ms']/1000:.2f} 秒 | {info['fps']} FPS | {info['bytes']} 字节 | "
              f"{'透明' if info['transparent'] else '实底'} | "
              f"{'无限循环' if info['loop'] == 0 else '未设无限循环'}")
        print(f"相邻相同画面 {info['still_pairs']} 处；变化最大在第 {info['largest_jump_at_frame']} 帧；"
              f"首尾差异 {info['loop_seam_change']}{'（接缝是硬切，确认是有意为之）' if info['seam_is_hard_cut'] else ''}")
        if args.extract:
            print(f"逐帧时长：{info['delays_ms']}")
        for issue in info["issues"]:
            print(f"问题：{issue}")
        if not info["issues"]:
            print("技术检查未发现问题。动作、笑点和角色一致性仍需看联系表判断。")
    return 1 if info["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
