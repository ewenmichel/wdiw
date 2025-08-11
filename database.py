# database.py - Enhanced version with new founder background fields
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Table, JSON, text
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

founder_tag_table = Table(
    'founder_tags',
    Base.metadata,
    Column('founder_id', Integer, ForeignKey('founders.id')),
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
    remuneration = Column(Integer, default=3)  # 1-5 scale (Underpaying, Below Market, At Market, Over Market, Overpaying)
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
    person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    
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
    tags = relationship("Tag", secondary=founder_tag_table, back_populates="founders")
    person = relationship("Person", back_populates="founder_roles")
    
    # Helper methods for template access
    def get_education_tags(self):
        """Get tags with category 'education'"""
        return [tag for tag in self.tags if tag.category == "education"]
    
    def get_professional_tags(self):
        """Get tags with category 'professional'"""
        return [tag for tag in self.tags if tag.category == "professional"]

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
    founders = relationship("Founder", secondary=founder_tag_table, back_populates="tags")

class CompanyRelation(Base):
    __tablename__ = "company_relations"
    
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("companies.id"))
    child_id = Column(Integer, ForeignKey("companies.id"))
    relation_type = Column(String, nullable=False)  # spinoff, parent, competitor, partner, alumni
    
    parent = relationship("Company", foreign_keys=[parent_id], back_populates="parent_relations")
    child = relationship("Company", foreign_keys=[child_id], back_populates="child_relations")

class Person(Base):
    __tablename__ = "people"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    
    # A person can be founder/employee in multiple companies (different roles)
    founder_roles = relationship("Founder", back_populates="person")

def create_tables():
    Base.metadata.create_all(bind=engine)
    migrate_schema()

def migrate_schema():
    """Lightweight migrations for SQLite to add new columns/tables if missing."""
    conn = engine.connect()
    try:
        # Ensure founders.person_id exists
        res = conn.execute(text("PRAGMA table_info(founders)"))
        cols = [row[1] for row in res]
        if 'person_id' not in cols:
            conn.execute(text("ALTER TABLE founders ADD COLUMN person_id INTEGER"))
            # Create index for faster lookups
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_founders_person_id ON founders(person_id)"))

        # Ensure people table exists (create_all above should create it)
        conn.execute(text("CREATE TABLE IF NOT EXISTS people (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL UNIQUE)"))

        # Backfill people from existing founders if they have no person_id
        # 1) Insert missing persons for distinct founder names
        conn.execute(text("INSERT OR IGNORE INTO people(name) SELECT DISTINCT name FROM founders WHERE name IS NOT NULL AND TRIM(name) <> ''"))
        # 2) Update founders.person_id by joining on name
        conn.execute(text("UPDATE founders SET person_id = (SELECT id FROM people p WHERE p.name = founders.name) WHERE person_id IS NULL"))
    finally:
        conn.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()