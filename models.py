# models.py - Enhanced version with sectors and structured backgrounds
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

# Enums for predefined choices
class TagCategoryEnum(str, Enum):
    SECTEUR = "secteur"
    CORE_BUSINESS = "core_business"
    EDUCATION = "education"
    PROFESSIONAL = "professional"

# Keep SectorEnum for backward compatibility and migration
class SectorEnum(str, Enum):
    AI = "AI/ML"
    FINTECH = "FinTech"
    EDTECH = "EdTech"
    HEALTHTECH = "HealthTech"
    LEGALTECH = "LegalTech"
    AUTOMOBILE = "Automobile"
    ECOMMERCE = "E-commerce"
    CYBERSECURITY = "Cybersécurité"
    BLOCKCHAIN = "Blockchain/Crypto"
    DEEPTECH = "DeepTech"
    SAAS = "SaaS/Enterprise"
    MOBILITY = "Mobilité"
    ENERGY = "Énergie"
    AGTECH = "AgTech"
    PROPTECH = "PropTech"
    FOODTECH = "FoodTech"
    CLIMATE = "ClimaTech"
    GAMING = "Gaming/Entertainment"
    MEDIA = "Média/Content"
    OTHER = "Autre"

class WorkIntensityEnum(str, Enum):
    CHILL = "chill"
    BALANCED = "balanced"
    INTENSE = "intense"
    BOURRIN = "bourrin"

class CompanySizeEnum(str, Enum):
    EARLY = "early"
    STARTUP = "startup"
    SCALEUP = "scaleup"
    CORP = "corp"

class BackgroundTypeEnum(str, Enum):
    EDUCATION = "education"
    PROFESSIONAL = "professional"

# Background models
class EducationBackground(BaseModel):
    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    year: Optional[int] = None

class ProfessionalBackground(BaseModel):
    company: str
    position: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None

class FounderBackground(BaseModel):
    type: BackgroundTypeEnum
    education: Optional[EducationBackground] = None
    professional: Optional[ProfessionalBackground] = None

class FounderBase(BaseModel):
    person_id: Optional[int] = None
    name: str
    title: Optional[str] = None
    background_type: Optional[BackgroundTypeEnum] = None
    education_background: Optional[EducationBackground] = None
    professional_background: Optional[ProfessionalBackground] = None
    
    # Tag system for backgrounds
    education_tags: List[str] = []  # List of education institution tags
    professional_tags: List[str] = []  # List of professional company tags
    
    # Legacy field for backward compatibility
    background: Optional[str] = None

class FounderCreate(FounderBase):
    pass

class Founder(FounderBase):
    id: int
    company_id: int
    
    class Config:
        from_attributes = True

class PersonBase(BaseModel):
    name: str

class Person(PersonBase):
    id: int
    
    class Config:
        from_attributes = True

class InvestorBase(BaseModel):
    name: str
    type: Optional[str] = None

class InvestorCreate(InvestorBase):
    pass

class Investor(InvestorBase):
    id: int
    
    class Config:
        from_attributes = True

# Tag models
class TagBase(BaseModel):
    name: str
    category: TagCategoryEnum
    color: Optional[str] = "#64b5f6"

class TagCreate(TagBase):
    pass

class TagUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[TagCategoryEnum] = None
    color: Optional[str] = None

class Tag(TagBase):
    id: int
    usage_count: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True

class CompanyRelationBase(BaseModel):
    relation_type: str
    related_company_name: str

class CompanyRelationCreate(CompanyRelationBase):
    pass

class CompanyBase(BaseModel):
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    # Keep sector for backward compatibility during migration
    sector: Optional[SectorEnum] = None
    location: Optional[str] = None
    high_profile: int = Field(default=3, ge=1, le=5)
    remuneration: int = Field(default=3, ge=1, le=5)
    work_intensity: WorkIntensityEnum = Field(default=WorkIntensityEnum.BALANCED)
    company_size: CompanySizeEnum = Field(default=CompanySizeEnum.STARTUP)
    founded_year: Optional[int] = None
    last_funding: Optional[str] = None

class CompanyCreate(CompanyBase):
    founders: List[FounderCreate] = []
    investors: List[str] = []  # List of investor names
    relations: List[CompanyRelationCreate] = []
    # New tag system
    secteur_tags: List[str] = []  # List of tag names for secteur category
    core_business_tags: List[str] = []  # List of tag names for core_business category

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    sector: Optional[SectorEnum] = None
    location: Optional[str] = None
    high_profile: Optional[int] = Field(None, ge=1, le=5)
    remuneration: Optional[int] = Field(None, ge=1, le=5)
    work_intensity: Optional[WorkIntensityEnum] = None
    company_size: Optional[CompanySizeEnum] = None
    founded_year: Optional[int] = None
    last_funding: Optional[str] = None
    founders: Optional[List[FounderCreate]] = None
    investors: Optional[List[str]] = None
    relations: Optional[List[CompanyRelationCreate]] = None
    # New tag system
    secteur_tags: Optional[List[str]] = None
    core_business_tags: Optional[List[str]] = None

class Company(CompanyBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    founders: List[Founder] = []
    investors: List[Investor] = []
    tags: List[Tag] = []
    
    class Config:
        from_attributes = True
    
    # Helper methods for template access
    def get_secteur_tags(self) -> List[Tag]:
        return [tag for tag in self.tags if tag.category == "secteur"]
    
    def get_core_business_tags(self) -> List[Tag]:
        return [tag for tag in self.tags if tag.category == "core_business"]