import io,tempfile,unittest
from pathlib import Path
from PIL import Image
from poster_atlas import render_atlas
class AtlasTests(unittest.TestCase):
 def test_empty_atlas_has_exact_grid_and_padding_color(self):
  im=Image.open(io.BytesIO(render_atlas([])))
  self.assertEqual(im.size,(1536,1728));self.assertEqual(im.getpixel((0,0)),(16,27,39))
 def test_cell_order_and_invalid_image_do_not_shift_other_posters(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'poster.png';Image.new('RGB',(200,300),'red').save(p)
   bad=Path(d)/'bad';bad.write_bytes(b'not an image')
   item={'PosterIndex':-1};baditem={'PosterIndex':-1}
   im=Image.open(io.BytesIO(render_atlas([(9,p,item),(0,bad,baditem)])))
   self.assertEqual(item['PosterIndex'],9);self.assertEqual(baditem['PosterIndex'],-1)
   self.assertEqual(im.getpixel((288,432)),(255,0,0));self.assertEqual(im.getpixel((0,0)),(16,27,39))