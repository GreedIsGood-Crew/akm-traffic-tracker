from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


class LandingMood(enum.Enum):
    link = "link"
    mirror = "mirror"
    local_file = "local_file"


class CampaignStatus(enum.Enum):
    active = "active"
    paused = "paused"


class CampaignType(enum.Enum):
    campaign = "campaign"
    direct = "direct"


class RedirectMode(enum.Enum):
    direct = "direct"
    meta = "meta"
    js = "js"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    alias = Column(String(255), unique=True, nullable=False)
    type = Column(Enum(CampaignType, name='campaign_type', create_type=False), nullable=True)
    status = Column(Enum(CampaignStatus, name='campaign_status', create_type=False), nullable=True)
    redirect_mode = Column(Enum(RedirectMode, name='redirect_mode_type', create_type=False), nullable=True)
    domain_id = Column(Integer, nullable=True)
    traffic_source_id = Column(Integer, nullable=True)
    config = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)
    group_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Landing(Base):
    __tablename__ = "landings"

    id = Column(Integer, primary_key=True, index=True)
    folder = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), unique=True, nullable=False)
    link = Column(String(255), nullable=True)
    type = Column(Enum(LandingMood, name='landing_mood', create_type=False), nullable=True)
    tags = Column(String(255), nullable=True)
    group_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
