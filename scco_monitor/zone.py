from .core import get_signal


def scan_transitions(rows: list[dict]) -> dict:
    if len(rows) < 2:
        return {"zone_history": [], "transitions": []}

    zones, transitions = [], []
    prev_zone = None

    for row in rows:
        date = row["date"]
        ratio = float(row["ratio"])
        price = float(row.get("scco_close", 0))
        z = get_signal(ratio)[0]

        zones.append((date, z, ratio, price))

        if prev_zone is not None and z != prev_zone:
            transitions.append((date, prev_zone, z, ratio, price))
        prev_zone = z

    return {"zone_history": zones, "transitions": transitions}
