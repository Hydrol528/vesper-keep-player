"""Writable runtime data belongs to this installation; credentials stay in RAM."""
import os,sys
from pathlib import Path
DATA=Path(os.environ.get('VESPER_DATA_DIR',str(Path(sys.executable).resolve().parent/'Data') if getattr(sys,'frozen',False) else str(Path(__file__).resolve().parent/'Data')))
CACHE=DATA/'cache'
WORK=DATA/'temp'
