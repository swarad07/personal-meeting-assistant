from collections.abc import AsyncGenerator

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import settings

_driver: AsyncDriver | None = None


async def get_neo4j_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def get_neo4j_session() -> AsyncGenerator:
    driver = await get_neo4j_driver()
    async with driver.session() as session:
        yield session


async def close_neo4j_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def init_neo4j_constraints() -> None:
    """Create uniqueness constraints and indexes on Neo4j nodes."""
    driver = await get_neo4j_driver()
    constraints = [
        "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT org_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
        "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
        "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT meeting_id IF NOT EXISTS FOR (m:Meeting) REQUIRE m.id IS UNIQUE",
    ]
    async with driver.session() as session:
        for constraint in constraints:
            await session.run(constraint)
