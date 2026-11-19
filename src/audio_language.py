"""Choose audio using Jellyfin metadata, without reading source files."""
from playback_common import PreparationError

def choose_audio(streams):
 audio=[s for s in streams if s.get('codec_type','audio')=='audio']
 if not audio:raise PreparationError('Selected video has no audio track')
 def english(s):return str(s.get('tags',{}).get('language','')).lower().replace('_','-') in ('eng','en','english','en-us','en-gb')
 main=[s for s in audio if english(s) and 'commentary' not in str(s.get('tags',{}).get('title','')).lower()]
 choices=main or [s for s in audio if english(s)] or [s for s in audio if s.get('disposition',{}).get('default')] or audio
 index=int(choices[0]['index'])
 if not 0<=index<=128:raise PreparationError('Invalid audio track')
 return index
