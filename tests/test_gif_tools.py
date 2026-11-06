"""Exercise inspect_gif and caption_gif against generated fixtures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw, ImageStat

SCRIPTS=Path(__file__).resolve().parents[1]/"skills"/"gagcha"/"scripts"

def tool(name,*args):
    return subprocess.run([sys.executable,SCRIPTS/name,*map(str,args)],capture_output=True,text=True,encoding="utf-8")

def moving(path,count=6,size=(120,120),transparent=False,delay=100,loop=0):
    frames=[]
    for i in range(count):
        frame=Image.new("RGBA",size,(0,0,0,0) if transparent else (255,255,255,255))
        ImageDraw.Draw(frame).ellipse((10+i*14,40,50+i*14,80),fill=(220,40,40,255))
        frames.append(frame.convert("P",palette=Image.Palette.ADAPTIVE) if not transparent else frame)
    options=dict(save_all=True,append_images=frames[1:],duration=delay,disposal=2)
    if loop is not None:
        options["loop"]=loop
    frames[0].save(path,**options)

class Base(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir=Path(tmp.name)
        self.gif=self.dir/"源.gif"

class InspectTests(Base):
    def info(self,*extra):
        result=tool("inspect_gif.py",self.gif,"--json",*extra)
        return result,json.loads(result.stdout)

    def test_reports_playback_facts(self):
        moving(self.gif)
        result,info=self.info()
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual((info["frames"],info["duration_ms"],info["loop"],info["size"]),(6,600,0,[120,120]))
        self.assertEqual(info["issues"],[])

    def test_flags_missing_infinite_loop(self):
        moving(self.gif,loop=None)
        result,info=self.info()
        self.assertEqual(result.returncode,1)
        self.assertTrue(any("循环" in issue for issue in info["issues"]))

    def test_flags_a_gif_with_no_visible_motion(self):
        frames=[Image.new("P",(60,60),i%2) for i in range(4)]
        for frame in frames:
            frame.putpalette([255,255,255,255,255,254]+[0]*762)
        frames[0].save(self.gif,save_all=True,append_images=frames[1:],duration=100,loop=0)
        result,info=self.info()
        self.assertEqual(result.returncode,1)
        self.assertTrue(any("看不出来" in issue for issue in info["issues"]))

    def test_compare_puts_the_reference_beside_the_result(self):
        moving(self.gif)
        reference,out=self.dir/"原图.png",self.dir/"比.png"
        Image.new("RGB",(200,400),"blue").save(reference)
        self.assertEqual(tool("inspect_gif.py",self.gif,"--compare",reference,out).returncode,0)
        with Image.open(out) as sheet:
            self.assertEqual(sheet.size,(192+384+384,384))
            self.assertEqual(sheet.convert("RGB").getpixel((5,5)),(0,0,255))

    def test_rejects_a_file_that_is_not_a_gif(self):
        Image.new("RGB",(10,10)).save(self.gif,format="PNG")
        self.assertEqual(tool("inspect_gif.py",self.gif).returncode,2)

    def test_writes_review_sheets_and_frames_that_pack_again(self):
        moving(self.gif)
        sheet,chat,frames,again=self.dir/"s.png",self.dir/"c.png",self.dir/"帧",self.dir/"again.gif"
        result=tool("inspect_gif.py",self.gif,"--sheet",sheet,"--chat",chat,"--extract",frames)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        with Image.open(chat) as preview:
            self.assertEqual(preview.size,(192,192))
        self.assertTrue(sheet.is_file())
        self.assertEqual(len(list(frames.glob("*.png"))),6)
        self.assertEqual(tool("pack_gif.py",frames,again,"--delay-ms","100").returncode,0)

class CaptionTests(Base):
    def caption(self,*extra,text="破防了"):
        return tool("caption_gif.py",self.gif,text,self.dir/"字.gif",*extra)

    def test_caption_changes_pixels_and_keeps_timing(self):
        moving(self.gif)
        result=self.caption()
        self.assertEqual(result.returncode,0,result.stderr)
        with Image.open(self.dir/"字.gif") as out,Image.open(self.gif) as src:
            self.assertEqual((out.n_frames,out.size,out.info["loop"]),(src.n_frames,src.size,0))
            self.assertEqual(out.info["duration"],100)
            band=(0,90,120,120)
            self.assertNotEqual(out.convert("RGB").crop(band).tobytes(),src.convert("RGB").crop(band).tobytes())

    def test_time_window_limits_the_caption(self):
        moving(self.gif)
        self.assertEqual(self.caption("--from-ms","300").returncode,0)
        with Image.open(self.dir/"字.gif") as out,Image.open(self.gif) as src:
            band=(0,90,120,120)
            def caption_contrast(frame):
                out.seek(frame);src.seek(frame)
                a,b=(im.convert("RGB").crop(band) for im in (out,src))
                return max(ImageStat.Stat(ImageChops.difference(a,b)).extrema,key=lambda e:e[1])[1]
            # Re-encoding shifts colors by a few levels, so compare against a tolerance.
            self.assertLess(caption_contrast(0),16)
            self.assertGreater(caption_contrast(4),100)

    def test_transparent_gif_stays_transparent(self):
        moving(self.gif,transparent=True)
        self.assertEqual(self.caption().returncode,0)
        with Image.open(self.dir/"字.gif") as out:
            self.assertEqual(out.convert("RGBA").getchannel("A").getextrema()[0],0)

    def test_empty_text_and_bad_window_do_not_write(self):
        moving(self.gif)
        self.assertEqual(self.caption(text="  ").returncode,2)
        self.assertEqual(self.caption("--from-ms","99999").returncode,2)
        self.assertFalse((self.dir/"字.gif").exists())

    def test_existing_output_is_protected(self):
        moving(self.gif)
        (self.dir/"字.gif").write_bytes(b"keep")
        self.assertEqual(self.caption().returncode,2)
        self.assertEqual((self.dir/"字.gif").read_bytes(),b"keep")

if __name__=="__main__":
    unittest.main()
