# crud.py - Enhanced version with structured founder backgrounds
from sqlalchemy.orm import Session
from sqlalchemy import or_
import models
import database
import re

def create_slug(name: str) -> str:
    """Create a URL-friendly slug from company name"""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

def get_company(db: Session, company_id: int):
    return db.query(database.Company).filter(database.Company.id == company_id).first()

def get_company_by_slug(db: Session, slug: str):
    return db.query(database.Company).filter(database.Company.slug == slug).first()

def get_companies(db: Session, skip: int = 0, limit: int = 100, search: str = None):
    query = db.query(database.Company)
    
    if search:
        query = query.filter(
            or_(
                database.Company.name.contains(search),
                database.Company.sector.contains(search),
                database.Company.location.contains(search)
            )
        )
    
    return query.offset(skip).limit(limit).all()

def create_company(db: Session, company: models.CompanyCreate):
    # Create company
    db_company = database.Company(
        name=company.name,
        slug=create_slug(company.name),
        website=company.website,
        description=company.description,
        sector=company.sector.value if company.sector else None,  # Convert enum to string
        location=company.location,
        high_profile=company.high_profile,
        remuneration=company.remuneration,
        work_intensity=company.work_intensity.value,  # Convert enum to string
        company_size=company.company_size.value,  # Convert enum to string
        founded_year=company.founded_year,
        last_funding=company.last_funding
    )
    
    db.add(db_company)
    db.flush()  # Get the ID
    
    # Add founders with structured backgrounds and person linking
    for founder_data in company.founders:
        person = get_or_create_person(db, founder_data)
        founder = database.Founder(
            name=founder_data.name,
            title=founder_data.title,
            background_type=founder_data.background_type.value if founder_data.background_type else None,
            background=founder_data.background,
            company_id=db_company.id,
            person_id=person.id if person else None
        )
        
        # Add education background fields
        if founder_data.education_background:
            founder.education_institution = founder_data.education_background.institution
            founder.education_degree = founder_data.education_background.degree
            founder.education_field = founder_data.education_background.field
            founder.education_year = founder_data.education_background.year
        
        # Add professional background fields
        if founder_data.professional_background:
            founder.professional_company = founder_data.professional_background.company
            founder.professional_position = founder_data.professional_background.position
            founder.professional_duration = founder_data.professional_background.duration
            founder.professional_description = founder_data.professional_background.description
        
        db.add(founder)
        db.flush()
        
        # Add education tags
        if hasattr(founder_data, 'education_tags') and founder_data.education_tags:
            for tag_name in founder_data.education_tags:
                if tag_name.strip():
                    tag = get_or_create_tag(db, tag_name.strip(), "education")
                    founder.tags.append(tag)
                    update_tag_usage_count(db, tag.id, 1)
        
        # Add professional tags
        if hasattr(founder_data, 'professional_tags') and founder_data.professional_tags:
            for tag_name in founder_data.professional_tags:
                if tag_name.strip():
                    tag = get_or_create_tag(db, tag_name.strip(), "professional")
                    founder.tags.append(tag)
                    update_tag_usage_count(db, tag.id, 1)

        # Propagate this founder profile to all other founder roles for the same person
        if founder.person_id:
            propagate_founder_profile(db, founder)
    
    # Add investors
    for investor_name in company.investors:
        investor = db.query(database.Investor).filter(database.Investor.name == investor_name).first()
        if not investor:
            investor = database.Investor(name=investor_name)
            db.add(investor)
            db.flush()
        
        db_company.investors.append(investor)
    
    # Add secteur tags
    for tag_name in company.secteur_tags:
        if tag_name.strip():
            tag = get_or_create_tag(db, tag_name.strip(), "secteur")
            db_company.tags.append(tag)
            update_tag_usage_count(db, tag.id, 1)
    
    # Add core business tags
    for tag_name in company.core_business_tags:
        if tag_name.strip():
            tag = get_or_create_tag(db, tag_name.strip(), "core_business")
            db_company.tags.append(tag)
            update_tag_usage_count(db, tag.id, 1)
    
    # Add relations
    for relation_data in company.relations:
        related_company = db.query(database.Company).filter(
            database.Company.name == relation_data.related_company_name
        ).first()
        
        if related_company:
            if relation_data.relation_type == "spinoff":
                # Current company is a spinoff of related_company
                relation = database.CompanyRelation(
                    parent_id=related_company.id,
                    child_id=db_company.id,
                    relation_type="spinoff"
                )
            elif relation_data.relation_type == "parent":
                # Current company is parent of related_company
                relation = database.CompanyRelation(
                    parent_id=db_company.id,
                    child_id=related_company.id,
                    relation_type="spinoff"
                )
            else:
                # Generic relation
                relation = database.CompanyRelation(
                    parent_id=db_company.id,
                    child_id=related_company.id,
                    relation_type=relation_data.relation_type
                )
            
            db.add(relation)
    
    db.commit()
    db.refresh(db_company)
    return db_company

def update_company(db: Session, company_id: int, company_update: models.CompanyUpdate):
    db_company = get_company(db, company_id)
    if not db_company:
        return None
    
    # Update basic fields
    update_data = company_update.dict(exclude_unset=True, exclude={'founders', 'investors', 'relations'})
    for field, value in update_data.items():
        # Convert enum values to strings
        if hasattr(value, 'value'):
            value = value.value
        setattr(db_company, field, value)
    
    # Update slug if name changed
    if company_update.name:
        db_company.slug = create_slug(company_update.name)
    
    # Update founders if provided
    if company_update.founders is not None:
        # Delete existing founders
        db.query(database.Founder).filter(database.Founder.company_id == company_id).delete()

        # Add new founders with person linking
        for founder_data in company_update.founders:
            person = get_or_create_person(db, founder_data)
            founder = database.Founder(
                name=founder_data.name,
                title=founder_data.title,
                background_type=founder_data.background_type.value if founder_data.background_type else None,
                background=founder_data.background,
                company_id=company_id,
                person_id=person.id if person else None
            )

            # Add education background fields
            if founder_data.education_background:
                founder.education_institution = founder_data.education_background.institution
                founder.education_degree = founder_data.education_background.degree
                founder.education_field = founder_data.education_background.field
                founder.education_year = founder_data.education_background.year

            # Add professional background fields
            if founder_data.professional_background:
                founder.professional_company = founder_data.professional_background.company
                founder.professional_position = founder_data.professional_background.position
                founder.professional_duration = founder_data.professional_background.duration
                founder.professional_description = founder_data.professional_background.description

            db.add(founder)
            db.flush()

            # Sync tags from input
            if hasattr(founder_data, 'education_tags') and founder_data.education_tags:
                for tag_name in founder_data.education_tags:
                    if tag_name.strip():
                        tag = get_or_create_tag(db, tag_name.strip(), "education")
                        founder.tags.append(tag)
                        update_tag_usage_count(db, tag.id, 1)

            if hasattr(founder_data, 'professional_tags') and founder_data.professional_tags:
                for tag_name in founder_data.professional_tags:
                    if tag_name.strip():
                        tag = get_or_create_tag(db, tag_name.strip(), "professional")
                        founder.tags.append(tag)
                        update_tag_usage_count(db, tag.id, 1)

            # Propagate to other founder roles for the same person
            if founder.person_id:
                propagate_founder_profile(db, founder)
    
    # Update investors if provided
    if company_update.investors is not None:
        # Clear existing associations
        db_company.investors.clear()
        
        # Add new investors
        for investor_name in company_update.investors:
            investor = db.query(database.Investor).filter(database.Investor.name == investor_name).first()
            if not investor:
                investor = database.Investor(name=investor_name)
                db.add(investor)
                db.flush()
            
            db_company.investors.append(investor)
    
    # Update tags if provided
    if company_update.secteur_tags is not None or company_update.core_business_tags is not None:
        # Decrement usage count for existing tags
        for tag in db_company.tags:
            update_tag_usage_count(db, tag.id, -1)
        
        # Clear existing tag associations
        db_company.tags.clear()
        
        # Add new secteur tags
        if company_update.secteur_tags is not None:
            for tag_name in company_update.secteur_tags:
                if tag_name.strip():
                    tag = get_or_create_tag(db, tag_name.strip(), "secteur")
                    db_company.tags.append(tag)
                    update_tag_usage_count(db, tag.id, 1)
        
        # Add new core business tags
        if company_update.core_business_tags is not None:
            for tag_name in company_update.core_business_tags:
                if tag_name.strip():
                    tag = get_or_create_tag(db, tag_name.strip(), "core_business")
                    db_company.tags.append(tag)
                    update_tag_usage_count(db, tag.id, 1)
    
    db.commit()
    db.refresh(db_company)
    return db_company

def delete_company(db: Session, company_id: int):
    db_company = get_company(db, company_id)
    if db_company:
        db.delete(db_company)
        db.commit()
    return db_company

# Tag CRUD operations
def get_tags(db: Session, category: str = None, skip: int = 0, limit: int = 100):
    query = db.query(database.Tag)
    
    if category:
        query = query.filter(database.Tag.category == category)
    
    return query.order_by(database.Tag.usage_count.desc(), database.Tag.name).offset(skip).limit(limit).all()

def get_tag_by_name_and_category(db: Session, name: str, category: str):
    return db.query(database.Tag).filter(
        database.Tag.name == name, 
        database.Tag.category == category
    ).first()

def create_tag(db: Session, tag: models.TagCreate):
    db_tag = database.Tag(
        name=tag.name,
        category=tag.category.value,
        color=tag.color
    )
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

def get_or_create_tag(db: Session, name: str, category: str, color: str = "#64b5f6"):
    # Try to get existing tag
    tag = get_tag_by_name_and_category(db, name, category)
    
    if not tag:
        # Create new tag
        tag_data = models.TagCreate(name=name, category=category, color=color)
        tag = create_tag(db, tag_data)
    
    return tag

def update_tag_usage_count(db: Session, tag_id: int, increment: int = 1):
    tag = db.query(database.Tag).filter(database.Tag.id == tag_id).first()
    if tag:
        tag.usage_count = max(0, tag.usage_count + increment)
        db.commit()
        db.refresh(tag)
    return tag

def search_tags(db: Session, query: str, category: str = None, limit: int = 10):
    """Search tags by name for autocomplete suggestions"""
    search_query = db.query(database.Tag).filter(
        database.Tag.name.contains(query)
    )
    
    if category:
        search_query = search_query.filter(database.Tag.category == category)
    
    return search_query.order_by(database.Tag.usage_count.desc()).limit(limit).all()

# PERSON CRUD
def get_person_by_id(db: Session, person_id: int):
    return db.query(database.Person).filter(database.Person.id == person_id).first()

def get_person_by_name(db: Session, name: str):
    return db.query(database.Person).filter(database.Person.name == name).first()

def create_person(db: Session, name: str):
    person = database.Person(name=name)
    db.add(person)
    db.flush()
    return person

def get_or_create_person(db: Session, founder_data: models.FounderCreate):
    # Prefer explicit person_id when provided
    if getattr(founder_data, 'person_id', None):
        person = get_person_by_id(db, founder_data.person_id)
        if person:
            # Keep person name as source of truth if founder name changed
            if founder_data.name and person.name != founder_data.name:
                person.name = founder_data.name
                db.flush()
            return person
    # Otherwise match by exact name
    if founder_data.name:
        person = get_person_by_name(db, founder_data.name)
        if person:
            return person
        return create_person(db, founder_data.name)
    return None

def propagate_founder_profile(db: Session, source_founder: database.Founder):
    """
    Propagate canonical person-bound fields from source_founder to all other founder roles
    of the same person across companies (name, background fields, and related tags).
    """
    # Ensure person exists
    if not source_founder.person_id:
        return
    # Update Person name to match the latest source_founder name
    person = get_person_by_id(db, source_founder.person_id)
    if person and person.name != source_founder.name:
        person.name = source_founder.name
        db.flush()

    # Fetch all other founder roles linked to this person
    other_founders = db.query(database.Founder).filter(
        database.Founder.person_id == source_founder.person_id,
        database.Founder.id != source_founder.id
    ).all()

    for other in other_founders:
        # Name sync
        other.name = source_founder.name
        other.background_type = source_founder.background_type

        # Education background sync
        other.education_institution = source_founder.education_institution
        other.education_degree = source_founder.education_degree
        other.education_field = source_founder.education_field
        other.education_year = source_founder.education_year

        # Professional background sync
        other.professional_company = source_founder.professional_company
        other.professional_position = source_founder.professional_position
        other.professional_duration = source_founder.professional_duration
        other.professional_description = source_founder.professional_description

        # Tags sync: replace all education/professional tags to match source
        # First, collect target tag IDs by category from source
        source_edu_tag_ids = {t.id for t in source_founder.tags if t.category == 'education'}
        source_pro_tag_ids = {t.id for t in source_founder.tags if t.category == 'professional'}

        # Remove existing education/professional tags
        other.tags = [t for t in other.tags if t.category not in ('education', 'professional')]

        # Attach source tags
        if source_edu_tag_ids or source_pro_tag_ids:
            all_needed_tag_ids = list(source_edu_tag_ids | source_pro_tag_ids)
            if all_needed_tag_ids:
                tags = db.query(database.Tag).filter(database.Tag.id.in_(all_needed_tag_ids)).all()
                for t in tags:
                    other.tags.append(t)

    db.flush()