import json,threading,unittest,urllib.request,urllib.error
from shared_catalogue_http import server
from shared_provider import SharedProvider
from shared_catalogue import SharedCatalogues
class ProviderTests(unittest.TestCase):
 def setUp(self):
  self.store=SharedCatalogues();self.http=server(store=self.store);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
  self.base='http://127.0.0.1:'+str(self.http.server_port)
  self.client=SharedProvider(self.base,allow_local_test=True)
 def tearDown(self):
  self.client.disconnect();self.http.shutdown();self.http.server_close();self.thread.join()
 def publish(self):
  return self.client.publish({'items':[{'id':'opaque','name':'Example','type':'Movie','token':'NEVER-EXPORT','Path':'PRIVATE'}]},b'\x89PNG\r\n\x1a\nexample','i'*24)
 def test_publish_projection_selection_and_disconnect(self):
  url=self.publish()
  with urllib.request.urlopen(url+'/catalogue') as response:
   data=response.read();self.assertNotIn(b'NEVER-EXPORT',data);self.assertNotIn(b'PRIVATE',data)
  request=urllib.request.Request(url+'/select',data=b'{"index":0}')
  urllib.request.urlopen(request).close()
  self.assertEqual(self.client.selection(),0);self.assertIsNone(self.client.selection())
  self.client.heartbeat();self.client.disconnect()
  with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(url+'/catalogue')
 def test_bad_posters_revoke_partial_publication(self):
  with self.assertRaises(urllib.error.HTTPError):self.client.publish({'items':[]},b'invalid','i'*24)
  self.assertIsNone(self.client.control);self.assertEqual(self.store._shares,{})
 def test_require_https_and_no_embedded_credentials(self):
  for value in ('http://example.com','https://user:secret@example.com','https://example.com/?token=secret','https://example.com/other'):
   with self.assertRaises(ValueError):SharedProvider(value)
if __name__=='__main__':unittest.main()
