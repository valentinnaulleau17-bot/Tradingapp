"""
Position manager — stores active position and history in a local JSON file.
Supports multi-entry (average-down / average-up) and leveraged P&L.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent / "data" / "positions.json"


def _load() -> dict:
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _DATA_FILE.exists():
        _DATA_FILE.write_text(json.dumps({"active": None, "history": []}, indent=2))
    with open(_DATA_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def _save(data: dict) -> None:
    with open(_DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


# ── public API ───────────────────────────────────────────────────────────────

def get_active() -> dict | None:
    return _load()["active"]


def get_history() -> list[dict]:
    return _load()["history"]


def open_position(
    *,
    asset: str,
    direction: str,
    signal_type: str,
    entry_price: float,
    quantity: float,
    leverage: int,
    stop_loss: float,
    take_profit: float,
    note: str = "",
) -> None:
    data = _load()
    if data["active"]:
        raise ValueError("Une position est déjà ouverte — fermez-la d'abord.")
    data["active"] = {
        "id": datetime.now().isoformat(),
        "asset": asset,
        "direction": direction,
        "signal_type": signal_type,
        "leverage": leverage,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "note": note,
        "entries": [
            {"price": entry_price, "quantity": quantity, "date": datetime.now().isoformat()}
        ],
        "average_price": entry_price,
        "total_quantity": quantity,
        "opened_at": datetime.now().isoformat(),
        "status": "open",
    }
    _save(data)


def add_entry(entry_price: float, quantity: float) -> None:
    data = _load()
    pos = data["active"]
    if not pos:
        raise ValueError("Aucune position active.")
    pos["entries"].append({
        "price": entry_price,
        "quantity": quantity,
        "date": datetime.now().isoformat(),
    })
    total_cost = sum(e["price"] * e["quantity"] for e in pos["entries"])
    total_qty  = sum(e["quantity"] for e in pos["entries"])
    pos["average_price"]  = total_cost / total_qty
    pos["total_quantity"] = total_qty
    _save(data)


def close_position(exit_price: float) -> dict:
    data = _load()
    pos = data["active"]
    if not pos:
        raise ValueError("Aucune position active.")

    avg   = pos["average_price"]
    qty   = pos["total_quantity"]
    lev   = pos["leverage"]

    gross_pnl = (exit_price - avg) * qty
    if pos["direction"] == "short":
        gross_pnl = -gross_pnl

    pnl_pct          = gross_pnl / (avg * qty) * 100 if avg else 0
    leveraged_pnl_pct = pnl_pct * lev

    pos.update(
        exit_price=exit_price,
        closed_at=datetime.now().isoformat(),
        gross_pnl=gross_pnl,
        pnl_pct=pnl_pct,
        leveraged_pnl_pct=leveraged_pnl_pct,
        status="closed",
    )
    data["history"].insert(0, pos)
    data["active"] = None
    _save(data)
    return pos


def update_barriers(stop_loss: float, take_profit: float) -> None:
    data = _load()
    if not data["active"]:
        raise ValueError("Aucune position active.")
    data["active"]["stop_loss"]  = stop_loss
    data["active"]["take_profit"] = take_profit
    _save(data)


def live_pnl(current_price: float) -> dict | None:
    pos = get_active()
    if not pos:
        return None
    avg = pos["average_price"]
    qty = pos["total_quantity"]
    lev = pos["leverage"]
    gross = (current_price - avg) * qty
    if pos["direction"] == "short":
        gross = -gross
    pnl_pct  = gross / (avg * qty) * 100 if avg else 0
    return {
        "gross_pnl":          gross,
        "pnl_pct":            pnl_pct,
        "leveraged_pnl_pct":  pnl_pct * lev,
    }
