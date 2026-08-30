import sys
sys.path.insert(0, ".")
from sqlmodel import Session, select
from app.db import engine
from app.models import ScriptCache, AudioCache

with Session(engine) as db:
    script = db.exec(select(ScriptCache).order_by(ScriptCache.id.desc())).first()
    print(f"word_count={script.word_count}, status={script.status}")
    audio = db.exec(select(AudioCache).where(AudioCache.script_cache_id == script.id)).first()
    print(f"duration_seconds={audio.duration_seconds}, status={audio.status}")
