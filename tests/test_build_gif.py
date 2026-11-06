"""Exercise build_gif's sheet and light modes against generated fixtures."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

SCRIPT=Path(__file__).resolve().parents[1]/"skills"/"gif-actions"/"scripts"/"build_gif.py"
RED=(220,40,40,255)

def frames_of(path):
    with Image.open(path) as image:
        result=[]
        for index in range(image.n_frames):
            image.seek(index)
            result.append(image.convert("RGBA"))
        return result

def box_of(frame):
    white=Image.new("RGBA",frame.size,(255,255,255,255))
    white.alpha_composite(frame)
    return ImageChops.difference(white.convert("RGB"),Image.new("RGB",frame.size,"white")).convert("L").point(lambda v:255 if v>60 else 0).getbbox()

class Base(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir=Path(tmp.name)
        self.out=self.dir/"成品.gif"

    def run_tool(self,*args):
        return subprocess.run([sys.executable,SCRIPT,*map(str,args)],capture_output=True,text=True,encoding="utf-8")

    def waving_sheet(self,background=(255,255,255,255),skip=None,columns=4,rows=1,cell=200):
        """A fixed head with one arm rising, so the union box moves while the head should not."""
        sheet=Image.new("RGBA",(columns*cell,rows*cell),background)
        draw=ImageDraw.Draw(sheet)
        for index in range(columns*rows):
            if index==skip:
                continue
            x,y=(index%columns)*cell,(index//columns)*cell
            draw.ellipse((x+70,y+80,x+130,y+140),fill=RED)
            draw.rectangle((x+125,y+100-index*18,x+135,y+120),fill=(30,30,200,255))
        path=self.dir/"sheet.png"
        sheet.save(path)
        return path

class SheetTests(Base):
    def test_head_stays_put_when_a_moving_hand_changes_the_pose_bounds(self):
        result=self.run_tool("sheet",self.waving_sheet(),self.out,"--grid","4x1","--size","240x240")
        self.assertEqual(result.returncode,0,result.stderr)
        frames=frames_of(self.out)
        self.assertEqual(len(frames),4)
        centers=[]
        for frame in frames:
            red=frame.convert("RGB").split()
            mask=ImageChops.subtract(red[0],red[2]).point(lambda v:255 if v>120 else 0)
            box=mask.getbbox()
            centers.append(((box[0]+box[2])/2,(box[1]+box[3])/2))
        self.assertLessEqual(max(c[0] for c in centers)-min(c[0] for c in centers),2)
        self.assertLessEqual(max(c[1] for c in centers)-min(c[1] for c in centers),2)

    def test_key_makes_the_background_transparent_but_keeps_enclosed_white(self):
        sheet=Image.new("RGBA",(400,200),(255,255,255,255))
        draw=ImageDraw.Draw(sheet)
        for x,shift in ((0,0),(200,12)):
            draw.ellipse((x+50+shift,50,x+150+shift,150),fill=RED)
            draw.ellipse((x+85+shift,85,x+115+shift,115),fill=(255,255,255,255))
        path=self.dir/"k.png"
        sheet.save(path)
        self.assertEqual(self.run_tool("sheet",path,self.out,"--grid","2x1","--size","200x200","--key").returncode,0)
        frame=frames_of(self.out)[0]
        self.assertEqual(frame.getpixel((0,0))[3],0)
        hole=[frame.getpixel((x,y)) for x in range(200) for y in range(200)]
        self.assertTrue(any(p[3]==255 and min(p[:3])>230 for p in hole),"enclosed white was removed")

    def test_empty_cell_is_reported_and_nothing_is_written(self):
        result=self.run_tool("sheet",self.waving_sheet(skip=2),self.out,"--grid","4x1")
        self.assertEqual(result.returncode,2)
        self.assertIn("3",result.stderr)
        self.assertFalse(self.out.exists())

    def test_order_repeats_cells_for_a_return_motion(self):
        self.assertEqual(self.run_tool("sheet",self.waving_sheet(),self.out,"--grid","4x1","--order","1,2,3,4,3,2").returncode,0)
        self.assertEqual(len(frames_of(self.out)),6)

    def test_order_outside_the_grid_is_rejected(self):
        self.assertEqual(self.run_tool("sheet",self.waving_sheet(),self.out,"--grid","4x1","--order","1,9").returncode,2)

    def test_delay_list_must_match_frame_count(self):
        self.assertEqual(self.run_tool("sheet",self.waving_sheet(),self.out,"--grid","4x1","--delay-ms","80,80").returncode,2)

    def test_stabilize_removes_camera_drift_on_a_photographic_sheet(self):
        # A textured backdrop shifted per cell, with a static subject drawn into the texture.
        base=Image.effect_noise((300,300),90).filter(ImageFilter.GaussianBlur(5)).point(lambda v:max(0,min(255,(v-128)*6+128))).convert("RGBA")
        ImageDraw.Draw(base).rectangle((120,120,180,180),fill=RED)
        sheet=Image.new("RGBA",(800,200))
        for index,shift in enumerate(((0,0),(6,3),(-5,4),(3,-6))):
            sheet.paste(base.crop((50+shift[0],50+shift[1],250+shift[0],250+shift[1])),(index*200,0))
        path=self.dir/"photo.png"
        sheet.save(path)
        def drift(extra):
            out=self.dir/f"o{len(extra)}.gif"
            self.assertEqual(self.run_tool("sheet",path,out,"--grid","4x1","--size","192x192",*extra).returncode,0)
            frames=frames_of(out)
            return [ImageStat.Stat(ImageChops.difference(frames[0].convert("L"),f.convert("L"))).mean[0] for f in frames[1:]]
        steady,raw=max(drift(["--stabilize"])),max(drift([]))
        self.assertLess(steady,raw*0.6,(steady,raw))

class DefaultSizeTests(Base):
    def test_portrait_sheet_keeps_its_shape_instead_of_being_cropped_square(self):
        path=self.dir/"portrait.png"
        Image.effect_noise((1024,1536),60).convert("RGB").save(path)
        self.assertEqual(self.run_tool("sheet",path,self.out,"--grid","2x2","--delay-ms","100").returncode,0)
        self.assertEqual(frames_of(self.out)[0].size,(512,768))

    def test_explicit_size_still_wins(self):
        path=self.dir/"portrait.png"
        Image.effect_noise((1024,1536),60).convert("RGB").save(path)
        self.assertEqual(self.run_tool("sheet",path,self.out,"--grid","2x2","--size","256x256").returncode,0)
        self.assertEqual(frames_of(self.out)[0].size,(256,256))

    def test_light_keeps_the_photo_shape(self):
        path=self.dir/"portrait.png"
        Image.effect_noise((600,900),60).convert("RGB").save(path)
        self.assertEqual(self.run_tool("light",path,self.out,"--preset","sway","--frames","6").returncode,0)
        self.assertEqual(frames_of(self.out)[0].size,(512,768))

class LightTests(Base):
    def photo(self):
        image=Image.effect_noise((600,800),50).convert("RGB")
        path=self.dir/"p.png"
        image.save(path)
        return path

    def test_every_preset_loops_and_moves(self):
        for preset in ("breathe","nod","bounce","sway","shake","tremble","pop","lean"):
            out=self.dir/f"{preset}.gif"
            result=self.run_tool("light",self.photo(),out,"--preset",preset,"--size","256x256","--frames","12")
            self.assertEqual(result.returncode,0,preset+result.stderr)
            frames=frames_of(out)
            self.assertGreater(len(frames),2,preset)

    def test_photo_never_shows_an_empty_edge(self):
        out=self.dir/"edge.gif"
        self.assertEqual(self.run_tool("light",self.photo(),out,"--preset","sway","--size","256x256").returncode,0)
        for frame in frames_of(out):
            self.assertEqual(frame.getchannel("A").getextrema()[0],255)

    def test_transparent_subject_stays_transparent_and_inside_the_canvas(self):
        sprite=Image.new("RGBA",(300,300),(0,0,0,0))
        ImageDraw.Draw(sprite).ellipse((60,60,240,240),fill=RED)
        path=self.dir/"s.png"
        sprite.save(path)
        out=self.dir/"s.gif"
        self.assertEqual(self.run_tool("light",path,out,"--preset","bounce","--size","256x256").returncode,0)
        for frame in frames_of(out):
            self.assertEqual(frame.getchannel("A").getextrema()[0],0)
            box=box_of(frame)
            self.assertTrue(box[0]>0 and box[1]>0 and box[2]<256 and box[3]<256)

if __name__=="__main__":
    unittest.main()
