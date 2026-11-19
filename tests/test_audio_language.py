import unittest
from audio_language import choose_audio
class AudioTests(unittest.TestCase):
 def test_english_beats_default_japanese(self):self.assertEqual(choose_audio([{'index':1,'tags':{'language':'jpn'},'disposition':{'default':1}},{'index':2,'tags':{'language':'eng'}}]),2)
 def test_main_dub_beats_english_commentary(self):self.assertEqual(choose_audio([{'index':2,'tags':{'language':'eng','title':'Commentary'}},{'index':3,'tags':{'language':'en-US','title':'English dub'}}]),3)
 def test_missing_english_keeps_existing_default(self):self.assertEqual(choose_audio([{'index':1,'tags':{'language':'jpn'}},{'index':2,'tags':{'language':'deu'},'disposition':{'default':1}}]),2)
if __name__=='__main__':unittest.main()
