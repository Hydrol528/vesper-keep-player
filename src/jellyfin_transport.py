"""Selected-video-only proxy for Jellyfin's native finite HLS playback service.
Tokens, media IDs and internal URLs remain in memory on this local connector.
"""
import hashlib,json,re,secrets,threading,time,urllib.parse,urllib.request
from pathlib import Path
from playback_common import CACHE,PreparationError
from audio_language import choose_audio
from server_connection import server_url, normalize_server
class Done:
 returncode=0
 def poll(self):return 0
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise PreparationError('Unexpected stream redirect')
class JellyfinTransport:
 requires_session=True
 def __init__(self,jelly,auth):
  self.jelly=jelly;self.auth=auth;self.lock=threading.RLock();self.jobs={};self.run=CACHE/('jellyfin-'+secrets.token_hex(8));self.run.mkdir(parents=True);self.opener=urllib.request.build_opener(NoRedirect)
 def prepare(self,item,revision,session=None):
  if not session or not session.get('token'):raise PreparationError('Connect your library first')
  server=server_url(session)
  streams=item.get('MediaStreams') or next((x.get('MediaStreams',[]) for x in item.get('MediaSources',[]) if x.get('MediaStreams')),[])
  audio_index=choose_audio([{'codec_type':'audio','index':x['Index'],'tags':{'language':x.get('Language',''),'title':x.get('Title','')},'disposition':{'default':x.get('IsDefault',False)}} for x in streams if x.get('Type')=='Audio'])
  device='vesper-'+secrets.token_hex(12)
  profile={'Name':'Vesper PC and Quest HLS','MaxStreamingBitrate':4200000,'DirectPlayProfiles':[], 'TranscodingProfiles':[{'Container':'ts','Type':'Video','VideoCodec':'h264','AudioCodec':'aac','Protocol':'hls','Context':'Streaming','MaxAudioChannels':'2','MinSegments':2,'SegmentLength':4,'BreakOnNonKeyFrames':False}]}
  body={'UserId':session['user'],'DeviceProfile':profile,'MaxStreamingBitrate':4200000,'MaxAudioChannels':2,'EnableDirectPlay':False,'EnableDirectStream':False,'EnableTranscoding':True,'AllowVideoStreamCopy':False,'AllowAudioStreamCopy':False,'SubtitleStreamIndex':-1}
  body['AudioStreamIndex']=audio_index
  reply=self.jelly('/Items/'+item['Id']+'/PlaybackInfo?'+urllib.parse.urlencode({'userId':session['user'],'audioStreamIndex':audio_index,'maxAudioChannels':2}),session['token'],body=body,method='POST',server=server)
  source=next((x for x in reply.get('MediaSources',[]) if x.get('TranscodingUrl') and not x.get('IsInfiniteStream')),None)
  if not source:raise PreparationError('Jellyfin did not provide a seekable video stream')
  url=self.validate_url(urllib.parse.urljoin(server+'/',source['TranscodingUrl']),server)
  # Limit the decoder profile independently of server defaults.
  parsed=urllib.parse.urlsplit(url);query={k:v for k,v in urllib.parse.parse_qs(parsed.query).items() if k.lower() not in ('audiostreamindex','maxwidth','maxheight','videobitrate','audiobitrate','transcodingmaxaudiochannels','deviceid')};query.update(AudioStreamIndex=[str(audio_index)],MaxWidth=['1280'],MaxHeight=['720'],VideoBitrate=['4000000'],AudioBitrate=['160000'],TranscodingMaxAudioChannels=['2'],DeviceId=[device]);url=urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query,doseq=True)))
  with self.lock:
   slot=len(self.jobs)
   if slot>=32:raise PreparationError('Local playback slots are full')
   folder=self.run/str(slot);folder.mkdir()
   self.jobs[slot]={'process':Done(),'seekable':True,'folder':folder,'revision':revision,'until':time.time()+21600,'token':session['token'],'server':server,'urls':{'index.m3u8':url},'locks':{},'device':device,'playSession':reply.get('PlaySessionId',''),'revoked':False}
  self.resource(slot,'index.m3u8')
  return slot
 @staticmethod
 def validate_url(url,server):
  p=urllib.parse.urlsplit(url)
  b=urllib.parse.urlsplit(normalize_server(server))
  if any(x in (".","..") for x in p.path.split("/")) or "%" in p.path:raise PreparationError("Invalid stream path")
  if (p.scheme,p.hostname,p.port)!=(b.scheme,b.hostname,b.port) or p.username or p.password or p.fragment or not p.path.lower().startswith(b.path.lower().rstrip('/')+'/videos/'):raise PreparationError('Unexpected stream endpoint')
  return url
 def mapped(self,slot,base,relative):
  url=self.validate_url(urllib.parse.urljoin(base,relative),self.jobs[slot]['server']);ext='.m3u8' if urllib.parse.urlsplit(url).path.lower().endswith('.m3u8') else '.ts';name='r'+hashlib.sha256(url.encode()).hexdigest()[:24]+ext
  with self.lock:
   job=self.jobs[slot]
   if len(job['urls'])>=20000 and name not in job['urls']:raise PreparationError('Stream resource limit exceeded')
   job['urls'][name]=url
  return '/watch/'+str(slot)+'/'+name
 def rewrite(self,slot,base,text):
  lines=[]
  for line in text.splitlines():
   if line and not line.startswith('#'):line=self.mapped(slot,base,line.strip())
   elif 'URI="' in line:line=re.sub(r'URI="([^"]+)"',lambda m:'URI="'+self.mapped(slot,base,m[1])+'"',line)
   lines.append(line)
  return '\n'.join(lines)+'\n'
 def resource(self,slot,name):
  if not re.fullmatch(r'index\.m3u8|r[a-f0-9]{24}\.(?:m3u8|ts)',name):raise PreparationError('Invalid stream resource')
  with self.lock:
   job=self.jobs.get(slot)
   if not job or job['revoked'] or job['until']<=time.time() or name not in job['urls']:raise PreparationError('Stream unavailable')
   gate=job['locks'].setdefault(name,threading.Lock())
  with gate:
   target=job['folder']/name
   if target.exists() and not name.endswith('.m3u8'):return target
   request=urllib.request.Request(job['urls'][name],headers={'Authorization':self.auth+', Token="'+job['token']+'"'})
   try:
    with self.opener.open(request,timeout=35) as response:data=response.read(32*1024*1024+1)
   except Exception as error:raise PreparationError('Jellyfin could not supply this video segment') from error
   if len(data)>32*1024*1024:raise PreparationError('Stream resource too large')
   if name.endswith('.m3u8'):
    text=data.decode('utf-8-sig')
    if not text.startswith('#EXTM3U'):raise PreparationError('Invalid video playlist')
    data=self.rewrite(slot,job['urls'][name],text).encode()
   with self.lock:
    if job['revoked']:raise PreparationError('Stream revoked')
    tmp=target.with_suffix(target.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(target)
   return target
 def stop_preparing(self,slots):
  for slot in slots:
   with self.lock:
    job=self.jobs.get(slot)
    if not job or job['revoked']:continue
    job['revoked']=True
   try:self.jelly('/Videos/ActiveEncodings?'+urllib.parse.urlencode({'deviceId':job['device'],'playSessionId':job['playSession']}),job['token'],method='DELETE',server=job['server'])
   except Exception:pass
 def close(self):self.stop_preparing(list(self.jobs))
