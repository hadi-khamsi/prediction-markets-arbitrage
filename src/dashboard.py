from datetime import datetime

from rich.console import Console
from rich.table import Table

from .models import Opportunity


class Dashboard:
    """Terminal dashboard for displaying arbitrage opportunities."""

    def __init__(self):
        # Use detected width but ensure minimum of 120 for proper display
        self.console = Console()
        if self.console.width < 120:
            self.console = Console(width=120)

    def render(
        self,
        opportunities: list[Opportunity],
        kalshi_count: int,
        poly_count: int,
        matched_count: int,
    ) -> None:
        """Render the dashboard with current opportunities."""
        self.console.clear()

        # Header - Bloomberg terminal style
        now = datetime.now().strftime("%H:%M:%S")
        self.console.print(f"PREDICTION MARKETS", style="bold")
        self.console.print(f"{now} | K:{kalshi_count} | P:{poly_count} | Matched:{matched_count} | Arb:{len(opportunities)}")
        self.console.print()

        if not opportunities:
            self.console.print("No arbitrage. All spreads negative.", style="dim")
            self.console.print("Ctrl+C to exit", style="dim")
            return

        # Create table - optimized for 120 char terminal
        table = Table(show_header=True, header_style="bold", box=None, expand=False)
        table.add_column("#", width=2, no_wrap=True)
        table.add_column("PROFIT", style="green", width=7, no_wrap=True)
        table.add_column("SIM", width=3, no_wrap=True)
        table.add_column("KALSHI", width=24, overflow="ellipsis", no_wrap=True)
        table.add_column("K$", width=4, no_wrap=True)
        table.add_column("KV", width=5, no_wrap=True)
        table.add_column("POLY", width=24, overflow="ellipsis", no_wrap=True)
        table.add_column("P$", width=4, no_wrap=True)
        table.add_column("PV", width=5, no_wrap=True)
        table.add_column("LQ", width=2, no_wrap=True)
        table.add_column("EXP", width=5, no_wrap=True)
        table.add_column("ACT", width=7, no_wrap=True)

        for i, opp in enumerate(opportunities, 1):
            kalshi = opp.pair.contract_a if opp.pair.contract_a.exchange == "kalshi" else opp.pair.contract_b
            poly = opp.pair.contract_b if opp.pair.contract_b.exchange == "polymarket" else opp.pair.contract_a

            k_price = kalshi.yes_price if "YES" in opp.kalshi_action else kalshi.no_price
            p_price = poly.yes_price if "YES" in opp.poly_action else poly.no_price

            exp = ""
            if kalshi.end_date:
                exp = kalshi.end_date.strftime("%m/%d")
            elif poly.end_date:
                exp = poly.end_date.strftime("%m/%d")

            # Clear action format with space
            k_act = "Y" if "YES" in opp.kalshi_action else "N"
            p_act = "Y" if "YES" in opp.poly_action else "N"
            action = f"K:{k_act} P:{p_act}"

            # Format volume
            k_vol = self._format_volume(kalshi.volume)
            p_vol = self._format_volume(poly.volume)

            # Liquidity indicator based on min volume of the pair
            liq = self._liquidity_indicator(kalshi.volume, poly.volume)

            table.add_row(
                str(i),
                f"${opp.profit:.3f}",
                f"{opp.pair.similarity:.0%}",
                kalshi.title,
                f"{k_price:.2f}",
                k_vol,
                poly.title,
                f"{p_price:.2f}",
                p_vol,
                liq,
                exp,
                action,
            )

        self.console.print(table)
        self.console.print()
        self.console.print("LIQ: [green]H[/green]>$100k [yellow]M[/yellow]$10-100k [red]L[/red]<$10k", style="dim")
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

    def _liquidity_indicator(self, vol_a, vol_b) -> str:
        """Return liquidity indicator based on minimum volume of pair."""
        a = self._parse_volume(vol_a)
        b = self._parse_volume(vol_b)
        if a is None or b is None:
            return "?"
        min_vol = min(a, b)
        if min_vol >= 100_000:
            return "[green]H[/green]"
        if min_vol >= 10_000:
            return "[yellow]M[/yellow]"
        return "[red]L[/red]"
