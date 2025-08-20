import os
import sys
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import re


# Ensure project root is on sys.path when running this file directly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from dotenv import load_dotenv  # type: ignore
import httpx  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import anthropic  # type: ignore

from wdiw.database import get_neo4j_session  # type: ignore


READINESS_VALUE = "AI-GENERATED"


def load_env() -> Tuple[str, str]:
    load_dotenv()
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("BRAVE_API_KEY") or ""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY") or ""
    if not brave_key:
        raise RuntimeError("Missing BRAVE_SEARCH_API_KEY in environment/.env")
    if not anthropic_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY in environment/.env")
    return brave_key, anthropic_key


def create_slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def brave_search(api_key: str, query: str, count: int = 6) -> List[Dict[str, Any]]:
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
        "User-Agent": "crystaldoor-agent/1.0",
    }
    params = {"q": query, "count": count, "safesearch": "off"}
    with httpx.Client(timeout=20.0, headers=headers) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    results = []
    for it in (data.get("web", {}) or {}).get("results", [])[:count]:
        results.append({
            "url": it.get("url"),
            "title": it.get("title"),
            "description": it.get("description"),
        })
    return results


def fetch_text(url: str) -> str:
    try:
        with httpx.Client(timeout=20.0, headers={"User-Agent": "crystaldoor-agent/1.0"}) as client:
            resp = client.get(url, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = soup.get_text(" ", strip=True)
        # Keep it within a reasonable token budget
        return text[:120000]
    except Exception:
        return ""


def fetch_page_html(url: str) -> str:
    try:
        with httpx.Client(timeout=20.0, headers={"User-Agent": "crystaldoor-agent/1.0"}) as client:
            resp = client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
    except Exception:
        return ""


def extract_page_signals(html: str, url: str) -> Dict[str, Any]:
    if not html:
        return {"url": url, "title": "", "description": "", "headings": [], "json_ld": [], "text": ""}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        # keep application/ld+json separately
        if tag.name == "script" and tag.get("type") == "application/ld+json":
            continue
        tag.extract()
    title = (soup.find("title").get_text().strip() if soup.find("title") else "")
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    description = (meta_desc_tag.get("content", "") if meta_desc_tag else "")
    headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"])][:8]
    # Collect JSON-LD blocks
    json_ld_blocks: List[str] = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            json_ld_blocks.append(s.get_text().strip())
        except Exception:
            pass
    text = soup.get_text(" ", strip=True)
    return {
        "url": url,
        "title": title,
        "description": description,
        "headings": headings,
        "json_ld": json_ld_blocks[:3],
        "text": text[:60000],
    }


KEYWORDS = [
    "founder", "co-founder", "cofounder", "ceo", "cto", "cfo", "leadership", "team",
    "about", "mission", "founded", "established", "since", "year", "employees", "company size",
]


def score_url_for_company(url: str, title: str, company: str) -> int:
    score = 0
    domain = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    c = company.lower()
    # Prefer official domain
    if c.split()[0] in domain:
        score += 5
    # Prefer about/team pages
    if any(x in path for x in ["/about", "/team", "/leadership", "/company"]):
        score += 4
    # Prefer known sources
    if any(k in domain for k in ["wikipedia.org", "crunchbase.com", "linkedin.com"]):
        score += 3
    # Penalize PDFs and binaries
    if path.endswith(('.pdf', '.zip', '.png', '.jpg', '.jpeg')):
        score -= 3
    # Title match
    if company.lower() in (title or '').lower():
        score += 2
    return score


def shortlist_urls(company: str, results: List[Dict[str, Any]], max_urls: int = 4) -> List[str]:
    ranked = []
    seen = set()
    for it in results:
        u = (it.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        ranked.append((score_url_for_company(u, it.get("title", ""), company), u))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in ranked[:max_urls]]


def compress_pages(pages: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for p in pages:
        url = p.get("url", "")
        title = p.get("title", "")
        desc = p.get("description", "")
        heads = "; ".join(p.get("headings", [])[:5])
        json_ld = "\n".join(p.get("json_ld", [])[:2])
        text = p.get("text", "")
        # Extract keyword sentences
        snippets: List[str] = []
        for kw in KEYWORDS:
            m = re.search(rf"(.{{0,120}}\b{re.escape(kw)}\b.*?\.)(?!.*\1)", text, flags=re.IGNORECASE)
            if m:
                snippets.append(m.group(1).strip())
        snippets = list(dict.fromkeys(snippets))[:5]
        block = [
            f"URL: {url}",
            f"TITLE: {title}",
            f"META: {desc}",
            f"HEADINGS: {heads}",
            ("JSON_LD:\n" + json_ld) if json_ld else "",
            "SNIPPETS:",
            *[f"- {s}" for s in snippets],
        ]
        parts.append("\n".join([b for b in block if b]))
    corpus = "\n\n".join(parts)
    return corpus[:12000]


def call_anthropic_structured(anthropic_key: str, company: str, corpus: str, max_tokens: int = 600) -> Dict[str, Any]:
    client = anthropic.Anthropic(api_key=anthropic_key)
    schema = {
        "company": {
            "name": "string",
            "website": "string|null",
            "description": "string|null",
            "location": "string|null",
            "company_size": "string|null",
            "founded_year": "number|null",
            "last_funding": "string|null",
            "readiness": "string",
        },
        "founders": [
            {
                "name": "string",
                "title": "string|null",
                "role": "string|null",
                "career_track": "string|null",
                "education_institution": "string|null",
                "professional_company": "string|null",
                "previous_companies": ["string"],
                "readiness": "string",
            }
        ],
    }
    system_prompt = (
        "You extract factual company and founder data into strict JSON. "
        "Only use information from the provided corpus; do not guess. "
        "If a field is not found, return null or [] for lists."
    )
    # Build prompt in two steps so .format() does not see raw corpus braces
    prompt_template = (
        "Extract the following fields for the company '{company}'.\n"
        "Return strictly JSON with keys: company, founders.\n\n"
        "Schema: {schema}\n\n"
        "Corpus (web content snippets):\n"
    )
    user_prompt = prompt_template.format(company=company, schema=json.dumps(schema)) + corpus

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
    )
    # Extract text content
    text_parts = []
    for part in msg.content:
        if getattr(part, "type", None) == "text":
            text_parts.append(part.text)
    text = "\n".join(text_parts).strip()
    # Strip markdown json fences if present
    if text.startswith("```") and text.endswith("```"):
        inner = text[3:-3].strip()
        if inner.lower().startswith("json"):
            inner = inner[4:].lstrip()
        text = inner
    try:
        data = json.loads(text)
    except Exception:
        # Last resort: find first/last braces
        start = text.find("{")
        end = text.rfind("}")
        data = json.loads(text[start:end+1]) if start != -1 and end != -1 else {"company": {}, "founders": []}

    # Inject readiness flags
    data = data or {"company": {}, "founders": []}
    if "company" not in data or not isinstance(data["company"], dict):
        data["company"] = {}
    data["company"]["readiness"] = READINESS_VALUE
    founders = data.get("founders") or []
    fixed_founders: List[Dict[str, Any]] = []
    for f in founders:
        if not isinstance(f, dict):
            continue
        f["readiness"] = READINESS_VALUE
        # Normalize previous_companies list
        prev = f.get("previous_companies") or []
        if isinstance(prev, str):
            prev = [prev]
        f["previous_companies"] = [str(x) for x in prev if x]
        fixed_founders.append(f)
    data["founders"] = fixed_founders
    return data


def collect_from_web(brave_key: str, anthropic_key: str, company: str) -> Dict[str, Any]:
    # Search queries to gather diverse sources
    queries = [
        f"{company} official site about",
        f"{company} founders",
        f"{company} wikipedia",
        f"{company} crunchbase",
        f"{company} linkedin company",
    ]
    raw_results: List[Dict[str, Any]] = []
    for q in queries:
        try:
            raw_results.extend(brave_search(brave_key, q, count=5))
        except Exception:
            continue
    # Deduplicate by URL
    seen_urls: set = set()
    deduped: List[Dict[str, Any]] = []
    for r in raw_results:
        u = (r.get("url") or "").strip()
        if u and u not in seen_urls:
            seen_urls.add(u)
            deduped.append(r)
    top_urls = shortlist_urls(company, deduped, max_urls=4)

    pages: List[Dict[str, Any]] = []
    for u in top_urls:
        html = fetch_page_html(u)
        if html:
            pages.append(extract_page_signals(html, u))
        time.sleep(0.05)
    corpus = compress_pages(pages)

    try:
        return call_anthropic_structured(anthropic_key, company, corpus, max_tokens=500)
    except Exception as e:
        # Rate limit fallback: shrink corpus to top 2 pages and fewer tokens
        small_corpus = compress_pages(pages[:2]) if pages else corpus[:6000]
        try:
            return call_anthropic_structured(anthropic_key, company, small_corpus, max_tokens=300)
        except Exception:
            # Last resort: return minimal shell
            return {"company": {"name": company, "readiness": READINESS_VALUE}, "founders": []}


def write_temporary_to_neo4j(payload: Dict[str, Any]) -> None:
    company = payload.get("company") or {}
    founders = payload.get("founders") or []
    if not company.get("name"):
        return
    with get_neo4j_session() as session:
        # Allocate or find company id
        row = session.run("MATCH (c:Company {name:$n}) RETURN c.id AS id, c.slug AS slug", n=company["name"]).single()
        if row and row.get("id") is not None:
            company_id = int(row["id"])
        else:
            max_row = session.run("MATCH (c:Company) RETURN coalesce(max(c.id),0) AS mid").single()
            company_id = int((max_row and max_row["mid"] or 0)) + 1
            session.run(
                "MERGE (c:Company {id:$id}) SET c.name=$name, c.slug=$slug",
                id=company_id,
                name=company["name"],
                slug=create_slug(company["name"]),
            )

        # Update scalar properties and readiness on company
        session.run(
            """
            MATCH (c:Company {id:$id})
            SET c.website=$website,
                c.description=$description,
                c.location=$location,
                c.company_size=$company_size,
                c.founded_year=$founded_year,
                c.last_funding=$last_funding,
                c.readiness=$readiness
            """,
            id=company_id,
            website=company.get("website"),
            description=company.get("description"),
            location=company.get("location"),
            company_size=company.get("company_size"),
            founded_year=company.get("founded_year"),
            last_funding=company.get("last_funding"),
            readiness=READINESS_VALUE,
        )

        # Founders: create Person and FOUNDER_OF relations with readiness
        for f in founders:
            if not f.get("name"):
                continue
            # Person id allocation or find by name
            prow = session.run("MATCH (p:Person {name:$n}) RETURN p.id AS id", n=f["name"]).single()
            if prow and prow.get("id") is not None:
                pid = int(prow["id"])
            else:
                maxp = session.run("MATCH (p:Person) RETURN coalesce(max(p.id),0) AS mid").single()
                pid = int((maxp and maxp["mid"] or 0)) + 1
                session.run("MERGE (p:Person {id:$id}) SET p.name=$name, p.readiness=$readiness", id=pid, name=f["name"], readiness=READINESS_VALUE)

            session.run(
                """
                MATCH (p:Person {id:$pid}), (c:Company {id:$cid})
                MERGE (p)-[r:FOUNDER_OF]->(c)
                SET r.title=$title,
                    r.role=$role,
                    r.career_track=$career_track,
                    r.education_institution=$education_institution,
                    r.professional_company=$professional_company,
                    r.previous_companies=$previous_companies,
                    r.readiness=$readiness
                """,
                pid=pid,
                cid=company_id,
                title=f.get("title"),
                role=f.get("role"),
                career_track=f.get("career_track"),
                education_institution=f.get("education_institution"),
                professional_company=f.get("professional_company"),
                previous_companies=f.get("previous_companies") or [],
                readiness=READINESS_VALUE,
            )


def run_agent(companies: List[str], write_to_db: bool = True) -> List[Dict[str, Any]]:
    brave_key, anthropic_key = load_env()
    outputs: List[Dict[str, Any]] = []
    for name in companies:
        name = name.strip()
        if not name:
            continue
        data = collect_from_web(brave_key, anthropic_key, name)
        # Ensure readiness flags are present
        data.setdefault("company", {})
        data["company"].setdefault("readiness", READINESS_VALUE)
        for f in data.get("founders", []):
            f.setdefault("readiness", READINESS_VALUE)
        if write_to_db:
            write_temporary_to_neo4j(data)
        outputs.append(data)
    return outputs


def _parse_cli_args(argv: List[str]) -> List[str]:
    return [a for a in (argv or []) if a and a.strip()]


if __name__ == "__main__":
    # Usage: python agent/company_agent.py "Company A" "Company B"
    args = _parse_cli_args(sys.argv[1:])
    if not args:
        print("Usage: python agent/company_agent.py 'Company A' 'Company B'")
        sys.exit(1)
    try:
        result = run_agent(args, write_to_db=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)

