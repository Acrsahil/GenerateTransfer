from db_config import db_connect
from rich.console import Console
from rich.table import Table

console = Console()

query = '''
SELECT sm.name,sm.create_date,sm.location_id,sm.product_qty FROM stock_move sm
WHERE sm.name LIKE '%ANUA 7 RICE CERAMIDE HYDRATING BARRIER SERUM - 50ML%'
AND sm.create_date >= '2026-06-18'
ORDER BY sm.product_qty DESC LIMIT 1;
'''

query2 = '''

'''

conn = db_connect()
cursor = conn.cursor()
cursor.execute(query)
rows = cursor.fetchall()

# cursor.description gives you column names after execute()
columns = [desc[0] for desc in cursor.description]

table = Table(show_lines=True)
for col in columns:
    table.add_column(col, style="cyan", overflow="fold")

for row in rows:
    table.add_row(*[str(v) if v is not None else "NULL" for v in row])

console.print(table)

cursor.close()
conn.close()
