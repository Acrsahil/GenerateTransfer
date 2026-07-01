import os
import sys
from datetime import date, timedelta
import pandas as pd

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich import box

# ── Import the query module ──────────────────────────────────────────────────
from move_history import fetch_transfers, COLUMNS

console = Console()

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_DATE_FROM   = (date.today() - timedelta(days=1)).isoformat()   # yesterday
DEFAULT_DATE_TO     = date.today().isoformat()                          # today
DEFAULT_SOURCE      = "WH/input"   # lowercase i
DEFAULT_DESTINATION = "WH/Stock"


# ── Helpers ──────────────────────────────────────────────────────────────────
def ask(label: str, default: str, hint: str = "") -> str:
    """Prompt with a coloured label and optional hint."""
    hint_str = f" [dim]({hint})[/dim]" if hint else ""
    return Prompt.ask(f"  [bold cyan]{label}[/bold cyan]{hint_str}", default=default)


def validate_date(value: str, label: str) -> str:
    """Ensure value is a valid YYYY-MM-DD date; re-prompt on error."""
    while True:
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            console.print(f"  [red]✗  Invalid date for {label}. Use YYYY-MM-DD.[/red]")
            value = Prompt.ask(f"  [bold cyan]{label}[/bold cyan]")


def validate_xlsx_path(path: str) -> str | None:
    if path.strip() == "":
        return None
    path = path.strip()
    if not path.lower().endswith(".xlsx"):
        console.print("  [red]✗  File must be an .xlsx file.[/red]")
        return None
    if not os.path.isfile(path):
        console.print(f"  [red]✗  File not found:[/red] {path}")
        return None
    return path


def render_table(rows: list[dict]) -> None:
    """Render query results as a Rich table."""
    table = Table(
        show_lines=True,
        box=box.ROUNDED,
        header_style="bold magenta",
        border_style="bright_black",
    )
    col_styles = {
        "product_name":       ("cyan",   40),
        "qty_done":           ("green",  10),
        "status":             ("yellow", 22),
        "source_location":    ("white",  18),
        "destination_location": ("white", 18),
    }
    for col in COLUMNS:
        style, width = col_styles.get(col, ("white", 20))
        table.add_column(col.replace("_", " ").title(), style=style,
                         min_width=width, overflow="fold")

    for row in rows:
        table.add_row(*[str(row.get(c, "")) if row.get(c) is not None else "—"
                        for c in COLUMNS])
    console.print(table)


# ── Main UI ──────────────────────────────────────────────────────────────────
def main() -> None:
    console.clear()
    console.print(Panel(
        "[bold white]Stock Transfer Sheet[/bold white]\n"
        "[dim]Query stock move lines between two locations[/dim]",
        style="bright_blue",
        padding=(1, 4),
    ))

    # ── Section 1 : Query Parameters ─────────────────────────────────────────
    console.print(Rule("[bold]Query Parameters[/bold]", style="bright_black"))
    console.print()

    date_from = validate_date(
        ask("Date From", DEFAULT_DATE_FROM, "YYYY-MM-DD"),
        "Date From",
    )
    date_to = validate_date(
        ask("Date To",   DEFAULT_DATE_TO,   "YYYY-MM-DD"),
        "Date To",
    )
    source      = ask("Source Location",      DEFAULT_SOURCE,      "e.g. WH/Input")
    destination = ask("Destination Location", DEFAULT_DESTINATION, "e.g. WH/Stock")

    # ── Section 2 : File Upload ───────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]File Upload (optional)[/bold]", style="bright_black"))
    console.print("  [dim]Provide a .xlsx transfer sheet to attach, or press Enter to skip.[/dim]")
    console.print()

    xlsx_path: str | None = None
    while True:
        raw = Prompt.ask("  [bold cyan]Excel file path[/bold cyan] [dim](.xlsx)[/dim]",
                         default="")
        xlsx_path = validate_xlsx_path(raw)
        if raw.strip() == "" or xlsx_path is not None:
            break
        # invalid but non-blank — ask again
        retry = Prompt.ask("  Try again?", choices=["y", "n"], default="y")
        if retry == "n":
            break

    if xlsx_path:
        console.print(f"  [green]✓  File loaded:[/green] {xlsx_path}")
    else:
        console.print("  [dim]No file attached.[/dim]")
    

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold]Date range :[/bold]  {date_from}  →  {date_to}\n"
        f"[bold]Source     :[/bold]  {source}\n"
        f"[bold]Destination:[/bold]  {destination}\n"
        f"[bold]Excel file :[/bold]  {xlsx_path or '—  (none)'}",
        title="[bold white]Confirmed Parameters[/bold white]",
        style="green",
        padding=(1, 4),
    ))

    confirm = Prompt.ask("\n  Run query?", choices=["y", "n"], default="y")
    if confirm != "y":
        console.print("\n  [yellow]Aborted.[/yellow]")
        sys.exit(0)

    # ── Run Query ─────────────────────────────────────────────────────────────
    console.print()
    with console.status("[bold cyan]Fetching transfers from database…[/bold cyan]"):
        try:
            rows = fetch_transfers(date_from, date_to, source, destination)
        except Exception as exc:
            console.print(f"\n  [bold red]DB Error:[/bold red] {exc}")
            sys.exit(1)

    console.print(Rule(f"[bold]Results — {len(rows)} row(s)[/bold]", style="bright_black"))
    console.print()

    if not rows:
        console.print("  [yellow]No records found for the given parameters.[/yellow]")

    else:
        # print("Distrub!")
        if xlsx_path:
            df1 = pd.DataFrame(rows)
            df2 = pd.read_excel(xlsx_path)

            print(df1.head())
            print(df2.head())

        render_table(rows)
    console.print()


if __name__ == "__main__":
    main()
