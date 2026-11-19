"""Bounded poster atlas builder; no external media tools or source paths."""
import io,warnings
from PIL import Image,ImageOps

def render_atlas(downloaded):
 canvas=Image.new('RGB',(1536,1728),'#101b27')
 for cell,path,item in downloaded:
  if not 0<=cell<48:continue
  try:
   with warnings.catch_warnings():
    warnings.simplefilter('error',Image.DecompressionBombWarning)
    with Image.open(path) as source:
     if source.width*source.height>20000000:continue
     tile=ImageOps.contain(source.convert('RGB'),(192,288),Image.Resampling.LANCZOS)
     canvas.paste(tile,((cell%8)*192+(192-tile.width)//2,(cell//8)*288+(288-tile.height)//2))
     item['PosterIndex']=cell
  except (OSError,ValueError,Warning):continue
 output=io.BytesIO();canvas.save(output,format='PNG');return output.getvalue()
