COLLECTOR_REGIONS = {
    # Global / multihop
    "rrc00": "global",
    "rrc25": "global",

    # Europe
    "rrc01": "europe",
    "rrc03": "europe",
    "rrc04": "europe",
    "rrc05": "europe",
    "rrc07": "europe",
    "rrc10": "europe",
    "rrc12": "europe",
    "rrc13": "europe",
    "rrc18": "europe",
    "rrc20": "europe",
    "rrc21": "europe",
    "rrc22": "europe",

    # North America
    "rrc11": "north_america",
    "rrc14": "north_america",
    "rrc16": "north_america",

    # Latin America
    "rrc15": "latin_america",
    "rrc24": "latin_america",

    # Africa
    "rrc19": "africa",

    # Asia-Pacific
    "rrc06": "asia_pacific",
    "rrc23": "asia_pacific",

    # Middle East
    "rrc26": "middle_east",
}


def get_region(collector: str | None) -> str:
    if not collector:
        return "unknown"

    collector_id = collector.lower().split(".")[0]

    return COLLECTOR_REGIONS.get(
        collector_id,
        "unknown",
    )