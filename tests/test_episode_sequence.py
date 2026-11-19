import unittest,time
from pathlib import Path
from unittest.mock import Mock
from connector import Broker,Denied
from episode_sequence import EpisodeSequence

class FakeTransport:
 def __init__(self):self.jobs={};self.prepared=[]
 def prepare(self,item,revision):
  slot=len(self.jobs);self.prepared.append(item['Id']);self.jobs[slot]={'process':Mock(poll=lambda:0,returncode=0)};return slot
 def resource(self,slot,name):return Mock(read_text=lambda:'#EXTM3U\n#EXT-X-ENDLIST\n')

class SequenceTests(unittest.TestCase):
 def setUp(self):
  self.b=Broker();self.sid,self.session=self.b.create();self.session.update(server='http://127.0.0.1:8096',token='private-token',user='private-user')
  self.items=[{'Id':str(i)*32,'Type':'Episode','Name':'Episode '+str(i),'SeriesId':'a'*32,'ParentIndexNumber':1,'IndexNumber':i} for i in range(1,5)]
  self.transport=FakeTransport();self.lookup=Mock(side_effect=lambda session,id:next(x for x in self.items if x['Id']==id));self.jelly=Mock(return_value={'Items':self.items})
  self.q=EpisodeSequence(self.b,self.transport,self.lookup,self.jelly)
 def settle(self,predicate):
  end=time.time()+2
  while time.time()<end:
   if predicate():return
   time.sleep(.01)
  self.fail('Timed out waiting for sequence state')
 def test_only_prepares_current_and_one_ahead(self):
  self.q.start(self.sid,self.items[0],True);self.settle(lambda:self.b.public().get('nextReady'))
  self.assertEqual(self.transport.prepared,[self.items[0]['Id'],self.items[1]['Id']])
  self.assertNotIn('private-token',str(self.b.public()));self.assertNotIn(self.items[2]['Id'],str(self.b.public()))
 def test_next_stream_prefetches_following_episode_once(self):
  self.q.start(self.sid,self.items[0],True);self.settle(lambda:self.b.public().get('nextReady'))
  slot=self.b.public()['nextSlot'];self.q.stream_opened(slot);self.q.stream_opened(slot)
  self.settle(lambda:self.b.public().get('nextReady') and self.b.public()['title']=='Episode 2')
  self.assertEqual(self.transport.prepared,[x['Id'] for x in self.items[:3]])
 def test_disabled_autoplay_prepares_only_selection(self):
  self.q.start(self.sid,self.items[1],False);self.settle(lambda:self.b.public()['ready'])
  self.assertEqual(self.transport.prepared,[self.items[1]['Id']]);self.jelly.assert_not_called()
 def test_cancel_keeps_current_and_disables_next(self):
  self.q.start(self.sid,self.items[0],True);self.settle(lambda:self.b.public().get('nextReady'))
  slot=self.b.public()['nextSlot'];self.q.cancel(self.sid);self.q.stream_opened(slot)
  self.assertEqual(self.q.position,0);self.assertFalse(self.b.public()['autoplay']);self.assertTrue(self.b.public()['ready'])
 def test_unconnected_session_cannot_prepare(self):
  self.session.pop('token')
  with self.assertRaises((Denied,KeyError)):self.q.start(self.sid,self.items[0],True)
 def test_final_episode_has_no_next(self):
  self.q.start(self.sid,self.items[-1],True);self.settle(lambda:self.b.public()['ready'])
  self.assertFalse(self.b.public()['autoplay']);self.assertFalse(self.b.public()['nextReady']);self.assertEqual(self.b.public()['nextSlot'],-1)
 def test_new_selection_cannot_be_overwritten_by_old_sequence(self):
  self.q.start(self.sid,self.items[0],True);self.settle(lambda:self.b.public().get('nextReady'))
  self.b.select(self.sid,{'Type':'Movie','Name':'Different selection'});self.q._publish()
  self.assertEqual(self.b.public()['title'],'Different selection')
 def test_selection_starts_from_buffer_before_encoding_finishes(self):
  process=Mock();process.poll.return_value=None;process.returncode=0
  class BufferedTransport(FakeTransport):
   def prepare(inner,item,revision):
    slot=super().prepare(item,revision);inner.jobs[slot]['process']=process;return slot
   def resource(inner,slot,name):
    return Mock(read_text=lambda:'#EXTM3U\n#EXT-X-PLAYLIST-TYPE:EVENT\n'+('#EXTINF:4,\nsegment.ts\n'*4)+('#EXT-X-ENDLIST\n' if process.poll() is not None else ''))
  t=BufferedTransport();q=EpisodeSequence(self.b,t,self.lookup,self.jelly)
  q.start(self.sid,self.items[0],False);self.settle(lambda:self.b.public()['ready']);self.assertIsNone(process.poll());process.poll.return_value=0
 def test_buffer_under_four_segments_does_not_start(self):
  process=Mock();process.poll.return_value=None;process.returncode=0
  class ShortTransport(FakeTransport):
   def prepare(inner,item,revision):
    slot=super().prepare(item,revision);inner.jobs[slot]['process']=process;return slot
   def resource(inner,slot,name):return Mock(read_text=lambda:'#EXTM3U\n#EXTINF:4,\nsegment.ts\n')
  q=EpisodeSequence(self.b,ShortTransport(),self.lookup,self.jelly);q.start(self.sid,self.items[0],False);self.settle(lambda:bool(q.transport.jobs));time.sleep(.1);self.assertFalse(self.b.public()['ready']);q.cancel(self.sid)
if __name__=='__main__':unittest.main()
