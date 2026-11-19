import unittest,json,threading,urllib.request,urllib.error
from http.server import ThreadingHTTPServer
import connector
from unittest.mock import patch

class PrivacyTests(unittest.TestCase):
 def setUp(self):
  self.now=1000;self.b=connector.Broker(lambda:self.now)
  self.a,self.sa=self.b.create();self.bsid,self.sb=self.b.create()
 def test_unconnected_cannot_select(self):
  with self.assertRaises(connector.Denied):self.b.select(self.a,{'Type':'Movie','Name':'Secret'})
 def test_authenticated_header_carries_token(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,*args):return b'{}'
  with patch('connector.open_request',return_value=Response()) as send:
   connector.jelly('/Items','test-token',server='http://127.0.0.1:8096')
  request=send.call_args[0][0]
  self.assertIn('Token="test-token"',request.get_header('Authorization'))
  self.assertIsNone(request.get_header('X-emby-token'))
 def test_expired_session_denied(self):
  self.now+=7201
  with self.assertRaises(connector.Denied):self.b.session(self.a)
 def test_active_session_renews_without_permanent_storage(self):
  self.now+=7100;self.b.session(self.a);self.now+=7100
  self.assertIs(self.b.session(self.a),self.sa)
 def test_idle_expiry_removes_session_credentials(self):
  self.sa['token']='private-test-token';self.now+=7201
  with self.assertRaises(connector.Denied):self.b.session(self.a)
  self.assertNotIn(self.a,self.b.sessions)
 def test_sessions_do_not_share_credentials(self):
  self.sa.update(server='http://127.0.0.1:8096',token='private-a',user='user-a');self.assertNotIn('token',self.sb)
 def test_only_selected_title_reaches_public_feed(self):
  self.sa.update(server='http://127.0.0.1:8096',token='private-a',user='user-a',catalog=['Unselected private title'])
  self.b.select(self.a,{'Type':'Movie','Name':'Chosen title','Path':'E:/private.mkv','AccessToken':'bad','Overview':'private metadata'})
  p=self.b.public();self.assertEqual(p['title'],'Chosen title')
  for secret in ('private-a','user-a','Unselected private title','private.mkv','Overview','AccessToken'):
   self.assertNotIn(secret,json.dumps(p))
  self.assertFalse(p['ready']);self.assertEqual(p['slot'],-1)
 def test_reject_series_as_playback(self):
  self.sa['token']='a'
  with self.assertRaises(connector.Denied):self.b.select(self.a,{'Type':'Series'})
 def test_revision_increments(self):
  self.sa['token']='a'
  self.b.select(self.a,{'Type':'Movie','Name':'One'});self.b.select(self.a,{'Type':'Episode','Name':'Two'})
  self.assertEqual(self.b.public()['revision'],2)
 def test_selection_expiry_returns_idle(self):
  self.sa['token']='a';self.b.select(self.a,{'Type':'Movie'});self.now+=21601
  self.assertEqual(self.b.public()['state'],'idle')
 def test_unknown_session_cannot_access_other_session(self):
  with self.assertRaises(connector.Denied):self.b.session('made-up-token')

class HttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),connector.Handler)
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
  cls.url='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def request(self,path,body=None,headers=None):
  h={'Host':'127.0.0.1:8097'};h.update(headers or {})
  req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=h)
  try:
   with urllib.request.urlopen(req) as r:return r.status,r.read(),r.headers
  except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
 def test_private_catalog_requires_session(self):self.assertEqual(self.request('/api/catalog')[0],403)
 def test_cross_origin_selection_blocked(self):
  self.assertEqual(self.request('/api/select',{}, {'Origin':'https://unrelated.example'})[0],403)
 def test_dns_rebinding_host_blocked(self):self.assertEqual(self.request('/room/theatre.json',headers={'Host':'attacker.example'})[0],403)
 def test_relay_has_no_credentials(self):
  status,body,headers=self.request('/room/theatre.json');self.assertEqual(status,200)
  self.assertNotIn('token',body.decode().lower());self.assertEqual(headers['Cache-Control'],'no-store')
 def test_approved_code_survives_local_countdown(self):
  sid,s=connector.broker.create();s.update(server='http://127.0.0.1:8096',quick='fake-secret',quick_until=0)
  replies=[{'Authenticated':True},{'AccessToken':'fake-private-token','User':{'Id':'fake-user'}}]
  with patch('connector.jelly',side_effect=replies):
   code,body,_=self.request('/api/connect/status',{}, {'Cookie':'vesper_session='+sid,'Origin':connector.ORIGIN,'X-Vesper-CSRF':s['csrf']})
  self.assertEqual(code,200);self.assertTrue(json.loads(body)['connected'])
  self.assertNotIn('fake-private-token',body.decode());self.assertNotIn('quick',s)
 def test_reload_preserves_browser_session(self):
  sid,s=connector.broker.create()
  code,body,h=self.request('/',headers={'Cookie':'vesper_session='+sid})
  self.assertEqual(code,200);self.assertTrue(h['Set-Cookie'].startswith('vesper_session='+sid+';'))
 def test_session_cookie_security_and_csrf(self):
  code,body,h=self.request('/');self.assertEqual(code,200);cookie=h['Set-Cookie']
  self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
  code,body,h=self.request('/api/session',headers={'Cookie':cookie.split(';')[0]})
  self.assertEqual(code,200);self.assertTrue(json.loads(body)['csrf'])
  code,_,_=self.request('/api/select',{}, {'Cookie':cookie.split(';')[0],'Origin':connector.ORIGIN})
  self.assertEqual(code,403)

class SignInGateTests(HttpTests):
 def test_signed_out_page_has_no_catalogue_or_pairing_controls(self):
  code,body,_=self.request('/');self.assertEqual(code,200);self.assertIn(b'Connect Jellyfin',body)
  for hidden in (b'pairWorld',b'worldPair',b'id="grid"',b'Find a movie'):
   self.assertNotIn(hidden,body)
 def test_signed_in_page_is_only_served_with_authenticated_session(self):
  sid,session=connector.broker.create();session['token']='private-test-token'
  code,body,_=self.request('/',headers={'Cookie':'vesper_session='+sid});self.assertEqual(code,200);self.assertIn(b'id="pairWorld"',body);self.assertNotIn(b'private-test-token',body)
 def test_catalogue_script_requires_login(self):
  self.assertEqual(self.request('/app.js')[0],403);self.assertEqual(self.request('/login.js')[0],200)

if __name__=='__main__':unittest.main(verbosity=2)


