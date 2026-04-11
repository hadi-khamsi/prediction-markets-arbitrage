from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import Opportunity

# Short labels for exchanges
EXCHANGE_LABELS = {
    "kalshi": "KAL",
    "polymarket": "POLY",
    "predictit": "PI",
}


class Dashboard:
    """Terminal dashboard for displaying arbitrage opportunities."""

    def __init__(self, max_rows: int = 10, title_width: int = 40):
        self.max_rows = max_rows
        self.title_width = title_width
        self.console = Console()
        if self.console.width < 140:
            self.console = Console(width=140)

    def render(
        self,
        opportunities: list[Opportunity],
        exchange_counts: dict[str, int],
        matched_count: int,
        latencies: dict[str, int] | None = None,
    ) -> None:
        """Render the dashboard with current opportunities."""
        self.console.clear()

        now = datetime.now().strftime("%H:%M:%S")

        # Header line 1: Title and status
        header = Text()
        header.append("ARB SCANNER", style="bold white")
        header.append("  ")
        header.append("● LIVE", style="bold green")
        self.console.print(header)

        # Header line 2: Stats
        counts_parts = []
        for ex, cnt in exchange_counts.items():
            label = EXCHANGE_LABELS.get(ex, ex[:3].upper())
            lat = ""
            if latencies and ex in latencies:
                lat = f" ({latencies[ex]}ms)"
            counts_parts.append(f"{label}:{cnt}{lat}")
        counts_str = " | ".join(counts_parts)

        stats = Text()
        stats.append(f"Updated: {now}", style="cyan")
        stats.append(f"  {counts_str}", style="white")
        stats.append(f"  Matched:{matched_count}", style="yellow")
        stats.append(f"  Arb:{len(opportunities)}", style="green" if opportunities else "dim")
        self.console.print(stats)
        self.console.print()

        if not opportunities:
            self.console.print("No arbitrage opportunities. All spreads negative.", style="dim")
            self.console.print()
            self.console.print("Ctrl+C to exit", style="dim")
            return

        display_opps = opportunities
        if self.max_rows > 0:
            display_opps = opportunities[: self.max_rows]

        table = Table(show_header=True, header_style="bold", box=None, expand=False, padding=(0, 1))
        table.add_column("#", width=2, no_wrap=True)
        table.add_column("PROFIT", style="green", width=7, no_wrap=True)
        table.add_column("SIM", width=4, no_wrap=True)
        table.add_column("TYPE", width=4, no_wrap=True)
        table.add_column("CONTRACT 1", width=self.title_width, overflow="fold")
        table.add_column("$", width=4, no_wrap=True)
        table.add_column("VOL", width=5, no_wrap=True)
        table.add_column("CONTRACT 2", width=self.title_width, overflow="fold")
        table.add_column("$", width=4, no_wrap=True)
        table.add_column("VOL", width=5, no_wrap=True)
        table.add_column("EXP", width=5, no_wrap=True)
        table.add_column("ACTION", width=13, no_wrap=True)

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

            # Format title with exchange prefix
            title_a = f"[{label_a}] {a.title}"
            title_b = f"[{label_b}] {b.title}"

            # Match type indicator
            match_type = opp.pair.match_type[:3].upper()  # "IDE" or "OPP"

            table.add_row(
                str(i),
                f"${opp.profit:.3f}",
                f"{opp.pair.similarity:.0%}",
                match_type,
                title_a,
                f"{price_a:.2f}",
                self._format_volume(a.volume),
                title_b,
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
