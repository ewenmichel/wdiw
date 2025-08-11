# main.py - Debug version with better error handling
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import traceback

# Fixed imports
import crud
import models
import database

app = FastAPI(title="Tech Companies Database", version="1.0.0")

# Create tables
database.create_tables()

# Templates
templates = Jinja2Templates(directory="templates")

# Sample data insertion with error handling
def insert_sample_data():
    try:
        db = next(database.get_db())
        
        # Check if data already exists
        if db.query(database.Company).first():
            print("Sample data already exists, skipping...")
            return
        
        print("Inserting sample data...")
        
        # Kili Technology
        kili_data = models.CompanyCreate(
            name="Kili Technology",
            website="https://kili-technology.com",
            description="Plateforme de data labeling et d'annotation pour l'IA d'entreprise",
            sector=models.SectorEnum.AI,
            location="Paris, France",
            high_profile=4,
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
                    )
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
                    )
                )
            ],
            investors=["Serena Capital", "Headline", "Balderton Capital", "Olivier Pomel (Datadog)", "Nicolas Dessaigne (Algolia)"]
        )
        
        kili_company = crud.create_company(db, kili_data)
        print(f"Created Kili Technology with ID: {kili_company.id}")
        
        # DeepIP
        deepip_data = models.CompanyCreate(
            name="DeepIP",
            website="https://deepip.ai",
            description="AI Patent Assistant intégré à Microsoft Word pour automatiser la rédaction de brevets",
            sector=models.SectorEnum.LEGALTECH,
            location="NYC & Paris",
            high_profile=5,
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
                    )
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
                    )
                )
            ],
            investors=["Resonance", "Headline", "Serena Capital", "Balderton Capital"],
            relations=[
                models.CompanyRelationCreate(relation_type="spinoff", related_company_name="Kili Technology")
            ]
        )
        
        deepip_company = crud.create_company(db, deepip_data)
        print(f"Created DeepIP with ID: {deepip_company.id}")
        
    except Exception as e:
        print(f"Error inserting sample data: {e}")
        traceback.print_exc()

# API Routes with better error handling
@app.get("/api/companies", response_model=List[models.Company])
def read_companies(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    try:
        companies = crud.get_companies(db, skip=skip, limit=limit, search=search)
        return companies
    except Exception as e:
        print(f"Error reading companies: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/companies", response_model=models.Company)
def create_company(company: models.CompanyCreate, db: Session = Depends(database.get_db)):
    try:
        print(f"Creating company: {company.name}")
        result = crud.create_company(db=db, company=company)
        print(f"Successfully created company with ID: {result.id}")
        return result
    except Exception as e:
        print(f"Error creating company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companies/{company_id}", response_model=models.Company)
def read_company(company_id: int, db: Session = Depends(database.get_db)):
    try:
        db_company = crud.get_company(db, company_id=company_id)
        if db_company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return db_company
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error reading company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/companies/{company_id}", response_model=models.Company)
def update_company(
    company_id: int, 
    company: models.CompanyUpdate, 
    db: Session = Depends(database.get_db)
):
    try:
        db_company = crud.update_company(db, company_id=company_id, company_update=company)
        if db_company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return db_company
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/companies/{company_id}")
def delete_company(company_id: int, db: Session = Depends(database.get_db)):
    try:
        db_company = crud.delete_company(db, company_id=company_id)
        if db_company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return {"message": "Company deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Tag API Routes
@app.get("/api/tags", response_model=List[models.Tag])
def get_tags(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db)
):
    try:
        tags = crud.get_tags(db, category=category, skip=skip, limit=limit)
        return tags
    except Exception as e:
        print(f"Error getting tags: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tags/search")
def search_tags(
    q: str,
    category: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(database.get_db)
):
    try:
        tags = crud.search_tags(db, query=q, category=category, limit=limit)
        return [{"name": tag.name, "category": tag.category, "color": tag.color, "usage_count": tag.usage_count} for tag in tags]
    except Exception as e:
        print(f"Error searching tags: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tags", response_model=models.Tag)
def create_tag(tag: models.TagCreate, db: Session = Depends(database.get_db)):
    try:
        # Check if tag already exists
        existing_tag = crud.get_tag_by_name_and_category(db, tag.name, tag.category.value)
        if existing_tag:
            raise HTTPException(status_code=400, detail="Tag already exists")
        
        result = crud.create_tag(db=db, tag=tag)
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating tag: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Person API Routes
@app.get("/api/persons/search")
def search_persons(q: str, limit: int = 10, db: Session = Depends(database.get_db)):
    try:
        # Simple contains search on Person names
        persons = db.query(database.Person).filter(database.Person.name.contains(q)).limit(limit).all()
        return [{"id": p.id, "name": p.name} for p in persons]
    except Exception as e:
        print(f"Error searching persons: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/persons")
def list_persons(limit: int = 200, db: Session = Depends(database.get_db)):
    try:
        persons = db.query(database.Person).order_by(database.Person.name).limit(limit).all()
        return [{"id": p.id, "name": p.name} for p in persons]
    except Exception as e:
        print(f"Error listing persons: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Web Interface Routes with better error handling
@app.get("/", response_class=HTMLResponse)
def read_companies_web(request: Request, db: Session = Depends(database.get_db)):
    try:
        companies = crud.get_companies(db)
        return templates.TemplateResponse("index.html", {"request": request, "companies": companies})
    except Exception as e:
        print(f"Error in web interface: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@app.get("/companies/new", response_class=HTMLResponse)
def new_company_form(request: Request):
    try:
        return templates.TemplateResponse("form.html", {"request": request, "company": None})
    except Exception as e:
        print(f"Error showing new company form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@app.post("/companies/new")
def create_company_form(
    request: Request,
    name: str = Form(...),
    website: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    sector: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    high_profile: int = Form(3),
    remuneration: int = Form(3),
    work_intensity: str = Form("balanced"),
    company_size: str = Form("startup"),
    founded_year: Optional[int] = Form(None),
    last_funding: Optional[str] = Form(None),
    db: Session = Depends(database.get_db)
):
    """Fallback route for form submission if JavaScript fails"""
    try:
        print(f"Creating company via form submission: {name}")
        
        # Create company data
        company_data = models.CompanyCreate(
            name=name,
            website=website,
            description=description,
            sector=models.SectorEnum(sector) if sector else None,
            location=location,
            high_profile=high_profile,
            remuneration=remuneration,
            work_intensity=models.WorkIntensityEnum(work_intensity),
            company_size=models.CompanySizeEnum(company_size),
            founded_year=founded_year,
            last_funding=last_funding,
            founders=[],
            investors=[],
            secteur_tags=[],
            core_business_tags=[],
            relations=[]
        )
        
        # Create company
        company = crud.create_company(db=db, company=company_data)
        print(f"Successfully created company via form: {company.id}")
        
        # Redirect to home page
        return RedirectResponse(url="/", status_code=303)
        
    except Exception as e:
        print(f"Error creating company via form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@app.get("/companies/{company_id}/edit", response_class=HTMLResponse)
def edit_company_form(request: Request, company_id: int, db: Session = Depends(database.get_db)):
    try:
        company = crud.get_company(db, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return templates.TemplateResponse("form.html", {"request": request, "company": company})
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error showing edit form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@app.get("/companies/{company_id}", response_class=HTMLResponse)
def view_company(request: Request, company_id: int, db: Session = Depends(database.get_db)):
    try:
        company = crud.get_company(db, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return templates.TemplateResponse("detail.html", {"request": request, "company": company})
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error viewing company: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

# Add simple error template route
@app.get("/error", response_class=HTMLResponse)
def error_page(request: Request):
    return templates.TemplateResponse("error.html", {"request": request, "error": "Une erreur est survenue"})

# Initialize sample data on startup
@app.on_event("startup")
def startup_event():
    print("Starting up application...")
    insert_sample_data()
    print("Application started successfully!")

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI application...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")