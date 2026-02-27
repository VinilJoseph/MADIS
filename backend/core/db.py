from sqlalchemy import create_engine, Column, Integer, String, JSON, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging
import os

logger = logging.getLogger("core.db")

DATABASE_URL = "sqlite:///./agentic_pdf.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_time = Column(DateTime, default=datetime.utcnow)
    document_type = Column(String)
    summary = Column(Text)
    key_sections = Column(JSON)
    insights = Column(JSON)
    agent_trace = Column(JSON)
    session_id = Column(String, index=True)  # Link to analytics session

class AnalyticsSession(Base):
    __tablename__ = "analytics_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    filename = Column(String)
    start_timestamp = Column(DateTime, default=datetime.utcnow)
    end_timestamp = Column(DateTime)
    total_duration_seconds = Column(Float)
    
    # Token Usage
    total_tokens = Column(Integer)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    api_calls = Column(Integer)
    estimated_cost_usd = Column(Float)
    
    # Agent Execution
    total_agents = Column(Integer)
    successful_agents = Column(Integer)
    failed_agents = Column(Integer)
    
    # Detailed data stored as JSON
    token_details = Column(JSON)
    execution_details = Column(JSON)
    thinking_process = Column(JSON)
    session_metadata = Column(JSON)

def init_db():
    logger.info("Initializing database tables")
    Base.metadata.create_all(bind=engine)

def save_analysis(filename: str, result_data: dict, session_id: str = None):
    db = SessionLocal()
    try:
        db_record = AnalysisResult(
            filename=filename,
            document_type=result_data.get("document_type"),
            summary=result_data.get("summary"),
            key_sections=result_data.get("key_sections"),
            insights=result_data.get("insights"),
            agent_trace=result_data.get("agent_trace"),
            session_id=session_id
        )
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        return db_record.id
    except Exception as e:
        logger.exception("Error saving analysis to DB: %s", e)
    finally:
        db.close()

def save_analytics_session(analytics_report: dict):
    """Save analytics session data to database"""
    db = SessionLocal()
    try:
        token_usage = analytics_report.get('token_usage', {})
        agent_exec = analytics_report.get('agent_execution', {})
        
        db_record = AnalyticsSession(
            session_id=analytics_report['session_id'],
            filename=analytics_report.get('metadata', {}).get('filename'),
            start_timestamp=datetime.fromisoformat(analytics_report['start_timestamp']),
            end_timestamp=datetime.fromisoformat(analytics_report['end_timestamp']),
            total_duration_seconds=analytics_report['total_duration_seconds'],
            total_tokens=token_usage.get('total_tokens', 0),
            prompt_tokens=token_usage.get('prompt_tokens', 0),
            completion_tokens=token_usage.get('completion_tokens', 0),
            api_calls=token_usage.get('api_calls', 0),
            estimated_cost_usd=token_usage.get('estimated_cost_usd', 0),
            total_agents=agent_exec.get('total_agents', 0),
            successful_agents=agent_exec.get('successful_agents', 0),
            failed_agents=agent_exec.get('failed_agents', 0),
            token_details=token_usage,
            execution_details=agent_exec,
            thinking_process=analytics_report.get('thinking_process', {}),
            session_metadata=analytics_report.get('metadata', {})
        )
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        return db_record.id
    except Exception as e:
        logger.exception("Error saving analytics session to DB: %s", e)
    finally:
        db.close()

def get_analytics_sessions(limit: int = 10):
    """Retrieve recent analytics sessions"""
    db = SessionLocal()
    try:
        sessions = db.query(AnalyticsSession).order_by(
            AnalyticsSession.start_timestamp.desc()
        ).limit(limit).all()
        return sessions
    finally:
        db.close()

def get_analysis_by_session(session_id: str) -> dict | None:
    """Retrieve analysis result for a specific session_id (used by MCP)."""
    db = SessionLocal()
    try:
        record = db.query(AnalysisResult).filter(
            AnalysisResult.session_id == session_id
        ).first()
        if not record:
            return None
        return {
            "session_id": session_id,
            "filename": record.filename,
            "document_type": record.document_type,
            "summary": record.summary,
            "key_sections": record.key_sections,
            "insights": record.insights,
            "agent_trace": record.agent_trace,
            "upload_time": record.upload_time.isoformat() if record.upload_time else None,
        }
    finally:
        db.close()


def get_analytics_summary():
    """Get summary statistics of all analytics sessions"""
    db = SessionLocal()
    try:
        sessions = db.query(AnalyticsSession).all()
        
        if not sessions:
            return {
                'total_sessions': 0,
                'total_tokens': 0,
                'total_cost': 0,
                'average_duration': 0
            }
        
        total_tokens = sum(s.total_tokens or 0 for s in sessions)
        total_cost = sum(s.estimated_cost_usd or 0 for s in sessions)
        total_duration = sum(s.total_duration_seconds or 0 for s in sessions)
        
        return {
            'total_sessions': len(sessions),
            'total_tokens': total_tokens,
            'total_cost': round(total_cost, 6),
            'average_duration': round(total_duration / len(sessions), 2),
            'total_api_calls': sum(s.api_calls or 0 for s in sessions)
        }
    finally:
        db.close()

