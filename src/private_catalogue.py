"""Short-lived, account-scoped read grants for a local in-world catalogue prototype.
No routes are exposed by this module; callers must use authenticated browser sessions.
"""
import json,secrets,time,threading

class SnapshotDenied(Exception):pass
class PrivateCatalogueSnapshots:
 def __init__(self,session_for,clock=time.time):self.session_for=session_for;self.clock=clock;self.lock=threading.RLock();self.grants={}
 def issue(self,sid,items,poster_png=None,combined=False):
  session=self.session_for(sid)
  if not session.get('token'):raise SnapshotDenied('Connect your library first')
  if len(items)>2000:raise SnapshotDenied('Choose a smaller library for this test')
  rows=[]
  for item in items:
   if item.get('Type') not in ('Movie','Series','Season','Episode'):continue
   rows.append({'id':str(item.get('Id',''))[:64],'name':str(item.get('Name','Untitled'))[:240],
    'type':item['Type'],'parent':str(item.get('ParentId',''))[:64],
    'season':item.get('ParentIndexNumber'),'number':item.get('IndexNumber'),
    'library':str(item.get('VesperLibrary',''))[:100],'poster':int(item.get('PosterIndex',-1)),'request':len(rows),
    'year':item.get('ProductionYear'),'overview':str(item.get('Overview',''))[:600]})
  payload=json.dumps({'version':1,'posterColumns':8,'posterRows':6,'items':rows},ensure_ascii=False).encode('utf-8')
  if len(payload)>1024*1024:raise SnapshotDenied('Catalogue snapshot is too large')
  if poster_png is not None and (not isinstance(poster_png,bytes) or not poster_png.startswith(bytes([137,80,78,71,13,10,26,10])) or len(poster_png)>8*1024*1024):raise SnapshotDenied('Invalid poster atlas')
  with self.lock:
   now=self.clock();self.grants={k:v for k,v in self.grants.items() if v['until']>now}
   if len(self.grants)>=64:raise SnapshotDenied('Too many active pairing links')
   catalog=secrets.token_urlsafe(16);image=secrets.token_urlsafe(16) if poster_png else None
   self.grants[catalog]={'sid':sid,'until':now+300,'uses':2,'kind':'catalogue','data':payload}
   if image:self.grants[image]={'sid':sid,'until':now+300,'uses':2,'kind':'posters','data':poster_png}
   if combined and image:
    self.grants.pop(image)
    self.grants[catalog].update(kind='bundle',uses={'catalogue':2,'posters':2},data={'catalogue':payload,'posters':poster_png})
    image=catalog
   return {'catalogue':catalog,'posters':image,'expiresIn':300,'count':len(rows)}
 def read(self,capability,kind):
  with self.lock:
   grant=self.grants.get(capability)
   if not grant or grant['until']<=self.clock():raise SnapshotDenied('Pairing link expired or unavailable')
   if grant['kind']=='bundle':
    if kind not in ('catalogue','posters') or grant['uses'].get(kind,0)<=0:raise SnapshotDenied('Pairing link expired or unavailable')
   elif grant['uses']<=0 or grant['kind']!=kind:raise SnapshotDenied('Pairing link expired or unavailable')
   try:session=self.session_for(grant['sid'])
   except Exception as error:raise SnapshotDenied('Library session ended') from error
   if not session.get('token'):raise SnapshotDenied('Library disconnected')
   if grant['kind']=='bundle':
    grant['uses'][kind]-=1
    return grant['data'][kind]
   grant['uses']-=1
   return grant['data']
 def revoke(self,sid):
  with self.lock:self.grants={k:v for k,v in self.grants.items() if v['sid']!=sid}


