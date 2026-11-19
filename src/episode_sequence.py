from server_connection import server_url, open_request
"""A private, explicitly approved episode sequence; only current/next titles enter the relay."""
import threading, time, urllib.parse

class EpisodeSequence:
    def __init__(self,broker,transport,item_for,jelly):
        self.broker=broker;self.transport=transport;self.item_for=item_for;self.jelly=jelly
        self.lock=threading.RLock();self.generation=0;self.rows=[];self.position=0;self.sid=None;self.cancelled=False
    def start(self,sid,item,autoplay=False,permit=None):
        session=self.broker.session(sid)
        if not session.get('token'):
            from connector import Denied
            raise Denied('Connect your library first')
        ids=[item['Id']]
        if autoplay and item.get('Type')=='Episode' and item.get('SeriesId'):
            params={'userId':session['user'],'parentId':item['SeriesId'],'recursive':'true','includeItemTypes':'Episode','sortBy':'ParentIndexNumber,IndexNumber','limit':500,'enableUserData':'false'}
            episodes=self.jelly('/Items?'+urllib.parse.urlencode(params),session['token'],server=server_url(session)).get('Items',[])
            # Preserve server order, skip specials during a regular season run, never guess missing IDs.
            episodes=[e for e in episodes if e.get('ParentIndexNumber',0)>0 or item.get('ParentIndexNumber',0)==0]
            found=next((i for i,e in enumerate(episodes) if e['Id']==item['Id']),None)
            if found is not None:ids=[e['Id'] for e in episodes[found:found+32]]
        with self.lock:
            if permit is not None and not permit():
                from connector import Denied
                raise Denied('The paired world session ended')
            obsolete=[row['slot'] for row in self.rows if row.get('slot',-1)>=0]
            selected=self.broker.select(sid,item);self.active_revision=selected['revision'];self.generation+=1;generation=self.generation
            self.rows=[{'id':i,'slot':-1,'ready':False,'title':''} for i in ids]
            self.position=0;self.sid=sid;self.cancelled=False
            self.broker.selection.update(autoplay=len(ids)>1,nextReady=False,nextSlot=-1,nextTitle='')
        if hasattr(self.transport,'stop_preparing'):self.transport.stop_preparing(obsolete)
        self._launch(0,generation)
        return selected
    def _launch(self,index,generation):
        threading.Thread(target=self._prepare,args=(index,generation),daemon=True).start()
    def _prepare(self,index,generation):
        try:
            with self.lock:
                if generation!=self.generation or self.cancelled:return
                item_id=self.rows[index]['id'];sid=self.sid
            item=self.item_for(self.broker.session(sid),item_id)
            # Keep at most two encoders active, including replaced selections still finishing.
            deadline=time.time()+180
            while sum(j['process'].poll() is None for j in self.transport.jobs.values())>=2:
                if time.time()>deadline:raise RuntimeError('Playback preparation is busy')
                with self.lock:
                    if generation!=self.generation or self.cancelled:return
                time.sleep(.5)
            slot=self.transport.prepare(item,-generation*100-index,session=self.broker.session(sid)) if getattr(self.transport,'requires_session',False) else self.transport.prepare(item,-generation*100-index)
            with self.lock:
                if generation!=self.generation:return
                self.rows[index].update(slot=slot,title=str(item.get('Name','Episode'))[:240])
            # Start the selected title from a small event-playlist buffer; keep following episodes finite.
            deadline=time.time()+21600
            while time.time()<deadline:
                with self.lock:
                    if generation!=self.generation or self.cancelled:return
                job=self.transport.jobs[slot]
                if index==0:
                    try:
                        partial=self.transport.resource(slot,'index.m3u8').read_text()
                        if partial.count('#EXTINF:')>=4:
                            with self.lock:
                                if generation!=self.generation or self.cancelled:return
                                if not self.rows[index]['ready']:
                                    self.rows[index]['ready']=True;self._publish()
                    except (OSError,RuntimeError):pass
                    except Exception as error:
                        from playback_common import PreparationError
                        if not isinstance(error,PreparationError):raise
                if job['process'].poll() is not None:
                    if job['process'].returncode!=0:raise RuntimeError('Episode preparation failed')
                    playlist=self.transport.resource(slot,'index.m3u8').read_text()
                    if not job.get('seekable') and '#EXT-X-ENDLIST' not in playlist:raise RuntimeError('Episode preparation is incomplete')
                    with self.lock:
                        if generation!=self.generation:return
                        self.rows[index]['ready']=True;self._publish()
                    if index==0 and len(self.rows)>1:self._launch(1,generation)
                    return
                time.sleep(.5)
            raise RuntimeError('Episode preparation expired')
        except Exception:
            with self.lock:
                if generation!=self.generation:return
                if index==self.position:self.broker.selection.update(ready=False,state='failed')
                else:self.broker.selection.update(nextReady=False,nextTitle='Next episode could not be prepared')
    def _publish(self):
        if not self.broker.selection or self.broker.selection['revision']!=self.active_revision:return
        current=self.rows[self.position]
        self.broker.selection.update(slot=current['slot'],ready=current['ready'],title=current['title'],state='ready' if current['ready'] else 'preparing')
        following=self.rows[self.position+1] if self.position+1<len(self.rows) else None
        self.broker.selection.update(autoplay=bool(following) and not self.cancelled,nextReady=bool(following and following['ready']),nextSlot=following['slot'] if following else -1,nextTitle=following['title'] if following else '')
    def stream_opened(self,slot):
        # No arbitrary advance endpoint: only a prepared, explicitly approved next stream can progress prefetch.
        with self.lock:
            if self.cancelled or not self.rows or self.position+1>=len(self.rows):return
            following=self.rows[self.position+1]
            if slot!=following['slot'] or not following['ready']:return
            self.position+=1;self._publish();index=self.position+1;generation=self.generation
            if index<len(self.rows):self._launch(index,generation)
    def cancel(self,sid):
        with self.lock:
            if sid!=self.sid:return
            self.cancelled=True
            if self.broker.selection:self.broker.selection.update(autoplay=False,nextReady=False,nextSlot=-1,nextTitle='')

