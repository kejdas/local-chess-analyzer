from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func
from .database import Base

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    chess_com_id = Column(String, unique=True, nullable=False, index=True)
    pgn = Column(Text, nullable=False)
    white_player = Column(String)
    black_player = Column(String)
    result = Column(String)
    game_date = Column(String)
    import_date = Column(TIMESTAMP, server_default=func.now())
    analysis_status = Column(String, default='queued')
    analysis_data = Column(Text)

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, unique=True, nullable=False)
    value = Column(String)
    
