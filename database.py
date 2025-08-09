# database.py - Enhanced version with new founder background fields
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Table, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./tech_companies.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Association tables for many-to-many relationships
company_investor_table = Table(
    'company_investors',
    Base.metadata,
    Column('company_id', Integer, ForeignKey('companies.id')),
    Column('investor_id', Integer, ForeignKey('investors.id'))
)

company_tag_table = Table(
    'company_tags',
    Base.metadata,
    Column('company_id', Integer, ForeignKey('companies.id')),
    Column('tag_id', Integer, ForeignKey('tags.id')),
    Column('created_at', DateTime, default=datetime.utcnow)
)

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True)
    website = Column(String)
    description = Column(Text)
    sector = Column(String)  # Will store enum values
    location = Column(String)
    
    # Criteria
    high_profile = Column(Integer, default=3)  # 1-5 scale
    work_intensity = Column(String, default="balanced")  # chill, balanced, intense, bourrin
    company_size = Column(String, default="startup")  # early, startup, scaleup, corp
    
    # Financial data
    founded_year = Column(Integer)
    last_funding = Column(String)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    founders = relationship("Founder", back_populates="company", cascade="all, delete-orphan")
    investors = relationship("Investor", secondary=company_investor_table, back_populates="companies")
    tags = relationship("Tag", secondary=company_tag_table, back_populates="companies")
    
    # Relations with other companies
    parent_relations = relationship("CompanyRelation", foreign_keys="CompanyRelation.parent_id", back_populates="parent")
    child_relations = relationship("CompanyRelation", foreign_keys="CompanyRelation.child_id", back_populates="child")
    
    # Helper methods for template access
    def get_secteur_tags(self):
        """Get tags with category 'secteur'"""
        return [tag for tag in self.tags if tag.category == "secteur"]
    
    def get_core_business_tags(self):
        """Get tags with category 'core_business'"""
        return [tag for tag in self.tags if tag.category == "core_business"]

class Founder(Base):
    __tablename__ = "founders"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    title = Column(String)
    
    # Background information
    background_type = Column(String)  # 'education' or 'professional'
    
    # Education background (stored as JSON)
    education_institution = Column(String)
    education_degree = Column(String)
    education_field = Column(String)
    education_year = Column(Integer)
    
    # Professional background (stored as JSON)
    professional_company = Column(String)
    professional_position = Column(String)
    professional_duration = Column(String)
    professional_description = Column(Text)
    
    # Legacy field for backward compatibility
    background = Column(Text)
    
    company_id = Column(Integer, ForeignKey("companies.id"))
    company = relationship("Company", back_populates="founders")

class Investor(Base):
    __tablename__ = "investors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String)  # VC, Angel, Corporate, etc.
    
    companies = relationship("Company", secondary=company_investor_table, back_populates="investors")

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)  # 'secteur' or 'core_business'
    color = Column(String, default="#64b5f6")  # Default blue color
    usage_count = Column(Integer, default=0)  # Track how many companies use this tag
    created_at = Column(DateTime, default=datetime.utcnow)
    
    companies = relationship("Company", secondary=company_tag_table, back_populates="tags")

class CompanyRelation(Base):
    __tablename__ = "company_relations"
    
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("companies.id"))
    child_id = Column(Integer, ForeignKey("companies.id"))
    relation_type = Column(String, nullable=False)  # spinoff, parent, competitor, partner, alumni
    
    parent = relationship("Company", foreign_keys=[parent_id], back_populates="parent_relations")
    child = relationship("Company", foreign_keys=[child_id], back_populates="child_relations")

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()