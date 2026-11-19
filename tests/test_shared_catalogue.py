import unittest
from shared_catalogue import SharedCatalogues,ShareDenied
class SharingTests(unittest.TestCase):
 def setUp(self):
  self.now=100.;self.store=SharedCatalogues(clock=lambda:self.now);self.rows={'items':[{'id':'opaque-1','name':'Example','type':'Episode','request':0,'token':'must-not-share','Path':'X:/private'}]};self.grant=self.store.publish('provider','instance-A',self.rows)
 def test_two_viewers_read_and_choose(self):
  for _ in range(8):self.assertEqual(self.store.read(self.grant['capability'],'instance-A')['items'][0]['name'],'Example')
  self.store.select(self.grant['capability'],'instance-A',0);self.assertEqual(self.store.take_selection(**self.args()),0);self.assertIsNone(self.store.take_selection(**self.args()))
 def args(self):return {'cap':self.grant['capability'],'control':self.grant['control']}
 def test_no_credentials_or_paths_in_snapshot(self):
  row=self.store.read(self.grant['capability'],'instance-A')['items'][0];self.assertNotIn('token',row);self.assertNotIn('Path',row)
 def test_disconnect_immediately_denies_read_and_select(self):
  self.store.disconnect(**self.args())
  with self.assertRaises(ShareDenied):self.store.read(self.grant['capability'],'instance-A')
  with self.assertRaises(ShareDenied):self.store.select(self.grant['capability'],'instance-A',0)
 def test_provider_leaving_revokes(self):
  self.store.provider_left('provider','instance-A')
  with self.assertRaises(ShareDenied):self.store.read(self.grant['capability'],'instance-A')
 def test_lost_provider_expires_without_viewer_extending_it(self):
  self.now=129.;self.store.read(self.grant['capability'],'instance-A');self.now=130.
  with self.assertRaises(ShareDenied):self.store.read(self.grant['capability'],'instance-A')
 def test_only_provider_can_extend_lease(self):
  with self.assertRaises(ShareDenied):self.store.heartbeat(self.grant['capability'],'wrong')
  self.now=120.;self.store.heartbeat(**self.args());self.now=140.;self.store.read(self.grant['capability'],'instance-A')
 def test_instance_isolation(self):
  with self.assertRaises(ShareDenied):self.store.read(self.grant['capability'],'instance-B')
  with self.assertRaises(ShareDenied):self.store.select(self.grant['capability'],'instance-B',0)
 def test_other_provider_remains_connected(self):
  other=self.store.publish('sister','instance-B',self.rows);self.store.provider_left('provider','instance-A');self.store.read(other['capability'],'instance-B')
 def test_repair_invalidates_old_link(self):
  self.store.publish('provider','instance-A',self.rows)
  with self.assertRaises(ShareDenied):self.store.read(self.grant['capability'],'instance-A')
 def test_viewer_cannot_disconnect(self):
  with self.assertRaises(ShareDenied):self.store.disconnect(self.grant['capability'],'wrong')
 def test_invalid_selection_rejected(self):
  for index in (-1,1,True,'0'):
   with self.assertRaises(ShareDenied):self.store.select(self.grant['capability'],'instance-A',index)
 def test_unlocked_viewers_can_select_locked_viewers_cannot(self):
  self.store.select(self.grant['capability'],'instance-A',0)
  self.store.set_locked(**self.args(),locked=True)
  with self.assertRaises(ShareDenied):self.store.select(self.grant['capability'],'instance-A',0)
  self.store.select(self.grant['capability'],'instance-A',0,control=self.grant['control'])
  self.store.set_locked(**self.args(),locked=False)
  self.store.select(self.grant['capability'],'instance-A',0)
 def test_viewer_cannot_change_lock(self):
  with self.assertRaises(ShareDenied):self.store.set_locked(self.grant['capability'],'wrong',True)
 def test_poster_layout_cannot_carry_account_data(self):
  for value in ({'token':'secret'},'secret',True,0,65):
   with self.assertRaises(ShareDenied):self.store.publish('p','i',dict(self.rows,posterColumns=value))
 def test_total_memory_budget_rejects_extra_posters(self):
  store=SharedCatalogues(max_bytes=400)
  grant=store.publish('provider','instance',{'items':[]})
  with self.assertRaises(ShareDenied):store.set_posters(grant['capability'],grant['control'],b'\x89PNG\r\n\x1a\n'+b'x'*500)
  self.assertEqual(store.read(grant['capability'],'instance','posters'),b'')
if __name__=='__main__':unittest.main()
