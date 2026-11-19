"""Packaged local service. Does not persist Jellyfin credentials."""
import sys,os,threading,time,ctypes,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if '--self-test' in sys.argv:
 import connector,poster_atlas,app_paths
 from PIL import Image
 assert all((ROOT/name).is_file() for name in ('login.html','index.html','login.js','app.js','style.css','vesper-logo.png'))
 from io import BytesIO
 im=Image.open(BytesIO(poster_atlas.render_atlas([])));assert im.size==(1536,1728)
 print(json.dumps({'ready':True,'assets':True,'posters':True}));sys.exit(0)
import connector as c
from app_paths import DATA,WORK
DATA.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
os.environ['TEMP']=str(WORK);os.environ['TMP']=str(WORK)
from jellyfin_transport import JellyfinTransport
from episode_sequence import EpisodeSequence
from private_world import PrivateWorldBridge
c.transport=JellyfinTransport(c.jelly,c.AUTH)
c.sequence=EpisodeSequence(c.broker,c.transport,c.item_for,c.jelly)
c.world_bridge=PrivateWorldBridge(c.broker,c.jelly,c.item_for,c.AUTH)
server=c.ThreadingHTTPServer(('127.0.0.1',8097),c.Handler)
def watch():
 while True:
  time.sleep(.5)
  sid=c.world_bridge.check_world()
  if sid is not None:c.sequence.cancel(sid)
threading.Thread(target=watch,daemon=True).start()
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateEventW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_bool,ctypes.c_wchar_p];k.CreateEventW.restype=ctypes.c_void_p
k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32];k.CloseHandle.argtypes=[ctypes.c_void_p]
stop=k.CreateEventW(None,True,False,'Local\\VesperKeepPlayer.Stop.'+str(os.getpid()))
def wait_stop():
 k.WaitForSingleObject(stop,0xFFFFFFFF);server.shutdown()
threading.Thread(target=wait_stop,daemon=True).start()
try:server.serve_forever()
finally:
 server.server_close()
 for sid in list(c.broker.sessions):
  try:c.world_bridge.revoke(sid);c.sequence.cancel(sid)
  except Exception:pass
 c.broker.sessions.clear();k.CloseHandle(stop)