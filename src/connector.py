"""Local-only catalogue/relay prototype. Never expose this HTTP listener publicly."""
import json, secrets, time, threading, re, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie

ROOT=Path(__file__).resolve().parent
from server_connection import normalize_server, server_url, approval_url, open_request, ServerAddressError
ORIGIN='http://127.0.0.1:8097'
AUTH='MediaBrowser Client="Vesper Keep Connector", Device="Local companion", DeviceId="vesper-local-prototype", Version="0.1"'
ID=re.compile(r'^[a-fA-F0-9]{32}$')

from private_catalogue import SnapshotDenied
from local_peer import trusted_vrchat
class Denied(Exception): pass
class Broker:
    def __init__(self,clock=time.time):
        self.clock=clock; self.sessions={}; self.selection=None; self.revision=0; self.lock=threading.RLock()
    def create(self):
        with self.lock:
            # Browser capabilities expire after two hours and live only in memory.
            now=self.clock()
            self.sessions={k:v for k,v in self.sessions.items() if v['until']>now}
            if len(self.sessions)>=64: raise Denied('Too many sessions')
            sid=secrets.token_urlsafe(32)
            self.sessions[sid]={'until':now+7200,'csrf':secrets.token_urlsafe(32)}
            return sid,self.sessions[sid]
    def session(self,sid):
        with self.lock:
            s=self.sessions.get(sid)
            if not s or s['until']<=self.clock():
                self.sessions.pop(sid,None)
                raise Denied('Reconnect this browser')
            s['until']=self.clock()+7200
            return s
    def select(self,sid,item):
        with self.lock:
            s=self.session(sid)
            if not s.get('token'): raise Denied('Connect your library first')
            if item.get('Type') not in ('Movie','Episode'): raise Denied('Choose a movie or episode')
            self.revision+=1
            # Private credentials and paths never enter the public relay payload.
            self.selection={'revision':self.revision,'title':str(item.get('Name','Selected media'))[:240],
                            'ready':False,'slot':-1,'state':'preparing','expires':self.clock()+21600}
            return dict(self.selection)
    def public(self):
        with self.lock:
            if not self.selection or self.selection['expires']<=self.clock():
                return {'revision':self.revision,'state':'idle','ready':False,'slot':-1,'title':''}
            return {k:v for k,v in self.selection.items() if k!='expires'}

INSTANCE=secrets.token_hex(4)
broker=Broker()
transport=None
sequence=None
world_bridge=None

def stream_ready(revision,slot):
    with broker.lock:
        if broker.selection and broker.selection['revision']==revision:
            broker.selection.update(ready=True,slot=slot,state='ready')
def stream_error(revision,message):
    with broker.lock:
        if broker.selection and broker.selection['revision']==revision:
            broker.selection.update(ready=False,slot=-1,state='failed')

def jelly(path,token=None,body=None,method=None,*,server):
    headers={'Authorization':AUTH,'Accept':'application/json'}
    if token: headers['Authorization']=AUTH+', Token="'+token+'"'
    data=None if body is None else json.dumps(body).encode()
    if data is not None: headers['Content-Type']='application/json'
    req=urllib.request.Request(normalize_server(server)+path,data=data,headers=headers,method=method)
    with open_request(req,timeout=20) as response:
        raw=response.read(4*1024*1024+1)
        if len(raw)>4*1024*1024: raise Denied('Response too large')
        return json.loads(raw) if raw.strip() else {}

def item_for(s,item_id):
    if not ID.fullmatch(item_id): raise Denied('Invalid item')
    if not s.get('token'): raise Denied('Connect your library first')
    # Always re-authorize against this session's Jellyfin user, never another browser's cache.
    return jelly('/Items/'+item_id+'?'+urllib.parse.urlencode({'userId':s['user']}),s['token'],server=server_url(s))

def entry(x):
    return {'id':x['Id'],'name':x.get('Name','Untitled'),'type':x.get('Type',''),
            'year':x.get('ProductionYear'),'overview':x.get('Overview','')[:4000],
            'number':x.get('IndexNumber'),'season':x.get('ParentIndexNumber'),
            'poster':bool(x.get('ImageTags',{}).get('Primary'))}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass # Never log capability URLs, cookies, bodies or Jellyfin tokens.
    def send(self,status,data,mime='application/json',cookie=None):
        if not isinstance(data,bytes): data=json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if cookie is None and getattr(self,'renew_cookie',None):cookie='vesper_session='+self.renew_cookie+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=7200'
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(data)
    def private(self):
        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
        sid=cookie.get('vesper_session')
        if not sid:raise Denied('Open the Vesper Keep player page first')
        session=broker.session(sid.value);self.renew_cookie=sid.value
        return sid.value,session
    def do_GET(self):
        try:
            if self.headers.get('Host')!='127.0.0.1:8097': raise Denied('Invalid host')
            u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query)
            if u.path=='/':
                try: sid,s=self.private()
                except Denied: sid,s=broker.create()
                page='index.html' if s.get('token') else 'login.html'
                self.send(200,(ROOT/page).read_bytes(),'text/html; charset=utf-8',
                          'vesper_session='+sid+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=7200');return
            if u.path=='/app.js':
                _,session=self.private()
                if not session.get('token'):raise Denied('Sign in first')
            if u.path in ('/app.js','/login.js','/style.css'):
                self.send(200,(ROOT/u.path[1:]).read_bytes(),'text/javascript' if u.path.endswith('.js') else 'text/css');return
            if u.path in ('/fonts/cinzel.ttf','/fonts/liberation-sans.ttf'):
                self.send(200,(ROOT/u.path[1:]).read_bytes(),'font/ttf');return
            if u.path.startswith('/world/pair/') or u.path.startswith('/p/'):
                cap=u.path.rsplit('/',1)[-1]
                if not re.fullmatch(r'(?:[A-Za-z0-9_-]{22}|[A-Za-z0-9_-]{43})',cap) or world_bridge is None:raise SnapshotDenied('Pairing link unavailable')
                image='image/' in self.headers.get('Accept','').lower()
                peer=trusted_vrchat(self.client_address,self.connection.getsockname())
                data=world_bridge.read(cap,'posters' if image else 'catalogue',peer)
                self.send(200,data,'image/png' if image else 'application/json');return
            if u.path=='/world/shared/disconnect':
                peer=trusted_vrchat(self.client_address,self.connection.getsockname())
                if not peer or world_bridge is None:raise Denied('Paired local client required')
                with world_bridge.lock:
                    view=world_bridge.active
                    if not view or view.get('peer')!=peer:raise Denied('Paired local client required')
                    sid=view['sid'];world_bridge.revoke(sid)
                    if sequence is not None:sequence.cancel(sid)
                self.send(200,{'disconnected':True});return
            if u.path.startswith('/world/request/'):
                value=u.path.rsplit('/',1)[-1]
                if world_bridge is not None and re.fullmatch(r'\d{1,4}',value):
                    peer=trusted_vrchat(self.client_address,self.connection.getsockname())
                    start=lambda sid,item,autoplay,permit:sequence.start(sid,item,autoplay,permit=permit)
                    with world_bridge.lock:shared=bool(world_bridge.shared_visit and world_bridge.shared_visit.active)
                    if shared and not peer:
                        self.send(503,{'error':'Player connection could not be verified. Retry shortly.'});return
                    if sequence is None or not world_bridge.direct_request(int(value),peer,start):
                        if shared:self.send(403,{'error':'The paired visit is unavailable'});return
                        world_bridge.request(int(value))
                self.send(200,{'accepted':True});return
            if u.path=='/health':self.send(200,{'version':'0.2','instance':INSTANCE});return
            if u.path=='/room/theatre.json':
                payload=broker.public();payload['catalogueShared']=False
                if world_bridge is not None:
                    with world_bridge.lock:
                        visit=world_bridge.shared_visit
                        payload['catalogueShared']=bool(visit and visit.active)
                self.send(200,payload);return
            if u.path.startswith('/watch/'):
                from playback_common import PreparationError
                m=re.fullmatch(r'/watch/(\d{1,2})/(index\.m3u8|part\d{6}\.ts|r[a-f0-9]{24}\.(?:m3u8|ts))',u.path)
                if not m or transport is None:self.send(404,{'error':'No selected stream'});return
                try:p=transport.resource(int(m[1]),m[2])
                except PreparationError:self.send(404,{'error':'Selected stream unavailable'});return
                if sequence is not None and m[2]=='index.m3u8':sequence.stream_opened(int(m[1]))
                self.send(200,p.read_bytes(),'application/vnd.apple.mpegurl' if m[2].endswith('.m3u8') else 'video/mp2t');return
            sid,s=self.private()
            if u.path=='/api/session':self.send(200,{'csrf':s['csrf'],'connected':bool(s.get('token')),'server':s.get('server','')});return
            if u.path=='/api/world/status':
                if not s.get('token'):raise Denied('Connect your library first')
                self.send(200,world_bridge.status(sid) if world_bridge else {'pairing':{'state':'idle'},'request':None});return
            if u.path=='/api/libraries':
                if not s.get('token'):raise Denied('Connect your library first')
                result=jelly('/UserViews?'+urllib.parse.urlencode({'userId':s['user']}),s['token'],server=server_url(s))
                self.send(200,{'items':[{'id':x['Id'],'name':x.get('Name','Library')} for x in result.get('Items',[]) if x.get('CollectionType') in ('movies','tvshows')]});return
            if u.path=='/api/catalog':
                if not s.get('token'):raise Denied('Connect your library first')
                search=q.get('q',[''])[0][:120];parent=q.get('parent',[''])[0];library=q.get('library',[''])[0]
                if library and not ID.fullmatch(library):raise Denied('Invalid library')
                if parent and not ID.fullmatch(parent):raise Denied('Invalid category')
                params={'userId':s['user'],'limit':48,'startIndex':max(0,min(10000,int(q.get('offset',['0'])[0]))),
                        'recursive':'true','includeItemTypes':'Movie,Series','sortBy':'SortName','fields':'Overview','enableUserData':'false'}
                if library:params['parentId']=library
                if search:params['searchTerm']=search
                if parent:params.update(parentId=parent,recursive='false',includeItemTypes='Season,Episode')
                result=jelly('/Items?'+urllib.parse.urlencode(params),s['token'],server=server_url(s))
                self.send(200,{'items':[entry(x) for x in result.get('Items',[])],'total':result.get('TotalRecordCount',0)});return
            if u.path.startswith('/api/poster/'):
                item_id=u.path.rsplit('/',1)[-1];item_for(s,item_id)
                req=urllib.request.Request(server_url(s)+'/Items/'+item_id+'/Images/Primary?maxWidth=300&quality=85',headers={'Authorization':AUTH+', Token="'+s['token']+'"'})
                with open_request(req,timeout=15) as r:
                    data=r.read(2*1024*1024+1)
                    if len(data)>2*1024*1024:raise Denied('Image too large')
                    self.send(200,data,r.headers.get_content_type());return
            self.send(404,{'error':'Not found'})
        except (Denied,SnapshotDenied) as e:self.send(403,{'error':str(e)})
        except (urllib.error.URLError,TimeoutError):self.send(502,{'error':'Jellyfin did not answer. Check its local server.'})
        except (ValueError,KeyError):self.send(400,{'error':'Invalid request'})
        except (BrokenPipeError,ConnectionResetError):pass
    def do_POST(self):
        try:
            if self.headers.get('Host')!='127.0.0.1:8097' or self.headers.get('Origin')!=ORIGIN:raise Denied('Open the local Vesper Keep player page')
            sid,s=self.private()
            if not secrets.compare_digest(self.headers.get('X-Vesper-CSRF',''),s['csrf']):raise Denied('Reload the Vesper Keep player page')
            length=int(self.headers.get('Content-Length','0'))
            if length>4096 or length<0:raise Denied('Request too large')
            body=json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body,dict):raise Denied('Invalid request body')
            if self.path=='/api/connect':
                if s.get('token'):raise Denied('Sign out before connecting a different Jellyfin server')
                server=normalize_server(body.get('server',''));result=jelly('/QuickConnect/Initiate',body={},method='POST',server=server);s.update(server=server,quick=result['Secret'],quick_until=time.time()+300)
                self.send(200,{'code':result['Code'],'approvalUrl':approval_url(server)});return
            if self.path=='/api/connect/status':
                if not s.get('quick'):raise Denied('Request a new connection code')
                state=jelly('/QuickConnect/Connect?'+urllib.parse.urlencode({'secret':s['quick']}),server=server_url(s))
                if not state.get('Authenticated'):self.send(200,{'connected':False});return
                result=jelly('/Users/AuthenticateWithQuickConnect',body={'Secret':s['quick']},method='POST',server=server_url(s))
                s.pop('quick',None)
                s.update(token=result['AccessToken'],user=result['User']['Id'])
                self.send(200,{'connected':True});return
            if self.path=='/api/world/stop':
                if world_bridge is None:raise Denied('Private world menu is not running')
                world_bridge.revoke(sid)
                if sequence is not None:sequence.cancel(sid)
                self.send(200,{'unpaired':True});return
            if self.path=='/api/world/direct':
                if world_bridge is None:raise Denied('Private world menu is not running')
                world_bridge.direct_mode(sid,body.get('enabled') is True,body.get('autoplay') is True)
                self.send(200,{'updated':True});return
            if self.path=='/api/world/share':
                if world_bridge is None or sequence is None:raise Denied('The player is not running')
                from keep_client import current_keep_peer
                from shared_provider import SharedProvider
                peer=current_keep_peer()
                if peer is None:raise Denied('Open VRChat and join the Keep, then try pairing again.')
                provider=SharedProvider('https://vesperkeep-catalogue-relay.onrender.com')
                start=lambda sid,item,autoplay,permit:sequence.start(sid,item,autoplay,permit=permit)
                world_bridge.begin(sid,{'peer':peer,'provider':provider,'start':start})
                self.send(200,{'state':'preparing','shared':True});return
            if self.path=='/api/world/create':
                if world_bridge is None:raise Denied('Private world menu is not running')
                world_bridge.begin(sid);self.send(200,{'state':'preparing'});return
            if self.path in ('/api/world/confirm','/api/world/decline'):
                if world_bridge is None:raise Denied('Private world menu is not running')
                item_id=world_bridge.take(sid,body.get('nonce',''))
                if self.path.endswith('/confirm'):
                    item=item_for(s,item_id)
                    if sequence is None:raise Denied('Playback is not running')
                    sequence.start(sid,item,body.get('autoplay') is True)
                self.send(200,{'confirmed':self.path.endswith('/confirm')});return
            if self.path=='/api/autoplay/cancel':
                if sequence is not None:sequence.cancel(sid)
                self.send(200,{'message':'Autoplay cancelled. Current playback can continue.'});return
            if self.path=='/api/prepare':
                from playback_common import PreparationError
                if transport is None:raise Denied('Playback transport is not running')
                item=item_for(s,str(body.get('id','')))
                if sequence is None:raise Denied('Episode preparation is not running')
                selected=sequence.start(sid,item,body.get('autoplay') is True)
                self.send(200,{'revision':selected['revision'],'state':'preparing','message':'Preparing selected media. Autoplay will follow episode order when enabled; the theatre shows a countdown before advancing.'});return
            if self.path=='/api/select':
                item=item_for(s,str(body.get('id','')))
                if sequence is not None:sequence.cancel(sid)
                selected=broker.select(sid,item)
                # Transport-only milestone: never advertise a stream until encoding and decoder tests pass.
                self.send(200,dict(selected,message='Selection reached the relay. Playback transport is not enabled in this prototype.'));return
            if self.path=='/api/disconnect':
                if world_bridge is not None:world_bridge.revoke(sid)
                if sequence is not None:sequence.cancel(sid)
                if s.get('token'):
                    try:jelly('/Sessions/Logout',s['token'],body={},method='POST',server=server_url(s))
                    except urllib.error.URLError:pass
                broker.sessions.pop(sid,None);self.send(200,{'disconnected':True},cookie='vesper_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0');return
            self.send(404,{'error':'Not found'})
        except (Denied,SnapshotDenied) as e:self.send(403,{'error':str(e)})
        except (urllib.error.URLError,TimeoutError):self.send(502,{'error':'Jellyfin did not answer this request.'})
        except (ValueError,KeyError):self.send(400,{'error':'Invalid request'})
        except (BrokenPipeError,ConnectionResetError):pass

if __name__=='__main__':
    print('Vesper local connector prototype: '+ORIGIN,flush=True)
    print('Local testing only. No startup stream. Credentials remain in process memory.',flush=True)
    from jellyfin_transport import JellyfinTransport
    transport=JellyfinTransport(jelly,AUTH)
    from episode_sequence import EpisodeSequence
    sequence=EpisodeSequence(broker,transport,item_for,jelly)
    from private_world import PrivateWorldBridge
    world_bridge=PrivateWorldBridge(broker,jelly,item_for,AUTH)
    def watch_world():
        while True:
            time.sleep(.5)
            sid=world_bridge.check_world()
            if sid is not None:sequence.cancel(sid)
    threading.Thread(target=watch_world,daemon=True).start()
    ThreadingHTTPServer.allow_reuse_address=False
    ThreadingHTTPServer(('127.0.0.1',8097),Handler).serve_forever()






