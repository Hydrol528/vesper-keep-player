from server_connection import server_url, open_request
"""Private snapshot export and browser-approved in-world play requests. Local prototype only."""
import json,secrets,time,threading,urllib.parse,urllib.request,subprocess,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from private_catalogue import PrivateCatalogueSnapshots,SnapshotDenied
from world_session import WorldSessionGuard
from shared_visit import SharedVisit
ROOT=Path(__file__).resolve().parent
from app_paths import WORK
from poster_atlas import render_atlas
class PrivateWorldBridge:
 def __init__(self,broker,jelly,item_for,auth_header,clock=time.time):
  self.broker=broker;self.jelly=jelly;self.item_for=item_for;self.auth_header=auth_header;self.clock=clock
  self.snapshots=PrivateCatalogueSnapshots(broker.session,clock);self.lock=threading.RLock();self.states={};self.views={};self.active=None;self.pending=None;self.shared_visit=None
 def begin(self,sid,shared=None):
  if not self.broker.session(sid).get('token'):raise SnapshotDenied('Connect your library first')
  with self.lock:
   if self.states.get(sid,{}).get('state')=='preparing':return
   ticket={'state':'preparing','shared':bool(shared)};self.states[sid]=ticket
  threading.Thread(target=self._build,args=(sid,ticket,shared),daemon=True).start()
 def _build(self,sid,ticket=None,shared=None):
  stage='library'
  if ticket is None:
   with self.lock:ticket={'state':'preparing'};self.states[sid]=ticket
  try:
   s=self.broker.session(sid);views=self.jelly('/UserViews?'+urllib.parse.urlencode({'userId':s['user']}),s['token'],server=server_url(s)).get('Items',[])
   items=[];seen=set()
   for view in views:
    if view.get('CollectionType') not in ('movies','tvshows'):continue
    params={'userId':s['user'],'parentId':view['Id'],'recursive':'true','includeItemTypes':'Movie,Series,Season,Episode','sortBy':'SortName','fields':'Overview,ParentId','enableUserData':'false','limit':2001}
    reply=self.jelly('/Items?'+urllib.parse.urlencode(params),s['token'],server=server_url(s))
    if reply.get('TotalRecordCount',0)>2000:raise SnapshotDenied('This test supports up to 2000 titles and episodes')
    for item in reply.get('Items',[]):
     if item['Id'] in seen:continue
     seen.add(item['Id']);item['VesperLibrary']=view.get('Name','Library');item['PosterIndex']=-1;items.append(item)
   if len(items)>2000:raise SnapshotDenied('This test supports up to 2000 titles and episodes')
   stage='posters'
   covers=[x for x in items if x.get('Type') in ('Movie','Series') and x.get('ImageTags',{}).get('Primary')][:48]
   WORK.mkdir(parents=True,exist_ok=True)
   with tempfile.TemporaryDirectory(prefix='world-posters-',dir=WORK) as folder:
    folder=Path(folder)
    def get_cover(pair):
     i,item=pair
     try:
      url=server_url(s)+'/Items/'+item['Id']+'/Images/Primary?maxWidth=300&quality=85'
      request=urllib.request.Request(url,headers={'Authorization':self.auth_header+', Token="'+s['token']+'"'})
      with open_request(request,timeout=20) as response:data=response.read(1024*1024+1)
      if len(data)>1024*1024:return None
      p=folder/(str(i)+'.img');p.write_bytes(data);return i,p,item
     except Exception:return None
    with ThreadPoolExecutor(max_workers=4) as pool:downloaded=[r for r in pool.map(get_cover,enumerate(covers)) if r]
    atlas=render_atlas(downloaded)
   items.sort(key=lambda x:(0,str(x.get('Name','')).casefold(),0) if x.get('Type') in ('Movie','Series') else (1,str(x.get('ParentId','')),x.get('IndexNumber') or 0))
   by_id={x['Id']:x for x in items}
   for _ in range(3):
    for item in items:
     if item.get('PosterIndex',-1)<0:
      parent=by_id.get(item.get('SeriesId')) or by_id.get(item.get('ParentId'))
      if parent:item['PosterIndex']=parent.get('PosterIndex',-1)
   with self.lock:
    if self.states.get(sid) is not ticket:return
    grant=self.snapshots.issue(sid,items,atlas,combined=True);cap=grant['catalogue']
    self.views[cap]={'sid':sid,'rows':items,'until':self.clock()+300,'catalogue':json.loads(self.snapshots.grants[cap]['data']['catalogue']),'atlas':atlas}
    url='http://127.0.0.1:8097/p/'+cap
    if shared:
     stage='relay'
     peer=shared['peer'];guard=WorldSessionGuard(peer)
     if not guard.current():raise SnapshotDenied('Return to the Keep before pairing')
     self.active=dict(self.views[cap],cap=cap,peer=peer,guard=guard,direct=True,autoplay=True);self.pending=None
     url=self.share_active(sid,shared['provider'],secrets.token_urlsafe(24),shared['start'])
    self.states[sid]={'state':'ready','url':url,'expires':self.clock()+300,'count':grant['count'],'shared':bool(shared)}
    if shared:self.states[sid].pop('expires',None)
  except Exception as error:
   # No URLs, title names, account identifiers or authorization are logged.
   print('CATALOGUE_PREPARATION_FAILED stage='+stage+' error='+type(error).__name__+' code='+str(getattr(error,'code','none')),flush=True)
   with self.lock:
    if self.states.get(sid) is ticket:self.states[sid]={'state':'failed','shared':bool(shared),'message':'The shared catalogue service did not respond. Try pairing again.' if stage=='relay' else 'The catalogue could not be prepared. Reconnect your library or try again.'}
 def read(self,cap,kind,peer=None):
  data=self.snapshots.read(cap,kind)
  if kind=='catalogue':
   with self.lock:
    view=self.views.get(cap)
    if not view or view['until']<=self.clock():raise SnapshotDenied('Pairing link expired')
    if not self.active or self.active['cap']!=cap:
     self.stop_shared()
     guard=WorldSessionGuard(peer) if peer else None
     self.active=dict(view,cap=cap,peer=peer,guard=guard,direct=bool(guard and guard.current()),autoplay=True);self.pending=None
  return data
 def share_active(self,sid,provider,instance,start):
  # Called only after browser consent and verified local world pairing.
  with self.lock:
   session=self.broker.session(sid);view=self.active
   if not session.get('token') or not view or view['sid']!=sid or not view.get('direct') or not view.get('guard') or not view['guard'].current():
    raise SnapshotDenied('Connect your library in the Keep before sharing')
   if not view.get('catalogue') or not view.get('atlas'):raise SnapshotDenied('Prepare a fresh catalogue before sharing')
   self.stop_shared()
   peer=view['peer']
   def play(index):
    # Reuse per-title Jellyfin authorization and the final native visit check.
    if type(index) is not int or not self.direct_request(index,peer,start):raise SnapshotDenied('Selection unavailable')
   visit=SharedVisit(provider,view['guard'],play,self.clock)
   url=visit.connect(view['catalogue'],view['atlas'],instance)
   self.shared_visit=visit
   return url
 def stop_shared(self):
  visit=self.shared_visit;self.shared_visit=None
  if visit:
   try:visit.stop()
   except Exception:pass # Remote lease expires even when disconnect cannot reach relay.
 def tick_shared(self):
  with self.lock:
   visit=self.shared_visit
   if not visit:return
   try:
    if not self.active or not self.broker.session(self.active['sid']).get('token'):
     self.stop_shared();return
    visit.tick()
   except Exception:self.stop_shared()
 def request(self,index):
  # An unauthenticated world request NEVER prepares or plays a movie and reveals no result metadata.
  with self.lock:
   if not self.active:return
   try:s=self.broker.session(self.active['sid'])
   except Exception:return
   if not s.get('token') or not 0<=index<len(self.active['rows']):return
   item=self.active['rows'][index]
   if item.get('Type') not in ('Movie','Episode'):return
   if self.pending and self.pending['until']>self.clock():return
   self.pending={'sid':self.active['sid'],'id':item['Id'],'nonce':secrets.token_urlsafe(24),'title':str(item.get('Name','Selected title'))[:240],'episode':item['Type']=='Episode','until':self.clock()+90}
 def direct_mode(self,sid,enabled,autoplay=False):
  session=self.broker.session(sid)
  if not session.get('token'):raise SnapshotDenied('Connect your library first')
  with self.lock:
   view=self.active
   if not view or view['sid']!=sid:raise SnapshotDenied('Pair your menu first')
   if enabled and (not view.get('guard') or not view['guard'].current()):raise SnapshotDenied('Pair your menu in the running Keep test first')
   view['direct']=bool(enabled);view['autoplay']=bool(autoplay)
   if enabled:self.pending=None
 def check_world(self):
  self.tick_shared()
  with self.lock:
   view=self.active
   if view and view.get('guard') and view['guard'].current():
    try:self.broker.session(view['sid'])
    except Exception:pass
   if view and view.get('guard') and not view['guard'].current():
    sid=view['sid'];self.stop_shared();self.snapshots.revoke(sid);self.views={k:v for k,v in self.views.items() if v['sid']!=sid};self.states[sid]={'state':'left'};self.active=None;self.pending=None
    return sid
  return None
 def direct_request(self,index,peer,start):
  with self.lock:
   view=self.active
   if not peer or not view or view.get('peer')!=peer or not view.get('direct'):return False
   guard=view.get('guard')
   if not guard or not guard.current():raise SnapshotDenied('The paired world session ended')
   try:session=self.broker.session(view['sid'])
   except Exception:return False
   if not session.get('token') or not 0<=index<len(view['rows']):return False
   row=view['rows'][index]
   if row.get('Type') not in ('Movie','Episode'):return False
   if self.clock()-view.get('last_direct',-100)<3:return True
   item=self.item_for(session,row['Id'])
   if item.get('Type') not in ('Movie','Episode') or item.get('Id')!=row['Id']:raise SnapshotDenied('This title is unavailable')
   if not guard.current():raise SnapshotDenied('The paired world session ended')
   start(view['sid'],item,view.get('autoplay',False) and item['Type']=='Episode',guard.current)
   view['last_direct']=self.clock();self.pending=None
   return True
 def status(self,sid):
  self.broker.session(sid)
  with self.lock:
   state=dict(self.states.get(sid,{'state':'idle'}))
   if state.get('expires',self.clock()+1)<=self.clock():state={'state':'expired'}
   pending=self.pending if self.pending and self.pending['sid']==sid and self.pending['until']>self.clock() else None
   view=self.active
   direct={'available':bool(view and view['sid']==sid and view.get('guard') and view['guard'].current()),'enabled':bool(view and view['sid']==sid and view.get('direct'))}
   return {'direct':direct,'pairing':state,'request':{k:pending[k] for k in ('nonce','title','episode')} if pending else None}
 def take(self,sid,nonce):
  self.broker.session(sid)
  with self.lock:
   p=self.pending
   if not p or p['sid']!=sid or p['until']<=self.clock() or not secrets.compare_digest(p['nonce'],str(nonce)):raise SnapshotDenied('This play request expired')
   self.pending=None;return p['id']
 def revoke(self,sid):
  with self.lock:
   if self.active and self.active['sid']==sid:self.stop_shared()
   self.snapshots.revoke(sid)
   self.states.pop(sid,None);self.views={k:v for k,v in self.views.items() if v['sid']!=sid}
   if self.active and self.active['sid']==sid:self.active=None
   if self.pending and self.pending['sid']==sid:self.pending=None
