#!/usr/bin/env python3
"""Split one inspected contact sheet into sequential PNGs, row by row."""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageOps

def dimensions(value):
    try:
        w, h = map(int, value.lower().split("x"))
        if min(w, h) > 0:
            return w, h
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected positive WIDTHxHEIGHT")

def cuts(spec, total, count):
    if spec is None:
        return [round(i * total / count) for i in range(count+1)]
    vals = list(map(int, spec.split(",")))
    if (len(vals) != count+1 or vals[0] != 0 or vals[-1] != total
            or any(a >= b for a,b in zip(vals,vals[1:]))):
        raise ValueError("边界须递增，包含 0、实际全宽或全高，以及每条分界线")
    return vals

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path)
    parser.add_argument("output", type=Path, help="新的帧目录")
    parser.add_argument("--grid", type=dimensions, required=True, help="列数x行数")
    parser.add_argument("--x-cuts", help="每列实际分界，例如 0,333,665,998,1330")
    parser.add_argument("--y-cuts", help="每行实际分界，例如 0,578,1182")
    parser.add_argument("--inset", type=int, default=0, help="每格向内裁多少像素")
    parser.add_argument("--size", type=dimensions, help="统一输出尺寸，等比中心裁切")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("输出目录已存在；请选新目录")
    if args.inset < 0:
        parser.error("--inset 须为非负数")
    try:
        with Image.open(args.sheet) as src:
            src.load()
            xs = cuts(args.x_cuts,src.width,args.grid[0])
            ys = cuts(args.y_cuts,src.height,args.grid[1])
            boxes = [(l+args.inset,t+args.inset,r-args.inset,b-args.inset)
                     for t,b in zip(ys,ys[1:]) for l,r in zip(xs,xs[1:])]
            if any(r<=l or b<=t for l,t,r,b in boxes):
                raise ValueError("格子太小，检查网格和内裁尺寸")
            # Preserve transparent source pixels, including palette-index transparency.
            pixels = src.convert("RGBA" if "A" in src.getbands() or "transparency" in src.info else "RGB")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temp = Path(tempfile.mkdtemp(dir=args.output.parent))
            try:
                for n, box in enumerate(boxes,1):
                    cell = pixels.crop(box)
                    if args.size:
                        cell = ImageOps.fit(cell,args.size,method=Image.Resampling.LANCZOS)
                    cell.save(temp/f"frame-{n:03d}.png")
                temp.rename(args.output)
            finally:
                if temp.exists():
                    shutil.rmtree(temp)
    except (OSError, ValueError) as error:
        parser.exit(1,str(error)+"\n")
    print(f"{len(boxes)} 帧 → {args.output}")

if __name__ == "__main__":
    sys.exit(main())
