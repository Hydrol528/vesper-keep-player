import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import jellyfin_transport as jt
from playback_common import PreparationError
class NativeTransportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=tempfile.gettempdir());self.root=Path(self.temp.name);self.jelly=Mock();self.patch=patch.object(jt,'CACHE',self.root);self.patch.start();self.transport=jt.JellyfinTransport(self.jelly,'test-auth')
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def test_rejects_external_redirects_and_arbitrary_paths(self):
  for url in ('https://external.example/video.ts','http://127.0.0.1:8096/Users','http://127.0.0.1:8097/Videos/1/a.ts','http://name:secret@127.0.0.1:8096/Videos/1/a.ts'):
   with self.assertRaises(PreparationError):self.transport.validate_url(url,'http://127.0.0.1:8096')
 def test_manifest_never_leaks_jellyfin_credentials_or_source_ids(self):
  self.transport.jobs[0]={'server':'http://127.0.0.1:8096','urls':{}}
  text=self.transport.rewrite(0,'http://127.0.0.1:8096/Videos/private-id/master.m3u8?api_key=private-token','#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\nmain.m3u8?api_key=private-token\n')
  self.assertNotIn('private-token',text);self.assertNotIn('private-id',text);self.assertIn('/watch/0/r',text)
  uri=self.transport.rewrite(0,'http://127.0.0.1:8096/Videos/private-id/main.m3u8','#EXTM3U\n#EXT-X-MAP:URI="init.mp4?api_key=private-token"\n')
  self.assertNotIn('private-token',uri)
 def test_unknown_resource_cannot_trigger_network(self):
  self.transport.opener=Mock()
  for name in ('../file','index.m3u8','r'+'a'*24+'.ts'):
   with self.assertRaises(PreparationError):self.transport.resource(0,name)
  self.transport.opener.open.assert_not_called()
 def test_finite_native_profile_and_english_audio(self):
  self.jelly.return_value={'PlaySessionId':'private-play','MediaSources':[{'TranscodingUrl':'/Videos/test-id/master.m3u8?api_key=private-token','IsInfiniteStream':False}]}
  response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.read.return_value=b'#EXTM3U\nmain.m3u8?api_key=private-token\n';self.transport.opener=Mock();self.transport.opener.open.return_value=response
  item={'Id':'a'*32,'MediaStreams':[{'Type':'Audio','Index':1,'Language':'hin'},{'Type':'Audio','Index':2,'Language':'eng'}]}
  slot=self.transport.prepare(item,1,{'server':'http://127.0.0.1:8096','user':'private-user','token':'private-token'})
  body=self.jelly.call_args.kwargs['body'];self.assertEqual(body['AudioStreamIndex'],2);self.assertFalse(body['EnableDirectPlay']);self.assertEqual(body['DeviceProfile']['TranscodingProfiles'][0]['Protocol'],'hls');self.assertTrue(self.transport.jobs[slot]['seekable']);self.assertIn('AudioStreamIndex=2',self.transport.jobs[slot]['urls']['index.m3u8'])
  result=self.transport.resource(slot,'index.m3u8').read_text();self.assertNotIn('private-token',result)
 def test_stop_revokes_old_stream_before_cancelling_encoder(self):
  self.transport.jobs[0]={'server':'http://127.0.0.1:8096','revoked':False,'device':'one-device','playSession':'one-session','token':'private-token'};self.transport.stop_preparing([0]);self.assertTrue(self.transport.jobs[0]['revoked']);self.assertEqual(self.jelly.call_args.kwargs['method'],'DELETE')
if __name__=='__main__':unittest.main()
