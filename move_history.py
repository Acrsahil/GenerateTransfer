from db_config import db_connect

TRANSFER_QUERY = '''
SELECT
    pt.name->>'en_US' AS product_name,
    SUM(sm.qty_done) AS qty_done,
    CASE
        WHEN sm.state = 'waiting'   THEN 'Waiting Another Move'
        WHEN sm.state = 'confirmed' THEN 'Waiting Availability'
        WHEN sm.state = 'assigned'  THEN 'Available'
        WHEN sm.state = 'draft'     THEN 'New'
        WHEN sm.state = 'cancel'    THEN 'Cancelled'
        WHEN sm.state = 'done'      THEN 'Done'
        ELSE sm.state
    END AS status,
    SUBSTRING(sl.complete_name  FROM '^[^/]*/[^/]*') AS source_location,
    SUBSTRING(sld.complete_name FROM '^[^/]*/[^/]*') AS destination_location
FROM
    stock_move_line sm
    JOIN product_product pp  ON sm.product_id        = pp.id
    JOIN product_template pt ON pp.product_tmpl_id   = pt.id
    JOIN stock_location sl   ON sm.location_id        = sl.id
    JOIN stock_location sld  ON sm.location_dest_id   = sld.id
WHERE
    sm.create_date >= %s
    AND sm.create_date <= %s
    AND sm.state IN ('assigned', 'done')
    AND SUBSTRING(sl.complete_name  FROM '^[^/]*/[^/]*') = %s
    AND SUBSTRING(sld.complete_name FROM '^[^/]*/[^/]*') = %s
GROUP BY
    pt.name,
    source_location,
    destination_location,
    sm.state
ORDER BY qty_done DESC
'''

COLUMNS = ["product_name", "qty_done", "status", "source_location", "destination_location"]


def fetch_transfers(date_from: str, date_to: str, source: str, destination: str) -> list[dict]:
    """
    Run the transfer query and return a list of row dicts.
    Raises on DB error.
    """
    params = (date_from, date_to, source, destination)
    conn = db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(TRANSFER_QUERY, params)
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]
            return [dict(zip(col_names, row)) for row in rows]
    finally:
        conn.close()
