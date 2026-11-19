import unittest,json
from unittest.mock import patch
import connector
from server_connection import normalize_server,approval_url,ServerAddressError,NoRedirect
from test_connector import HttpTests
class ServerTests(unittest.TestCase):
 def test_accepts_different_servers_and_base_paths(self):
  self.assertEqual(normalize_server('https://media.example/jellyfin/'),'https://media.example/jellyfin')
  self.assertEqual(approval_url('http://192.168.1.20:8096'),'http://192.168.1.20:8096/web/#/quickconnect')
 def test_rejects_embedded_passwords_and_unsafe_addresses(self):
  for value in ('https://name:password@example.com','http://remote.example','http://169.254.169.254','file:///E:/Movies','https://media.example/web/','https://media.example?api_key=secret','https://media.example/#/home'):
   with self.assertRaises(ServerAddressError):normalize_server(value)
 def test_empty_successful_logout_response_is_accepted(self):
  from unittest.mock import MagicMock
  response=MagicMock();response.__enter__.return_value=response;response.read.return_value=b''
  with patch('connector.open_request',return_value=response):
   self.assertEqual(connector.jelly('/Sessions/Logout','fake',body={},method='POST',server='https://my.example'),{})
 def test_redirect_never_forwards_credentials(self):
  with self.assertRaises(ServerAddressError):NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')
 def test_item_lookup_is_bound_to_session_server(self):
  for server,token in (('https://first.example','first-token'),('https://second.example','second-token')):
   with patch('connector.jelly',return_value={}) as request:
    connector.item_for({'server':server,'token':token,'user':'user'},'a'*32)
    self.assertEqual(request.call_args.kwargs['server'],server)
    self.assertEqual(request.call_args.args[1],token)
class ApprovalServerTests(HttpTests):
 def test_approval_uses_entered_server(self):
  sid,s=connector.broker.create()
  headers={'Cookie':'vesper_session='+sid,'Origin':connector.ORIGIN,'X-Vesper-CSRF':s['csrf']}
  with patch('connector.jelly',return_value={'Code':'ABC123','Secret':'private-secret'}) as request:
   status,data,_=self.request('/api/connect',{'server':'https://my.example/jellyfin'},headers)
  self.assertEqual(status,200);self.assertEqual(request.call_args.kwargs['server'],'https://my.example/jellyfin')
  self.assertEqual(json.loads(data)['approvalUrl'],'https://my.example/jellyfin/web/#/quickconnect')
  self.assertNotIn('private-secret',data.decode());self.assertEqual(s['server'],'https://my.example/jellyfin')
 def test_no_server_does_not_silently_connect_to_owner(self):
  sid,s=connector.broker.create()
  with patch('connector.jelly') as request:
   status,_,_=self.request('/api/connect',{}, {'Cookie':'vesper_session='+sid,'Origin':connector.ORIGIN,'X-Vesper-CSRF':s['csrf']})
  self.assertEqual(status,400);request.assert_not_called()
