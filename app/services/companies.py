from __future__ import annotations

from typing import List, Optional, Dict, Any
import re
from contextlib import contextmanager

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.db import neo4j as database
import app.schemas as models


def create_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@contextmanager
def neo4j_session():
    session = database.get_neo4j_session()
    try:
        yield session
    finally:
        session.close()


def _company_record_to_dict(c: Dict[str, Any], tags: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    company = {
        "id": c.get("id"),
        "slug": c.get("slug"),
        "name": c.get("name"),
        "website": c.get("website"),
        "description": c.get("description"),
        "sector": c.get("sector"),
        "location": c.get("location"),
        "high_profile": c.get("high_profile"),
        "remuneration": c.get("remuneration"),
        "work_intensity": c.get("work_intensity"),
        "company_size": c.get("company_size"),
        "founded_year": c.get("founded_year"),
        "last_funding": c.get("last_funding"),
    }
    if tags is not None:
        company["tags"] = [
            {"id": t.get("id"), "name": t.get("name"), "category": t.get("category"), "color": t.get("color")}
            for t in tags if t
        ]
        # Pre-split tags for templates that used methods
        company["secteur_tags"] = [t for t in company["tags"] if t.get("category") == "secteur"]
        company["core_business_tags"] = [t for t in company["tags"] if t.get("category") == "core_business"]
    return company


def get_companies(skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Dict[str, Any]]:
    cypher = [
        "MATCH (c:Company)",
    ]
    params: Dict[str, Any] = {"skip": skip, "limit": limit}
    if search:
        cypher.append("WHERE toLower(c.name) CONTAINS toLower($search) OR toString(c.sector) CONTAINS $search OR toString(c.location) CONTAINS $search")
        params["search"] = search
    cypher.append("OPTIONAL MATCH (c)-[:HAS_TAG]->(t:Tag)")
    cypher.append("WITH c, collect({id: t.id, name: t.name, category: t.category, color: t.color}) AS tags")
    cypher.append("RETURN c{.*} AS c, tags ORDER BY c.name SKIP $skip LIMIT $limit")
    query = "\n".join(cypher)
    with neo4j_session() as s:
        rows = s.run(query, **params)
        results: List[Dict[str, Any]] = []
        for r in rows:
            c = r["c"]
            tags = r["tags"] or []
            results.append(_company_record_to_dict(c, tags))
        return results


def filter_companies(
    tags: Optional[List[str]] = None,
    work_intensity_value: Optional[str] = None,
    work_intensity_cmp: Optional[str] = None,
    company_size_value: Optional[str] = None,
    company_size_cmp: Optional[str] = None,
    high_profile_value: Optional[int] = None,
    high_profile_cmp: Optional[str] = None,
    remuneration_value: Optional[int] = None,
    remuneration_cmp: Optional[str] = None,
) -> List[Dict[str, Any]]:
    where_clauses: List[str] = []
    params: Dict[str, Any] = {}

    cypher = ["MATCH (c:Company)"]
    if tags:
        # All tags required on the company
        cypher.append("WITH c MATCH (c)-[:HAS_TAG]->(t:Tag) WHERE t.name IN $tags WITH c, collect(DISTINCT t.name) AS tn")
        cypher.append("WHERE ALL(x IN $tags WHERE x IN tn)")
        params["tags"] = tags

    # Work intensity filter
    if work_intensity_value:
        order = ["chill", "balanced", "intense", "bourrin"]
        params["wi"] = work_intensity_value
        if work_intensity_cmp == "lte":
            cypher.append("WITH c WHERE index($order, c.work_intensity) <= index($order, $wi)")
        elif work_intensity_cmp == "gte":
            cypher.append("WITH c WHERE index($order, c.work_intensity) >= index($order, $wi)")
        else:
            cypher.append("WITH c WHERE c.work_intensity = $wi")
        params["order"] = order

    # Company size filter
    if company_size_value:
        order2 = ["early", "startup", "scaleup", "corp"]
        params["cs"] = company_size_value
        if company_size_cmp == "lte":
            cypher.append("WITH c WHERE index($order2, c.company_size) <= index($order2, $cs)")
        elif company_size_cmp == "gte":
            cypher.append("WITH c WHERE index($order2, c.company_size) >= index($order2, $cs)")
        else:
            cypher.append("WITH c WHERE c.company_size = $cs")
        params["order2"] = order2

    # Numeric filters
    if high_profile_value is not None:
        params["hp"] = high_profile_value
        if high_profile_cmp == "lte":
            cypher.append("WITH c WHERE c.high_profile <= $hp")
        elif high_profile_cmp == "eq":
            cypher.append("WITH c WHERE c.high_profile = $hp")
        else:
            cypher.append("WITH c WHERE c.high_profile >= $hp")

    if remuneration_value is not None:
        params["rm"] = remuneration_value
        if remuneration_cmp == "lte":
            cypher.append("WITH c WHERE c.remuneration <= $rm")
        elif remuneration_cmp == "eq":
            cypher.append("WITH c WHERE c.remuneration = $rm")
        else:
            cypher.append("WITH c WHERE c.remuneration >= $rm")

    cypher.append("OPTIONAL MATCH (c)-[:HAS_TAG]->(t:Tag)")
    cypher.append("WITH c, collect({id: t.id, name: t.name, category: t.category, color: t.color}) AS tags")
    cypher.append("RETURN c{.*} AS c, tags ORDER BY c.name")
    query = "\n".join(cypher)
    with neo4j_session() as s:
        rows = s.run(query, **params)
        return [_company_record_to_dict(r["c"], r["tags"] or []) for r in rows]


def get_company(company_id: int) -> Optional[Dict[str, Any]]:
    with neo4j_session() as s:
        rec = s.run(
            """
            MATCH (c:Company {id: $id})
            OPTIONAL MATCH (c)-[:HAS_TAG]->(ct:Tag)
            WITH c, collect(ct{.*}) AS ctags

            // Founders with tags aggregated per founder
            OPTIONAL MATCH (p:Person)-[rf:FOUNDER_OF]->(c)
            WITH c, ctags, p, rf
            OPTIONAL MATCH (p)-[:HAS_TAG]->(ft:Tag)
            WITH c, ctags, p, rf, collect(ft{.*}) AS ftags
            WITH c, ctags, collect({
                person_id: p.id, name: p.name, title: rf.title,
                background_type: rf.background_type,
                education_institution: rf.education_institution,
                education_degree: rf.education_degree,
                education_field: rf.education_field,
                education_year: rf.education_year,
                professional_company: rf.professional_company,
                professional_position: rf.professional_position,
                professional_duration: rf.professional_duration,
                professional_description: rf.professional_description,
                tags: ftags
            }) AS founders

            // Employees with tags aggregated per employee
            OPTIONAL MATCH (pe:Person)-[re:EMPLOYEE_OF]->(c)
            WITH c, ctags, founders, pe, re
            OPTIONAL MATCH (pe)-[:HAS_TAG]->(et:Tag)
            WITH c, ctags, founders, pe, re, collect(et{.*}) AS etags
            WITH c, ctags, founders, collect({
                person_id: pe.id, name: pe.name, title: re.title, role: re.role,
                department: re.department, career_track: re.career_track,
                background_type: re.background_type,
                education_institution: re.education_institution,
                education_degree: re.education_degree,
                education_field: re.education_field,
                education_year: re.education_year,
                professional_company: re.professional_company,
                professional_position: re.professional_position,
                professional_duration: re.professional_duration,
                professional_description: re.professional_description,
                tags: etags
            }) AS employees

            OPTIONAL MATCH (i:Investor)-[:INVESTED_IN]->(c)
            RETURN c{.*} AS c, ctags, founders, employees, collect(i{.*}) AS investors
            """,
            id=company_id,
        ).single()
        if not rec:
            return None
        c = _company_record_to_dict(rec["c"], rec["ctags"] or [])
        # Format founders and employees with split tags for templates
        def split_tags(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for it in items or []:
                tags = it.get("tags", [])
                it["education_tags"] = [t for t in tags if t.get("category") == "education"]
                it["professional_tags"] = [t for t in tags if t.get("category") == "professional"]
                out.append(it)
            return out
        c["founders"] = split_tags(rec["founders"] or [])
        c["employees"] = split_tags(rec["employees"] or [])
        c["investors"] = rec["investors"] or []
        return c


def _next_company_id(s) -> int:
    row = s.run("MATCH (c:Company) RETURN coalesce(max(c.id), 0) AS maxid").single()
    return int((row and row["maxid"]) or 0) + 1


def _next_person_id(s) -> int:
    row = s.run("MATCH (p:Person) RETURN coalesce(max(p.id), 0) AS maxid").single()
    return int((row and row["maxid"]) or 0) + 1


def _get_or_create_person(s, person_id: Optional[int], name: Optional[str]) -> int:
    if person_id:
        row = s.run("MATCH (p:Person {id:$id}) RETURN p.id AS id", id=person_id).single()
        if row and row["id"]:
            # Optionally sync name if provided
            if name:
                s.run("MATCH (p:Person {id:$id}) SET p.name=$name", id=person_id, name=name)
            return int(row["id"])
    # Try find by name
    if name:
        row = s.run("MATCH (p:Person {name:$name}) RETURN p.id AS id", name=name).single()
        if row and row["id"]:
            return int(row["id"])
        # Create new person id
        new_pid = _next_person_id(s)
        s.run("MERGE (p:Person {id:$id}) SET p.name=$name", id=new_pid, name=name)
        return new_pid
    # Fallback: create anonymous person
    new_pid = _next_person_id(s)
    s.run("MERGE (p:Person {id:$id})", id=new_pid)
    return new_pid


def create_company(company: models.CompanyCreate) -> Dict[str, Any]:
    data = company.dict()
    slug = create_slug(data["name"])
    with neo4j_session() as s:
        new_id = _next_company_id(s)
        s.run(
            """
            MERGE (c:Company {id: $id})
            SET c.slug=$slug, c.name=$name, c.website=$website, c.description=$description,
                c.sector=$sector, c.location=$location, c.high_profile=$high_profile,
                c.remuneration=$remuneration, c.work_intensity=$work_intensity,
                c.company_size=$company_size, c.founded_year=$founded_year, c.last_funding=$last_funding
            """,
            id=new_id,
            slug=slug,
            name=data.get("name"),
            website=data.get("website"),
            description=data.get("description"),
            sector=(data.get("sector") or None),
            location=data.get("location"),
            high_profile=data.get("high_profile"),
            remuneration=data.get("remuneration"),
            work_intensity=(data.get("work_intensity") and data.get("work_intensity").value) if hasattr(data.get("work_intensity"), "value") else data.get("work_intensity"),
            company_size=(data.get("company_size") and data.get("company_size").value) if hasattr(data.get("company_size"), "value") else data.get("company_size"),
            founded_year=data.get("founded_year"),
            last_funding=data.get("last_funding"),
        )

        # Tags on company
        for tag_name in (data.get("secteur_tags") or []):
            if not (tag_name and tag_name.strip()):
                continue
            s.run(
                """
                MERGE (t:Tag {name: $name, category: 'secteur'})
                ON CREATE SET t.color=$color
                WITH t
                MATCH (c:Company {id: $cid})
                MERGE (c)-[:HAS_TAG]->(t)
                """,
                name=tag_name.strip(), color="#64b5f6", cid=new_id,
            )
        for tag_name in (data.get("core_business_tags") or []):
            if not (tag_name and tag_name.strip()):
                continue
            s.run(
                """
                MERGE (t:Tag {name: $name, category: 'core_business'})
                ON CREATE SET t.color=$color
                WITH t
                MATCH (c:Company {id: $cid})
                MERGE (c)-[:HAS_TAG]->(t)
                """,
                name=tag_name.strip(), color="#64b5f6", cid=new_id,
            )

        # Investors
        for inv_name in (data.get("investors") or []):
            if not (inv_name and inv_name.strip()):
                continue
            inv_row = s.run("MATCH (i:Investor) WHERE i.name=$n RETURN i.id AS id", n=inv_name.strip()).single()
            if inv_row and inv_row["id"] is not None:
                inv_id = inv_row["id"]
            else:
                # Allocate investor id
                inv_id = int((s.run("MATCH (i:Investor) RETURN coalesce(max(i.id),0) AS mid").single()["mid"]) or 0) + 1
                s.run("MERGE (i:Investor {id:$id}) SET i.name=$n", id=inv_id, n=inv_name.strip())
            s.run("MATCH (i:Investor {id:$iid}), (c:Company {id:$cid}) MERGE (i)-[:INVESTED_IN]->(c)", iid=inv_id, cid=new_id)

        # Employees
        for emp in (data.get("employees") or []):
            name = emp.get("name")
            if not name:
                continue
            pid = _get_or_create_person(s, emp.get("person_id"), name)
            # Create relationship with properties
            s.run(
                """
                MATCH (p:Person {id:$pid}), (c:Company {id:$cid})
                MERGE (p)-[r:EMPLOYEE_OF]->(c)
                SET r.title=$title,
                    r.role=$role,
                    r.department=$department,
                    r.career_track=$career_track,
                    r.background_type=$background_type,
                    r.education_institution=$education_institution,
                    r.education_degree=$education_degree,
                    r.education_field=$education_field,
                    r.education_year=$education_year,
                    r.professional_company=$professional_company,
                    r.professional_position=$professional_position,
                    r.professional_duration=$professional_duration,
                    r.professional_description=$professional_description
                """,
                pid=pid,
                cid=new_id,
                title=emp.get("title"),
                role=emp.get("role"),
                department=emp.get("department"),
                career_track=emp.get("career_track"),
                background_type=emp.get("background_type"),
                education_institution=((emp.get("education_background") or {}).get("institution")),
                education_degree=((emp.get("education_background") or {}).get("degree")),
                education_field=((emp.get("education_background") or {}).get("field")),
                education_year=((emp.get("education_background") or {}).get("year")),
                professional_company=((emp.get("professional_background") or {}).get("company")),
                professional_position=((emp.get("professional_background") or {}).get("position")),
                professional_duration=((emp.get("professional_background") or {}).get("duration")),
                professional_description=((emp.get("professional_background") or {}).get("description")),
            )
            # Employee tags
            for tname in (emp.get("education_tags") or []):
                tname = (tname or "").strip()
                if not tname:
                    continue
                s.run(
                    """
                    MERGE (t:Tag {name:$name, category:'education'})
                    ON CREATE SET t.color=$color
                    WITH t
                    MATCH (p:Person {id:$pid})
                    MERGE (p)-[:HAS_TAG]->(t)
                    """,
                    name=tname,
                    color="#64b5f6",
                    pid=pid,
                )
            for tname in (emp.get("professional_tags") or []):
                tname = (tname or "").strip()
                if not tname:
                    continue
                s.run(
                    """
                    MERGE (t:Tag {name:$name, category:'professional'})
                    ON CREATE SET t.color=$color
                    WITH t
                    MATCH (p:Person {id:$pid})
                    MERGE (p)-[:HAS_TAG]->(t)
                    """,
                    name=tname,
                    color="#64b5f6",
                    pid=pid,
                )

    created = get_company(new_id)
    if not created:
        raise RuntimeError("Failed to create company")
    return created


def delete_company(company_id: int) -> bool:
    with neo4j_session() as s:
        s.run("MATCH (c:Company {id:$id}) DETACH DELETE c", id=company_id)
    return True


def update_company(company_id: int, company_update: models.CompanyUpdate) -> Dict[str, Any]:
    """Update scalar fields and optionally tags/investors for a company."""
    data = company_update.dict(exclude_unset=True)
    # Build props map for SET +=
    props: Dict[str, Any] = {}
    allowed_scalar_keys = [
        "name",
        "website",
        "description",
        "sector",
        "location",
        "high_profile",
        "remuneration",
        "work_intensity",
        "company_size",
        "founded_year",
        "last_funding",
    ]
    for k in allowed_scalar_keys:
        if k in data and data[k] is not None:
            # Unwrap enum if present
            v = data[k]
            if hasattr(v, "value"):
                v = v.value
            props[k] = v
    # If name present, recompute slug
    if "name" in props and props["name"]:
        props["slug"] = create_slug(props["name"])

    with neo4j_session() as s:
        if props:
            s.run(
                "MATCH (c:Company {id:$id}) SET c += $props",
                id=company_id,
                props=props,
            )

        # Update tags by category if provided
        for key, category in (("secteur_tags", "secteur"), ("core_business_tags", "core_business")):
            if key in data and data[key] is not None:
                tags: List[str] = [t for t in (data[key] or []) if t and str(t).strip()]
                # Remove existing links of this category
                s.run(
                    "MATCH (c:Company {id:$id})-[r:HAS_TAG]->(t:Tag {category:$cat}) DELETE r",
                    id=company_id,
                    cat=category,
                )
                # Recreate
                for tag_name in tags:
                    s.run(
                        """
                        MERGE (t:Tag {name:$name, category:$cat})
                        ON CREATE SET t.color=$color
                        WITH t
                        MATCH (c:Company {id:$id})
                        MERGE (c)-[:HAS_TAG]->(t)
                        """,
                        name=str(tag_name).strip(),
                        cat=category,
                        color="#64b5f6",
                        id=company_id,
                    )

        # Update investors if provided
        if "investors" in data and data["investors"] is not None:
            invs: List[str] = [i for i in (data["investors"] or []) if i and str(i).strip()]
            s.run("MATCH (i:Investor)-[r:INVESTED_IN]->(c:Company {id:$id}) DELETE r", id=company_id)
            for inv_name in invs:
                inv_row = s.run("MATCH (i:Investor) WHERE i.name=$n RETURN i.id AS id", n=str(inv_name).strip()).single()
                if inv_row and inv_row["id"] is not None:
                    inv_id = inv_row["id"]
                else:
                    inv_id = int((s.run("MATCH (i:Investor) RETURN coalesce(max(i.id),0) AS mid").single()["mid"]) or 0) + 1
                    s.run("MERGE (i:Investor {id:$id}) SET i.name=$n", id=inv_id, n=str(inv_name).strip())
                s.run(
                    "MATCH (i:Investor {id:$iid}), (c:Company {id:$cid}) MERGE (i)-[:INVESTED_IN]->(c)",
                    iid=inv_id,
                    cid=company_id,
                )

        # Replace employees if provided
        if "employees" in data and data["employees"] is not None:
            # Remove only the EMPLOYEE_OF relationships for this company
            s.run("MATCH (:Person)-[r:EMPLOYEE_OF]->(c:Company {id:$id}) DELETE r", id=company_id)
            # Recreate
            for emp in (data.get("employees") or []):
                name = emp.get("name")
                if not name:
                    continue
                pid = _get_or_create_person(s, emp.get("person_id"), name)
                s.run(
                    """
                    MATCH (p:Person {id:$pid}), (c:Company {id:$cid})
                    MERGE (p)-[r:EMPLOYEE_OF]->(c)
                    SET r.title=$title,
                        r.role=$role,
                        r.department=$department,
                        r.career_track=$career_track,
                        r.background_type=$background_type,
                        r.education_institution=$education_institution,
                        r.education_degree=$education_degree,
                        r.education_field=$education_field,
                        r.education_year=$education_year,
                        r.professional_company=$professional_company,
                        r.professional_position=$professional_position,
                        r.professional_duration=$professional_duration,
                        r.professional_description=$professional_description
                    """,
                    pid=pid,
                    cid=company_id,
                    title=emp.get("title"),
                    role=emp.get("role"),
                    department=emp.get("department"),
                    career_track=emp.get("career_track"),
                    background_type=emp.get("background_type"),
                    education_institution=((emp.get("education_background") or {}).get("institution")),
                    education_degree=((emp.get("education_background") or {}).get("degree")),
                    education_field=((emp.get("education_background") or {}).get("field")),
                    education_year=((emp.get("education_background") or {}).get("year")),
                    professional_company=((emp.get("professional_background") or {}).get("company")),
                    professional_position=((emp.get("professional_background") or {}).get("position")),
                    professional_duration=((emp.get("professional_background") or {}).get("duration")),
                    professional_description=((emp.get("professional_background") or {}).get("description")),
                )
                for tname in (emp.get("education_tags") or []):
                    tname = (tname or "").strip()
                    if not tname:
                        continue
                    s.run(
                        """
                        MERGE (t:Tag {name:$name, category:'education'})
                        ON CREATE SET t.color=$color
                        WITH t
                        MATCH (p:Person {id:$pid})
                        MERGE (p)-[:HAS_TAG]->(t)
                        """,
                        name=tname,
                        color="#64b5f6",
                        pid=pid,
                    )
                for tname in (emp.get("professional_tags") or []):
                    tname = (tname or "").strip()
                    if not tname:
                        continue
                    s.run(
                        """
                        MERGE (t:Tag {name:$name, category:'professional'})
                        ON CREATE SET t.color=$color
                        WITH t
                        MATCH (p:Person {id:$pid})
                        MERGE (p)-[:HAS_TAG]->(t)
                        """,
                        name=tname,
                        color="#64b5f6",
                        pid=pid,
                    )

    updated = get_company(company_id)
    if not updated:
        raise RuntimeError("Company not found after update")
    return updated

def get_tags(category: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    cypher = "MATCH (t:Tag)"
    params: Dict[str, Any] = {"skip": skip, "limit": limit}
    if category:
        cypher += " WHERE t.category=$category"
        params["category"] = category
    cypher += " RETURN t{.*} AS t ORDER BY t.name SKIP $skip LIMIT $limit"
    with neo4j_session() as s:
        return [r["t"] for r in s.run(cypher, **params)]


def search_tags(query: str, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    cypher = "MATCH (t:Tag) WHERE toLower(t.name) CONTAINS toLower($q)"
    params: Dict[str, Any] = {"q": query, "limit": limit}
    if category:
        cypher += " AND t.category=$category"
        params["category"] = category
    cypher += " RETURN t{.*} AS t ORDER BY t.name LIMIT $limit"
    with neo4j_session() as s:
        return [r["t"] for r in s.run(cypher, **params)]


def create_tag(tag: models.TagCreate) -> Dict[str, Any]:
    with neo4j_session() as s:
        s.run(
            "MERGE (t:Tag {name:$name, category:$cat}) ON CREATE SET t.color=$color",
            name=tag.name, cat=tag.category.value, color=tag.color or "#64b5f6",
        )
        rec = s.run("MATCH (t:Tag {name:$name, category:$cat}) RETURN t{.*} AS t", name=tag.name, cat=tag.category.value).single()
        return rec["t"] if rec else {"name": tag.name, "category": tag.category.value, "color": tag.color}


def search_persons(q: str, limit: int = 10) -> List[Dict[str, Any]]:
    with neo4j_session() as s:
        rows = s.run(
            "MATCH (p:Person) WHERE toLower(p.name) CONTAINS toLower($q) RETURN p.id AS id, p.name AS name LIMIT $limit",
            q=q, limit=limit,
        )
        return [{"id": r["id"], "name": r["name"]} for r in rows]


def list_persons(limit: int = 200) -> List[Dict[str, Any]]:
    with neo4j_session() as s:
        rows = s.run("MATCH (p:Person) RETURN p.id AS id, p.name AS name ORDER BY name LIMIT $limit", limit=limit)
        return [{"id": r["id"], "name": r["name"]} for r in rows]


def companies_graph() -> Dict[str, Any]:
    with neo4j_session() as s:
        nodes = []
        for r in s.run("MATCH (c:Company) RETURN 'company-' + toString(c.id) AS id, c.name AS label"):
            nodes.append({"id": r["id"], "label": r["label"], "type": "company"})
        for r in s.run("MATCH (p:Person) RETURN 'person-' + toString(p.id) AS id, p.name AS label"):
            nodes.append({"id": r["id"], "label": r["label"], "type": "person"})
        links = []
        for r in s.run(
            """
            MATCH (p:Person)-[r:FOUNDER_OF|EMPLOYEE_OF]->(c:Company)
            RETURN 'person-' + toString(p.id) AS source, 'company-' + toString(c.id) AS target,
                   CASE WHEN type(r)='FOUNDER_OF' THEN 'founder' ELSE 'employee' END AS relation
            """
        ):
            links.append({"source": r["source"], "target": r["target"], "relation": r["relation"]})
        # Shared tag edges between persons
        for r in s.run(
            """
            MATCH (p1:Person)-[:HAS_TAG]->(t:Tag)<-[:HAS_TAG]-(p2:Person)
            WHERE id(p1) < id(p2)
            RETURN 'person-' + toString(p1.id) AS source, 'person-' + toString(p2.id) AS target,
                   'shared_tag' AS relation
            """
        ):
            links.append({"source": r["source"], "target": r["target"], "relation": r["relation"]})
        return {"nodes": nodes, "links": links}

