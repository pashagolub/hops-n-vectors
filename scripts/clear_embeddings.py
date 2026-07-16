"""Force a full re-embed by nullifying all stored embeddings."""
from hopsnvectors.db import get_connection

conn = get_connection()
with conn.cursor() as cur:
    cur.execute("UPDATE beers SET embedding = NULL, embedded_at = NULL")
    print(f"Cleared embeddings for {cur.rowcount} rows.")
conn.commit()
conn.close()
