import sys
sys.path.insert(0, ".")
from sqlmodel import Session, select
from app.db import engine
from app.models import Topic, SourceDocument
from app.rag.vectorstore import get_vectorstore

with Session(engine) as db:
    topic = db.exec(select(Topic).where(Topic.title == "Uploaded Test Topic")).first()
    if topic:
        docs = db.exec(select(SourceDocument).where(SourceDocument.topic_id == topic.id)).all()
        for d in docs:
            db.delete(d)
        get_vectorstore().delete(where={"topic_id": topic.id})
        db.delete(topic)
        db.commit()
        print(f"deleted topic {topic.id} and its material")
    else:
        print("not found")
