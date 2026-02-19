from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from .schema import ChangeInfo, FilterResult


def render_md(
    results: Sequence[FilterResult],
    changes: Sequence[ChangeInfo] | None = None,
) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    matches = [r for r in results if r.is_match]
    non_matches = [r for r in results if not r.is_match]

    lines: list[str] = [
        f"# Porsche 911 (992.1) Monitor Report",
        f"",
        f"Generated: {now}",
        f"",
        f"**Total listings scanned:** {len(results)}  ",
        f"**Matches:** {len(matches)}  ",
        f"**Rejected:** {len(non_matches)}",
        "",
    ]

    # --- Matches section ---
    if matches:
        lines.append("## Matches")
        lines.append("")
        sorted_matches = sorted(matches, key=lambda r: r.score, reverse=True)
        for i, r in enumerate(sorted_matches, 1):
            l = r.listing
            change = changes[results.index(r)] if changes and results.index(r) < len(changes) else None
            lines.append(f"### {i}. {l.title}")
            lines.append("")

            # Change indicator
            if change and change.is_new:
                lines.append("**NEW LISTING**")
                lines.append("")
            elif change and change.is_changed:
                change_parts = []
                for field, (old, new) in change.changes.items():
                    change_parts.append(f"{field}: {old} -> {new}")
                if change_parts:
                    lines.append(f"**CHANGED:** {', '.join(change_parts)}")
                    lines.append("")

            lines.append(f"| Field | Value |")
            lines.append(f"|---|---|")
            lines.append(f"| Price | {_fmt_price(l.price_eur)} |")
            lines.append(f"| Mileage | {_fmt_km(l.mileage_km)} |")
            lines.append(f"| Registration | {l.first_registration or 'N/A'} |")
            lines.append(f"| Location | {l.location or 'N/A'} |")
            lines.append(f"| Accident-free | {'Yes' if l.accident_free else 'No' if l.accident_free is False else 'N/A'} |")
            lines.append(f"| Porsche Approved | {l.porsche_approved_months or 'N/A'} months |")
            lines.append(f"| Owners | {l.owners or 'N/A'} |")
            lines.append(f"| Source | {l.source} |")
            if l.dealer_name:
                lines.append(f"| Dealer | {l.dealer_name} |")
            lines.append(f"| Score | {r.score} |")
            lines.append(f"| Link | [{l.url}]({l.url}) |")
            lines.append("")

            # Must-have checklist
            lines.append("**Must-have options:**")
            lines.append("")
            for opt, found in r.detected.items():
                if opt in _NICE_TO_HAVE_NAMES:
                    continue
                icon = "+" if found else "-"
                lines.append(f"  {icon} {opt}")
            lines.append("")

            # Nice-to-have
            if r.nice_to_have_present:
                lines.append(f"**Nice-to-have present:** {', '.join(r.nice_to_have_present)}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # --- Rejected section ---
    if non_matches:
        lines.append("## Rejected Listings")
        lines.append("")
        lines.append("| Title | Price | km | Reasons |")
        lines.append("|---|---:|---:|---|")
        for r in non_matches:
            l = r.listing
            reasons_str = "; ".join(r.reasons)
            lines.append(
                f"| [{l.title}]({l.url}) | {_fmt_price(l.price_eur)} | "
                f"{_fmt_km(l.mileage_km)} | {reasons_str} |"
            )
        lines.append("")

    return "\n".join(lines)


_NICE_TO_HAVE_NAMES = {
    "90L fuel tank",
    "Surround View / 360 camera",
    "Glass sunroof",
    "PPF / Steinschlagschutzfolie",
}


def _fmt_price(price: int | None) -> str:
    if price is None:
        return "N/A"
    return f"{price:,} EUR".replace(",", ".")


def _fmt_km(km: int | None) -> str:
    if km is None:
        return "N/A"
    return f"{km:,} km".replace(",", ".")


def write_report(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
