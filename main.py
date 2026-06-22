import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import slack as sl
from rich.console import Console
from rich.table import Table
from db_config import db_connect

console = Console()

MONTH_MAP = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}
MONTH_ORDER = ["jan", "feb", "mar", "apr", "may", "jun",
               "jul", "aug", "sep", "oct", "nov", "dec"]
STOCK_COLS = ["wh_sam", "q_kap", "q_baf", "q_sam"]

# NOTE: no ORDER BY / LIMIT here on purpose. Ranking the top N products
# needs to happen *after* the monthly rows are pivoted wide, otherwise
# LIMIT would cut individual product-month rows and leave gaps that look
# like "no sales" for months that just didn't make the row-level cutoff.
QUERY = """
WITH stock_data AS (
    SELECT
        sq.product_id AS pid,
        SUM(CASE WHEN sl.complete_name LIKE 'WH/Stock%%'
                 THEN (sq.quantity - sq.reserved_quantity)
                 ELSE 0 END) AS wh_sam,
        SUM(CASE WHEN sl.complete_name LIKE 'JS-BR%%'
                 THEN (sq.quantity - sq.reserved_quantity)
                 ELSE 0 END) AS js_br,
        SUM(CASE WHEN sl.complete_name LIKE 'JS-ch%%'
                 THEN (sq.quantity - sq.reserved_quantity)
                 ELSE 0 END) AS js_ch,
        SUM(CASE WHEN sl.complete_name LIKE 'JS-PK%%'
                 THEN (sq.quantity - sq.reserved_quantity)
                 ELSE 0 END) AS js_pk,
        SUM(CASE WHEN sl.complete_name LIKE 'Q-SAM%%'
                 THEN (sq.quantity - sq.reserved_quantity)
                 ELSE 0 END) AS q_sam,
        SUM(CASE WHEN sl.complete_name LIKE 'Q-BAF%%'
                 THEN (sq.quantity - sq.reserved_quantity)
                 ELSE 0 END) AS q_baf,
        SUM(CASE WHEN sl.complete_name LIKE 'Q-KAP%%'
                 THEN (sq.quantity - sq.reserved_quantity)
                 ELSE 0 END) AS q_kap
    FROM stock_quant sq
    JOIN stock_location sl
        ON sq.location_id = sl.id
       AND sl.usage = 'internal'
    GROUP BY sq.product_id
),
sale_summary AS (
    SELECT
        sol.product_id,
        EXTRACT(MONTH FROM sol.create_date)::int AS month,
        SUM(sol.qty_delivered) AS qty_delivered
    FROM sale_order_line sol
    JOIN sale_order so ON sol.order_id = so.id
    WHERE sol.create_date >= %s
      AND sol.create_date < %s
      AND so.is_quickee_order = true
    GROUP BY sol.product_id, EXTRACT(MONTH FROM sol.create_date)
)
SELECT
    CASE
        WHEN pt.name::text LIKE '{%%}' THEN
            COALESCE(
                (pt.name::jsonb) ->> 'en_US',
                (pt.name::jsonb) ->> 'en_GB',
                pt.name::text
            )
        ELSE pt.name::text
    END AS product_name,
    sd.wh_sam,
    sd.q_kap,
    sd.q_baf,
    sd.q_sam,
    ss.qty_delivered,
    ss.month
FROM sale_summary ss
JOIN stock_data sd
    ON ss.product_id = sd.pid
JOIN product_product pp
    ON ss.product_id = pp.id
JOIN product_template pt
    ON pp.product_tmpl_id = pt.id
ORDER BY ss.product_id, ss.month;
"""


def get_date_range(months=6):
    end_date = datetime.now()
    start_date = end_date - relativedelta(months=months)
    return start_date, end_date


def fetch_dataframe(conn, query, params=()):
    # psycopg2 connections work fine with pd.read_sql; pandas may emit a
    # harmless UserWarning since it officially prefers SQLAlchemy connections.
    df = pd.read_sql(query, conn, params=params)

    # Postgres NUMERIC/SUM columns come back from psycopg2 as Decimal, not
    # float. Decimal can be compared against float fine, but multiplying
    # Decimal * float (like in transfer_value below) raises a TypeError.
    # Cast early so nothing downstream has to think about it.
    df[STOCK_COLS] = df[STOCK_COLS].astype(float)
    df["qty_delivered"] = df["qty_delivered"].astype(float)

    return df


def build_wide_report(df, top_n=10):
    df = df.copy()
    df["month"] = df["month"].map(MONTH_MAP)

    wide = df.pivot_table(
        index=["product_name"] + STOCK_COLS,
        columns="month",
        values="qty_delivered",
        aggfunc="median",
        fill_value=0,
    ).reset_index()

    existing_months = [m for m in MONTH_ORDER if m in wide.columns]
    wide = wide[["product_name"] + STOCK_COLS + existing_months]

    wide["mid_delivered"] = wide[existing_months].median(axis=1)
    wide = wide.sort_values("mid_delivered", ascending=False)
    # wide = wide.head(top_n)  # re-enable once you want it capped again

    return wide


def print_report(df):
    table = Table(title="Sales vs Stock Report", show_lines=True)

    for col in df.columns:
        table.add_column(str(col), style="cyan", overflow="fold")

    for _, row in df.iterrows():
        table.add_row(*[str(v) if pd.notna(v) else "0" for v in row])

    console.print(table)


def transfer_value(to, froms, ans):
    if to < ans:
        ans = ans - to
    else:
        ans = 0

    ans = min(int(min(froms * 0.40, ans)), 3)
    return ans


def make_transfer(df):
    t_baf = []
    t_sam = []
    t_kap = []

    for _, row in df.iterrows():
        ans = row["mid_delivered"]

        baf_ans = transfer_value(row["q_baf"], row["wh_sam"], ans)
        sam_ans = transfer_value(row["q_sam"], row["wh_sam"], ans)
        kap_ans = transfer_value(row["q_kap"], row["wh_sam"], ans)

        t_baf.append(baf_ans)
        t_sam.append(sam_ans)
        t_kap.append(kap_ans)

    df["T_kap"] = t_kap
    df["T_sam"] = t_sam
    df["T_baf"] = t_baf

    return df


def main():
    conn = None
    try:
        conn = db_connect()
        console.print("[green]Database connected successfully[/green]")

        start_date, end_date = get_date_range(6)
        print("Start_Date -> ", start_date)
        print("End_Date -> ", end_date)

        df = fetch_dataframe(conn, QUERY, (start_date, end_date))
        wide = build_wide_report(df)
        wide = make_transfer(wide)
        print_report(wide)
        wide.to_excel("QuikeeTransferOut.xlsx", index=False)
        transfer_file = "./QuikeeTransferOut.xlsx"
        notifier = sl.SlackNotifier()
        notifier.send_file(
            file_path=transfer_file,
            initial_comment="Here is the Transfer Excel report file for Quickee Order"
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
