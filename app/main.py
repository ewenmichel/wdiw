# main.py - Debug version with better error handling
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import json
import traceback

# Fixed imports for new structure
import pathlib
import os
import sys

# Ensure project root (directory containing `app/`) is on sys.path
_HERE = pathlib.Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import app.schemas as models
from app.db import neo4j as database
from app.services import companies as crud

app = FastAPI(title="Tech Companies Database", version="1.0.0")

# Initialize Neo4j constraints
database.init_neo4j_constraints()

# Templates (absolute path so it works from any CWD)
ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES_DIR = str(ROOT_DIR / "templates")
STATIC_DIR = str(ROOT_DIR / "static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Serve static files (crystals, fonts, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Sample data insertion with error handling
def insert_sample_data():
    try:
        # Check if data already exists (via Neo4j API)
        if crud.get_companies(limit=1):
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
        
        kili_company = crud.create_company(kili_data)
        print(f"Created Kili Technology with ID: {kili_company['id']}")
        
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
        
        deepip_company = crud.create_company(deepip_data)
        print(f"Created DeepIP with ID: {deepip_company['id']}")
        
    except Exception as e:
        print(f"Error inserting sample data: {e}")
        traceback.print_exc()

# API Routes with better error handling
@app.get("/api/companies")
def read_companies(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
):
    try:
        companies = crud.get_companies(skip=skip, limit=limit, search=search)
        return companies
    except Exception as e:
        print(f"Error reading companies: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companies/filter")
def filter_companies_api(
    tags: Optional[str] = None,  # comma-separated tag names
    work_intensity_value: Optional[str] = None,
    work_intensity_cmp: Optional[str] = None,  # lte/gte/eq
    company_size_value: Optional[str] = None,
    company_size_cmp: Optional[str] = None,  # lte/gte/eq
    high_profile_value: Optional[int] = None,
    high_profile_cmp: Optional[str] = None,  # lte/gte/eq
    remuneration_value: Optional[int] = None,
    remuneration_cmp: Optional[str] = None,  # lte/gte/eq
):
    try:
        tag_list = [t.strip() for t in tags.split(',')] if tags else None
        companies = crud.filter_companies(
            tags=tag_list,
            work_intensity_value=work_intensity_value,
            work_intensity_cmp=work_intensity_cmp,
            company_size_value=company_size_value,
            company_size_cmp=company_size_cmp,
            high_profile_value=high_profile_value,
            high_profile_cmp=high_profile_cmp,
            remuneration_value=remuneration_value,
            remuneration_cmp=remuneration_cmp
        )
        return companies
    except Exception as e:
        print(f"Error filtering companies: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph/companies")
def companies_graph():
    try:
        return crud.companies_graph()
    except Exception as e:
        print(f"Error creating graph: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/companies")
def create_company(company: models.CompanyCreate):
    try:
        print(f"Creating company: {company.name}")
        result = crud.create_company(company=company)
        print(f"Successfully created company with ID: {result['id']}")
        return result
    except Exception as e:
        print(f"Error creating company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companies/{company_id}")
def read_company(company_id: int):
    try:
        db_company = crud.get_company(company_id=company_id)
        if not db_company:
            raise HTTPException(status_code=404, detail="Company not found")
        return db_company
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error reading company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/companies/{company_id}")
def update_company(
    company_id: int,
    company: models.CompanyUpdate,
):
    try:
        result = crud.update_company(company_id=company_id, company_update=company)
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/companies/{company_id}")
def delete_company(company_id: int):
    try:
        crud.delete_company(company_id=company_id)
        return {"message": "Company deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting company: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Tag API Routes
@app.get("/api/tags")
def get_tags(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    try:
        tags = crud.get_tags(category=category, skip=skip, limit=limit)
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
):
    try:
        tags = crud.search_tags(query=q, category=category, limit=limit)
        return [{"name": tag["name"], "category": tag["category"], "color": tag.get("color", "#64b5f6"), "usage_count": tag.get("usage_count", 0)} for tag in tags]
    except Exception as e:
        print(f"Error searching tags: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tags")
def create_tag(tag: models.TagCreate):
    try:
        result = crud.create_tag(tag=tag)
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating tag: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Person API Routes
@app.get("/api/persons/search")
def search_persons(q: str, limit: int = 10):
    try:
        persons = crud.search_persons(q=q, limit=limit)
        return persons
    except Exception as e:
        print(f"Error searching persons: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/persons")
def list_persons(limit: int = 200):
    try:
        persons = crud.list_persons(limit=limit)
        return persons
    except Exception as e:
        print(f"Error listing persons: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Web Interface Routes with better error handling
@app.get("/", response_class=HTMLResponse)
def read_companies_web(request: Request):
    try:
        qp = request.query_params
        tags = qp.get("tags")
        work_intensity_value = qp.get("work_intensity_value")
        work_intensity_cmp = qp.get("work_intensity_cmp")
        company_size_value = qp.get("company_size_value")
        company_size_cmp = qp.get("company_size_cmp")
        high_profile_value = qp.get("high_profile_value")
        high_profile_cmp = qp.get("high_profile_cmp")
        remuneration_value = qp.get("remuneration_value")
        remuneration_cmp = qp.get("remuneration_cmp")

        if any([tags, work_intensity_value, company_size_value, high_profile_value, remuneration_value]):
            tag_list = [t.strip() for t in tags.split(',')] if tags else None
            companies = crud.filter_companies(
                tags=tag_list,
                work_intensity_value=work_intensity_value,
                work_intensity_cmp=work_intensity_cmp,
                company_size_value=company_size_value,
                company_size_cmp=company_size_cmp,
                high_profile_value=int(high_profile_value) if high_profile_value else None,
                high_profile_cmp=high_profile_cmp,
                remuneration_value=int(remuneration_value) if remuneration_value else None,
                remuneration_cmp=remuneration_cmp
            )
        else:
            companies = crud.get_companies()
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
        company = crud.create_company(company=company_data)
        print(f"Successfully created company via form: {company['id']}")
        
        # Redirect to home page
        return RedirectResponse(url="/", status_code=303)
        
    except Exception as e:
        print(f"Error creating company via form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@app.get("/companies/{company_id}/edit", response_class=HTMLResponse)
def edit_company_form(request: Request, company_id: int):
    try:
        company = crud.get_company(company_id)
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
def view_company(request: Request, company_id: int):
    try:
        company = crud.get_company(company_id)
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

@app.get("/graph", response_class=HTMLResponse)
def graph_page(request: Request):
    return templates.TemplateResponse("graph.html", {"request": request})

# Manifesto page
@app.get("/manifesto", response_class=HTMLResponse)
def manifesto_page(request: Request):
    return templates.TemplateResponse("manifesto.html", {"request": request})

@app.get("/manifesto.html", response_class=HTMLResponse)
def manifesto_page_alias(request: Request):
    return templates.TemplateResponse("manifesto.html", {"request": request})

# Initialize constraints on startup
@app.on_event("startup")
def startup_event():
    print("Starting up application...")
    try:
        database.init_neo4j_constraints()
    except Exception as e:
        print(f"[neo4j] constraint init error: {e}")
    print("Application started successfully!")

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI application...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")