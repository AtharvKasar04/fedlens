import json
from datetime import datetime
from app.db.session import SessionLocal
from app.db.models import FOMCMeeting, FOMCDocument, PolicyAssessment

def view_database():
    db = SessionLocal()
    try:
        print("\n" + "="*50)
        print("🏛️  FEDLENS DATABASE VIEWER")
        print("="*50)
        
        # 1. Show Meetings
        meetings = db.query(FOMCMeeting).order_by(FOMCMeeting.meeting_date.desc()).all()
        print(f"\n[1] MEETINGS SAVED: {len(meetings)}")
        for m in meetings:
            print(f"    - Meeting Date: {m.meeting_date}")
            
        # 2. Show Documents
        docs = db.query(FOMCDocument).all()
        print(f"\n[2] DOCUMENTS SAVED: {len(docs)}")
        for d in docs:
            print(f"    - Type: {d.doc_type} | Words: {d.word_count} | URL: {d.source_url}")
            
        # 3. Show AI Assessments
        assessments = db.query(PolicyAssessment).all()
        print(f"\n[3] AI ASSESSMENTS COMPLETED: {len(assessments)}")
        for a in assessments:
            meeting_date = db.query(FOMCMeeting).filter(FOMCMeeting.id == a.meeting_id).first().meeting_date
            print(f"    - Assessment for meeting on {meeting_date}:")
            
            # Print the JSON output cleanly
            if a.raw_llm_output:
                formatted_json = json.dumps(a.raw_llm_output, indent=4)
                print(f"{formatted_json}\n")
                
    except Exception as e:
        print(f"Error reading database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    view_database()
