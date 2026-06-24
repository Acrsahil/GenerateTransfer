from db_config import db_connect
from rich.console import Console
from rich.table import Table

console = Console()

query = '''
SELECT sm.name,sm.create_date,sm.location_id,sm.product_qty FROM stock_move sm
WHERE sm.name LIKE '%ANUA 7 RICE CERAMIDE HYDRATING BARRIER SERUM - 50ML%'
AND sm.create_date >= '2026-06-18'
ORDER BY sm.product_qty DESC LIMIT 5;
'''

query2 = '''
select
    pt.name->>'en_US' AS product_name,
    sum(sm.qty_done) as Qty_Done,
    case when sm.state = 'waiting' then 'Waiting Another Move'
    when sm.state = 'confirmed' then 'Waiting Availibility'
    when sm.state = 'assigned' then 'Available'
    when sm.state = 'draft' then 'New'
    when sm.state = 'cancel' then 'Cancelled'
    when sm.state = 'done' then 'Done'	
    else sm.state
    end as status,
    substring(
        sl.complete_name
        FROM '^[^/]*/[^/]*'
    ) AS Source_Location,
    substring(
        sld.complete_name
        FROM '^[^/]*/[^/]*'
    ) AS Destination_Location
from
    stock_move_line sm
    join product_product pp on sm.product_id = pp.id
    join product_template pt on pp.product_tmpl_id = pt.id
    join stock_location sl on sm.location_id = sl.id
    join stock_location sld on sm.location_dest_id = sld.id
where
    sm.create_date >=%s and sm.create_date<=%s and (sm.state = 'assigned' or sm.state = 'done')
    and substring(
        sl.complete_name
        FROM '^[^/]*/[^/]*'
    ) = %s

        and substring(
        sld.complete_name
        FROM '^[^/]*/[^/]*'
    ) = %s


group by
    pt.name,
    Source_Location,
    Destination_Location,
    state 
    order by Qty_Done desc
    LIMIT 20;
'''

parms = ('2026-06-23','2026-06-24','WH/input','WH/Stock')
conn = db_connect()
cursor = conn.cursor()
cursor.execute(query2,parms)
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
