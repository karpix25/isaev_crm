import asyncio
import asyncpg

async def scan_db(url, db_name):
    print(f"\nScanning {db_name}...")
    try:
        conn = await asyncpg.connect(url)
        rows = await conn.fetch("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema')")
        for r in rows:
            print(f"- {r['table_schema']}.{r['table_name']}")
            if r['table_name'] == 'leads':
                print(f"!!! FOUND leads in {db_name}.{r['table_schema']} !!!")
                # Apply migration here
                print("Applying migration...")
                try:
                    await conn.execute("CREATE TYPE readiness_score AS ENUM ('A', 'B', 'C');")
                except Exception as e:
                    print("Type creation warning:", e)
                try:
                    await conn.execute("ALTER TABLE leads ADD COLUMN readiness_score readiness_score NULL;")
                    print("SUCCESSFULLY APPLIED MIGRATION!")
                except Exception as e:
                    print("Column addition warning:", e)
                
        await conn.close()
    except Exception as e:
        print(f"Error scanning {db_name}:", e)

async def main():
    await scan_db('postgresql://nadaraya:C%40rlo1822@162.244.24.212:5434/postgres?sslmode=disable', 'postgres')

if __name__ == '__main__':
    asyncio.run(main())
