"""
database.py - Neo4j-only helper module

Provides a global Neo4j driver, constraint initialization, and session helper.
All SQLAlchemy/SQLite code has been removed to operate Neo4j-only.
"""

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable
import os
from pathlib import Path
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # optional dependency

# Load environment variables
# 1) Standard .env if present
if load_dotenv:
    load_dotenv()

# 2) Auto-load Neo4j Desktop/Cloud credentials file if present in repo or app root
if load_dotenv:
    try:
        here = Path(__file__).resolve()
        parents = list(here.parents)
        # Typical candidates: .../wdiw and repo root .../crystaldoor
        candidate_dirs = []
        if len(parents) > 2:
            candidate_dirs.append(parents[2])  # wdiw
        if len(parents) > 3:
            candidate_dirs.append(parents[3])  # repo root
        for base in candidate_dirs:
            for p in base.glob("Neo4j-*-Created-*.txt"):
                load_dotenv(dotenv_path=str(p), override=False)
                raise StopIteration
    except StopIteration:
        pass
    except Exception as e:
        print(f"[neo4j] Could not auto-load credentials file: {e}")

# Neo4j configuration
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
# Support both NEO4J_USER and NEO4J_USERNAME
NEO4J_USER = os.environ.get("NEO4J_USER") or os.environ.get("NEO4J_USERNAME", "neo4j")
# Do not default password to a likely-wrong value to avoid auth rate limiting loops
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

if not NEO4J_PASSWORD:
    raise RuntimeError(
        "NEO4J_PASSWORD is not set. Export NEO4J_PASSWORD (and NEO4J_URI/NEO4J_USER if needed) before starting the app."
    )

neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def verify_neo4j_connectivity() -> bool:
    try:
        neo4j_driver.verify_connectivity()
        return True
    except AuthError as e:
        print(f"[neo4j] Authentication failed or rate-limited: {e}")
        return False
    except ServiceUnavailable as e:
        print(f"[neo4j] Service unavailable: {e}")
        return False
    except Exception as e:
        print(f"[neo4j] Connectivity check error: {e}")
        return False

def init_neo4j_constraints():
    """Create uniqueness constraints and indexes for Neo4j if they don't exist."""
    if not verify_neo4j_connectivity():
        print("[neo4j] Skipping constraint initialization due to connectivity/auth issues.")
        return
    try:
        with neo4j_driver.session() as session:
            def safe_run(cypher: str):
                try:
                    session.run(cypher)
                except Exception as e:
                    print(f"[neo4j] constraint error for `{cypher}`: {e}")

            # Company unique by id and slug
            safe_run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE")
            safe_run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.slug IS UNIQUE")
            # Person unique by id and name
            safe_run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE")
            safe_run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE")
            # Tag unique by name
            safe_run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE")
            # Investor unique by id and by name
            safe_run("CREATE CONSTRAINT IF NOT EXISTS FOR (i:Investor) REQUIRE i.id IS UNIQUE")
            safe_run("CREATE CONSTRAINT IF NOT EXISTS FOR (i:Investor) REQUIRE i.name IS UNIQUE")
    except Exception as e:
        print(f"[neo4j] Failed to initialize constraints: {e}")

def get_neo4j_session():
    return neo4j_driver.session()