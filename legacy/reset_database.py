#!/usr/bin/env python3
"""
Script to reset the database with new schema including remuneration field and founder tags
"""
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

import database
import models
import crud
from sqlalchemy.orm import Session

def reset_database():
    """Drop all tables and recreate them with the new schema"""
    print("🔄 Resetting database...")
    
    # Remove existing database file
    db_file = "tech_companies.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Removed existing database file: {db_file}")
    
    # Recreate all tables with new schema
    database.create_tables()
    print("✅ Created new database tables with updated schema")
    
    # Insert sample data
    insert_sample_data()
    print("✅ Inserted sample data")
    
    print("🎉 Database reset completed successfully!")

def insert_sample_data():
    """Insert sample data with new fields"""
    try:
        db = next(database.get_db())
        
        print("📝 Inserting sample data...")
        
        # Kili Technology with new remuneration field
        kili_data = models.CompanyCreate(
            name="Kili Technology",
            website="https://kili-technology.com",
            description="Plateforme de data labeling et d'annotation pour l'IA d'entreprise",
            sector=models.SectorEnum.AI,
            location="Paris, France",
            high_profile=4,
            remuneration=4,  # Over Market
            work_intensity=models.WorkIntensityEnum.BALANCED,
            company_size=models.CompanySizeEnum.SCALEUP,
            founded_year=2018,
            last_funding="$30M+ Series A (2021)",
            founders=[
                models.FounderCreate(
                    name="François-Xavier Leduc", 
                    title="CEO & Co-founder", 
                    background_type=models.BackgroundTypeEnum.PROFESSIONAL,
                    professional_background=models.ProfessionalBackground(
                        company="Entrepreneur en série",
                        position="Various startups",
                        description="Serial entrepreneur with multiple successful exits"
                    ),
                    professional_tags=["Entrepreneur", "Startup"]
                ),
                models.FounderCreate(
                    name="Edouard d'Archimbaud", 
                    title="CTO & Co-founder", 
                    background_type=models.BackgroundTypeEnum.PROFESSIONAL,
                    professional_background=models.ProfessionalBackground(
                        company="BNP Paribas",
                        position="Head of AI Lab",
                        duration="2016-2018",
                        description="Built one of the most advanced AI Labs in Europe"
                    ),
                    professional_tags=["BNP Paribas", "AI Lab"]
                )
            ],
            investors=["Serena Capital", "Headline", "Balderton Capital", "Olivier Pomel (Datadog)", "Nicolas Dessaigne (Algolia)"],
            secteur_tags=["AI/ML", "Data"],
            core_business_tags=["Data Labeling", "Machine Learning"]
        )
        
        kili_company = crud.create_company(db, kili_data)
        print(f"✅ Created Kili Technology with ID: {kili_company.id}")
        
        # DeepIP with new fields
        deepip_data = models.CompanyCreate(
            name="DeepIP",
            website="https://deepip.ai",
            description="AI Patent Assistant intégré à Microsoft Word pour automatiser la rédaction de brevets",
            sector=models.SectorEnum.LEGALTECH,
            location="NYC & Paris",
            high_profile=5,
            remuneration=5,  # Overpaying
            work_intensity=models.WorkIntensityEnum.INTENSE,
            company_size=models.CompanySizeEnum.EARLY,
            founded_year=2024,
            last_funding="$15M Series A (2025)",
            founders=[
                models.FounderCreate(
                    name="François-Xavier Leduc", 
                    title="CEO & Co-founder", 
                    background_type=models.BackgroundTypeEnum.PROFESSIONAL,
                    professional_background=models.ProfessionalBackground(
                        company="Kili Technology",
                        position="CEO & Co-founder",
                        duration="2018-2024",
                        description="Successfully scaled Kili Technology to $30M+ Series A"
                    ),
                    professional_tags=["Kili Technology", "CEO"]
                ),
                models.FounderCreate(
                    name="Edouard d'Archimbaud", 
                    title="CTO & Co-founder", 
                    background_type=models.BackgroundTypeEnum.PROFESSIONAL,
                    professional_background=models.ProfessionalBackground(
                        company="Kili Technology",
                        position="CTO & Co-founder",
                        duration="2018-2024",
                        description="Led technical development of AI data platform"
                    ),
                    professional_tags=["Kili Technology", "CTO"]
                )
            ],
            investors=["Resonance", "Headline", "Serena Capital", "Balderton Capital"],
            secteur_tags=["LegalTech", "AI/ML"],
            core_business_tags=["Patent Assistant", "Legal AI"],
            relations=[
                models.CompanyRelationCreate(relation_type="spinoff", related_company_name="Kili Technology")
            ]
        )
        
        deepip_company = crud.create_company(db, deepip_data)
        print(f"✅ Created DeepIP with ID: {deepip_company.id}")
        
        # Add a third example with education background
        mistral_data = models.CompanyCreate(
            name="Mistral AI",
            website="https://mistral.ai",
            description="Créateur de modèles d'IA générative de pointe",
            location="Paris, France",
            high_profile=5,
            remuneration=4,  # Over Market
            work_intensity=models.WorkIntensityEnum.INTENSE,
            company_size=models.CompanySizeEnum.SCALEUP,
            founded_year=2023,
            last_funding="$415M Series A (2023)",
            founders=[
                models.FounderCreate(
                    name="Arthur Mensch", 
                    title="CEO & Co-founder", 
                    background_type=models.BackgroundTypeEnum.EDUCATION,
                    education_background=models.EducationBackground(
                        institution="École Normale Supérieure",
                        degree="PhD",
                        field="Machine Learning",
                        year=2020
                    ),
                    education_tags=["École Normale Supérieure", "ENS"]
                ),
                models.FounderCreate(
                    name="Guillaume Lample", 
                    title="Chief Scientist & Co-founder", 
                    background_type=models.BackgroundTypeEnum.PROFESSIONAL,
                    professional_background=models.ProfessionalBackground(
                        company="Meta AI",
                        position="Research Scientist",
                        duration="2017-2023",
                        description="Led research on large language models"
                    ),
                    professional_tags=["Meta", "Facebook AI"]
                )
            ],
            investors=["Andreessen Horowitz", "Lightspeed Venture Partners", "General Catalyst"],
            secteur_tags=["AI/ML", "DeepTech"],
            core_business_tags=["Large Language Models", "Generative AI"]
        )
        
        mistral_company = crud.create_company(db, mistral_data)
        print(f"✅ Created Mistral AI with ID: {mistral_company.id}")
        
        db.commit()
        
    except Exception as e:
        print(f"❌ Error inserting sample data: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_database()