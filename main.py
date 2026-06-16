import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "odoo"),
    "user":     os.getenv("DB_USER", "odoo"),
    "password": os.getenv("DB_PASSWORD", "odoo"),
    }



def db_connect():
    try:
        
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_session(readonly=True, autocommit=True)
        print("Database connected successfully")

        with conn.cursor() as cr:
            cr.execute('''
            with stock_data as(

                SELECT 
                  sq.product_id as pid,
                  SUM(CASE 
                          WHEN sl.complete_name LIKE 'WH/Stock%' 
                          THEN (sq.quantity - sq.reserved_quantity) 
                          ELSE 0 
                      END) AS wh_sam,
                  SUM(CASE 
                          WHEN sl.complete_name LIKE 'JS-BR%' 
                          THEN (sq.quantity - sq.reserved_quantity) 
                          ELSE 0 
                      END) AS js_br,
                  SUM(CASE 
                          WHEN sl.complete_name LIKE 'JS-ch%' 
                          THEN (sq.quantity - sq.reserved_quantity) 
                          ELSE 0 
                      END) AS js_ch,
                  SUM(CASE 
                          WHEN sl.complete_name LIKE 'JS-PK%' 
                          THEN (sq.quantity - sq.reserved_quantity) 
                          ELSE 0 
                      END) AS js_pk,
                  SUM(CASE 
                          WHEN sl.complete_name LIKE 'Q-SAM%' 
                          THEN (sq.quantity - sq.reserved_quantity) 
                          ELSE 0 
                      END) AS q_sam,
                  SUM(CASE 
                          WHEN sl.complete_name LIKE 'Q-BAF%' 
                          THEN (sq.quantity - sq.reserved_quantity) 
                          ELSE 0 
                      END) AS q_baf,
                  SUM(CASE 
                          WHEN sl.complete_name LIKE 'Q-KAP%' 
                          THEN (sq.quantity - sq.reserved_quantity) 
                          ELSE 0 
                      END) AS q_kap
                FROM stock_quant sq
                JOIN stock_location sl
                  ON sq.location_id = sl.id
                AND sl.usage = 'internal'
                JOIN product_product pp ON sq.product_id = pp.id 
                GROUP BY sq.product_id
                LIMIT 10
            ),
            sale_summary as (
            select product_id ,sum(qty_delivered) as delivered_qty from sale_order_line 
            group by product_id order by product_id limit 10
            )

            -- select
            -- case WHEN pt.name::text LIKE '{%}' THEN (pt.name::jsonb) ->> 'en_US'
            -- END AS product_name,
            -- COALESCE(wh_sam,0) as Qty_wh_Sam from  stock_data sd 
            -- join  product_product pp on sd.pid = pp.id 
            -- join  product_template pt on pp.product_tmpl_id = pt.id 

            select 
                CASE 
                   WHEN pt.name::text LIKE '{%}' THEN 
                        COALESCE((pt.name::jsonb) ->> 'en_US', (pt.name::jsonb) ->> 'en_GB', pt.name::text)
                   ELSE pt.name::text 
                END AS product_name
            ,sd.wh_sam ,ss.delivered_qty from sale_summary ss 
            join  stock_data sd on ss.product_id = sd.pid
            join product_template pt on ss.product_id = pt.id limit 10
            '''
            )

            headers = [desc[0] for desc in cr.description]
            print("\t".join(headers))

            data = cr.fetchall()
            for row in data:
                print("\t ".join(map(str, row)))

        return conn

    except Exception as e:
        print("Database connection failed:", e)
        return None


db_connect()



