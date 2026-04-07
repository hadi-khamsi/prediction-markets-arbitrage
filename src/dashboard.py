from datetime import datetime

from rich.console import Console
from rich.table import Table

from .models import Opportunity

# Short labels for exchanges
EXCHANGE_LABELS = {
    "kalshi": "KAL",
    "polymarket": "POLY",
    "predictit": "PI",
}


class Dashboard:
    """Terminal dashboard for displaying arbitrage opportunities."""

    def __init__(self, max_rows: int = 10, title_width: int = 30):
        self.max_rows = max_rows
        self.title_width = title_width
        self.console = Console()
        if self.console.width < 120:
            self.console = Console(width=120)

    def render(
        self,
        opportunities: list[Opportunity],
        exchange_counts: dict[str, int],
        matched_count: int,
    ) -> None:
        """Render the dashboard with current opportunities."""
        self.console.clear()

        now = datetime.now().strftime("%H:%M:%S")
        counts_str = " | ".join(
            f"{EXCHANGE_LABELS.get(ex, ex[:3].upper())}:{cnt}"
            for ex, cnt in exchange_counts.items()
        )
        self.console.print("ARB SCANNER", style="bold")
        self.console.print(f"Last Updated: {now} | {counts_str} | Matched:{matched_count} | Arb:{len(opportunities)}")
        self.console.print()

        if not opportunities:
            self.console.print("No arbitrage. All spreads negative.", style="dim")
            self.console.print("Ctrl+C to exit", style="dim")
            return

        display_opps = opportunities
        if self.max_rows > 0:
            display_opps = opportunities[: self.max_rows]

        table = Table(show_header=True, header_style="bold", box=None, expand=False)
        table.add_column("#", width=2, no_wrap=True)
        table.add_column("PROFIT", style="green", width=7, no_wrap=True)
        table.add_column("SIM", width=3, no_wrap=True)
        table.add_column("EX1", width=self.title_width, overflow="ellipsis", no_wrap=True)
        table.add_column("$1", width=4, no_wrap=True)
        table.add_column("V1", width=5, no_wrap=True)
        table.add_column("EX2", width=self.title_width, overflow="ellipsis", no_wrap=True)
        table.add_column("$2", width=4, no_wrap=True)
        table.add_column("V2", width=5, no_wrap=True)
        table.add_column("EXP", width=5, no_wrap=True)
        table.add_column("ACT", width=11, no_wrap=True)

        for i, opp in enumerate(display_opps, 1):
            a = opp.pair.contract_a
            b = opp.pair.contract_b

            price_a = a.yes_price if "YES" in opp.action_a else a.no_price
            price_b = b.yes_price if "YES" in opp.action_b else b.no_price

            exp = ""
            if a.end_date:
                exp = a.end_date.strftime("%m/%d")
            elif b.end_date:
                exp = b.end_date.strftime("%m/%d")

            label_a = EXCHANGE_LABELS.get(a.exchange, a.exchange[:3].upper())
            label_b = EXCHANGE_LABELS.get(b.exchange, b.exchange[:3].upper())
            act_a = "Y" if "YES" in opp.action_a else "N"
            act_b = "Y" if "YES" in opp.action_b else "N"
            action = f"{label_a}:{act_a} {label_b}:{act_b}"

            table.add_row(
                str(i),
                f"${opp.profit:.3f}",
                f"{opp.pair.similarity:.0%}",
                a.title,
                f"{price_a:.2f}",
                self._format_volume(a.volume),
                b.title,
                f"{price_b:.2f}",
                self._format_volume(b.volume),
                exp,
                action,
            )

        self.console.print(table)
        self.console.print()
        self.console.print("Ctrl+C to exit", style="dim")

    def _parse_volume(self, volume) -> float | None:
        """Parse volume to float, handling strings."""
        if volume is None:
            return None
        try:
            return float(volume)
        except (ValueError, TypeError):
            return None

    def _format_volume(self, volume) -> str:
        """Format volume as human-readable string."""
        vol = self._parse_volume(volume)
        if vol is None:
            return "?"
        if vol >= 1_000_000:
            return f"${vol/1_000_000:.1f}M"
        if vol >= 1_000:
            return f"${vol/1_000:.0f}k"
        return f"${vol:.0f}"

