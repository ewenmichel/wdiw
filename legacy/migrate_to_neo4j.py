import os
from database import get_db, is_neo4j_sync_enabled
import crud


def main():
    if not is_neo4j_sync_enabled():
        print("Neo4j sync is disabled. Set NEO4J_SYNC=1 and configure NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD.")
        return
    db = next(get_db())
    summary = crud.sync_all_to_neo4j(db)
    print(f"Backfill summary: {summary}")


if __name__ == "__main__":
    main()

