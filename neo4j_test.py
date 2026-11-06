import asyncio
from neo4j import AsyncGraphDatabase
from backend.app.settings import setting

URI = setting.neo4j_db_uri
AUTH = (setting.neo4j_username, setting.neo4j_password.get_secret_value())


async def test_neo4j():
    print("Starting Neo4j test...")

    driver = AsyncGraphDatabase.driver(
        URI,
        auth=AUTH,
    )

    try:
        print("Testing connectivity...")

        await driver.verify_connectivity()

        print("Neo4j connectivity OK")

        async with driver.session() as session:
            result = await session.run(
                "RETURN 1 AS value"
            )

            record = await result.single()

            print("Query result:", record["value"])

    except Exception as e:
        print("Neo4j test FAILED")
        print("Error type:", type(e).__name__)
        print("Error:", e)

    finally:
        await driver.close()
        print("Driver closed")


if __name__ == "__main__":
    asyncio.run(test_neo4j())