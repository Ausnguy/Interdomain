import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    coalesce,
    count,
    create_map,
    element_at,
    explode_outer,
    from_json,
    lit,
    lower,
    size,
    split,
    sum as spark_sum,
    timestamp_seconds,
    when,
    window,
)
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)


# Allow Spark to import code from src/interdomain
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from interdomain.processing.regions import COLLECTOR_REGIONS


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

KAFKA_TOPIC = os.getenv(
    "KAFKA_TOPIC",
    "bgp-updates",
)


announcement_schema = StructType(
    [
        StructField(
            "next_hop",
            StringType(),
            True,
        ),
        StructField(
            "prefixes",
            ArrayType(StringType()),
            True,
        ),
    ]
)


bgp_schema = StructType(
    [
        StructField(
            "timestamp",
            DoubleType(),
            True,
        ),
        StructField(
            "peer",
            StringType(),
            True,
        ),
        StructField(
            "peer_asn",
            StringType(),
            True,
        ),
        StructField(
            "id",
            StringType(),
            True,
        ),
        StructField(
            "host",
            StringType(),
            True,
        ),
        StructField(
            "type",
            StringType(),
            True,
        ),
        StructField(
            "path",
            ArrayType(LongType()),
            True,
        ),
        StructField(
            "announcements",
            ArrayType(announcement_schema),
            True,
        ),
        StructField(
            "withdrawals",
            ArrayType(StringType()),
            True,
        ),
    ]
)


def main():
    spark = (
        SparkSession.builder
        .appName("InterdomainBGPStream")
        .master("local[*]")
        .config(
            "spark.sql.shuffle.partitions",
            "4",
        )
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    print("Interdomain Spark processor started")
    print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {KAFKA_TOPIC}")

    # Build collector -> region mapping for Spark.
    #
    # Example:
    # rrc11 -> north_america
    # rrc23 -> asia_pacific
    region_values = []

    for collector, region in COLLECTOR_REGIONS.items():
        region_values.extend(
            [
                lit(collector),
                lit(region),
            ]
        )

    collector_region_map = create_map(
        *region_values
    )

    # 1. Read raw BGP messages from Kafka
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option(
            "kafka.bootstrap.servers",
            KAFKA_BOOTSTRAP_SERVERS,
        )
        .option(
            "subscribe",
            KAFKA_TOPIC,
        )
        .option(
            "startingOffsets",
            "latest",
        )
        .load()
    )

    # 2. Parse BGP JSON
    parsed = (
        raw_stream
        .select(
            from_json(
                col("value").cast("string"),
                bgp_schema,
            ).alias("bgp"),
            col("timestamp").alias(
                "kafka_timestamp"
            ),
        )
        .select(
            timestamp_seconds(
                col("bgp.timestamp")
            ).alias("event_time"),
            col("bgp.peer"),
            col("bgp.peer_asn"),
            col("bgp.host").alias(
                "collector"
            ),
            col("bgp.path"),
            col("bgp.announcements"),
            col("bgp.withdrawals"),
            col("kafka_timestamp"),
        )

        # RIPE sends values like:
        # rrc11.ripe.net
        .withColumn(
            "collector",
            lower(
                col("collector")
            ),
        )

        # Convert:
        # rrc11.ripe.net -> rrc11
        .withColumn(
            "collector_id",
            element_at(
                split(
                    col("collector"),
                    r"\.",
                ),
                1,
            ),
        )

        # Map:
        # rrc11 -> north_america
        .withColumn(
            "collector_region",
            coalesce(
                element_at(
                    collector_region_map,
                    col("collector_id"),
                ),
                lit("unknown"),
            ),
        )
    )

    # 3. Convert announcements into
    # individual route-level events
    announcements = (
        parsed
        .withColumn(
            "announcement",
            explode_outer(
                col("announcements")
            ),
        )
        .withColumn(
            "prefix",
            explode_outer(
                col(
                    "announcement.prefixes"
                )
            ),
        )
        .filter(
            col("prefix").isNotNull()
        )
        .select(
            "event_time",
            "peer",
            "peer_asn",
            "collector",
            "collector_region",
            "prefix",
            lit(
                "announcement"
            ).alias(
                "event_type"
            ),
            col(
                "announcement.next_hop"
            ).alias(
                "next_hop"
            ),
            size(
                col("path")
            ).alias(
                "path_length"
            ),
            element_at(
                col("path"),
                -1,
            ).alias(
                "origin_asn"
            ),
            "kafka_timestamp",
        )
    )

    # 4. Convert withdrawals into
    # individual route-level events
    withdrawals = (
        parsed
        .withColumn(
            "prefix",
            explode_outer(
                col("withdrawals")
            ),
        )
        .filter(
            col("prefix").isNotNull()
        )
        .select(
            "event_time",
            "peer",
            "peer_asn",
            "collector",
            "collector_region",
            "prefix",
            lit(
                "withdrawal"
            ).alias(
                "event_type"
            ),
            lit(
                None
            ).cast(
                "string"
            ).alias(
                "next_hop"
            ),
            size(
                col("path")
            ).alias(
                "path_length"
            ),
            element_at(
                col("path"),
                -1,
            ).alias(
                "origin_asn"
            ),
            "kafka_timestamp",
        )
    )

    # 5. Unified global route event stream
    route_events = (
        announcements
        .unionByName(
            withdrawals
        )
    )

    # 6. Detect route instability
    #
    # Grouping by collector prevents observations
    # from separate RIPE collectors from being
    # incorrectly merged together.
    instability = (
        route_events
        .withWatermark(
            "event_time",
            "2 minutes",
        )
        .groupBy(
            window(
                col("event_time"),
                "5 minutes",
                "1 minute",
            ),
            col("collector"),
            col("collector_region"),
            col("prefix"),
            col("peer_asn"),
        )
        .agg(
            count(
                "*"
            ).alias(
                "updates"
            ),

            spark_sum(
                when(
                    col(
                        "event_type"
                    )
                    == "announcement",
                    1,
                ).otherwise(
                    0
                )
            ).alias(
                "announcements"
            ),

            spark_sum(
                when(
                    col(
                        "event_type"
                    )
                    == "withdrawal",
                    1,
                ).otherwise(
                    0
                )
            ).alias(
                "withdrawals"
            ),
        )
        .filter(
            col("updates") >= 10
        )
        .select(
            col(
                "window.start"
            ).alias(
                "window_start"
            ),
            col(
                "window.end"
            ).alias(
                "window_end"
            ),
            "collector",
            "collector_region",
            "prefix",
            "peer_asn",
            "updates",
            "announcements",
            "withdrawals",
        )
    )

    # 7. Aggregate BGP activity by region
    regional_activity = (
        route_events
        .withWatermark(
            "event_time",
            "2 minutes",
        )
        .groupBy(
            window(
                col("event_time"),
                "1 minute",
            ),
            col(
                "collector_region"
            ),
        )
        .agg(
            count(
                "*"
            ).alias(
                "updates"
            ),

            spark_sum(
                when(
                    col(
                        "event_type"
                    )
                    == "announcement",
                    1,
                ).otherwise(
                    0
                )
            ).alias(
                "announcements"
            ),

            spark_sum(
                when(
                    col(
                        "event_type"
                    )
                    == "withdrawal",
                    1,
                ).otherwise(
                    0
                )
            ).alias(
                "withdrawals"
            ),
        )
        .select(
            col(
                "window.start"
            ).alias(
                "window_start"
            ),
            col(
                "window.end"
            ).alias(
                "window_end"
            ),
            "collector_region",
            "updates",
            "announcements",
            "withdrawals",
        )
    )

    # 8. Print unstable routes
    instability_query = (
        instability.writeStream
        .queryName(
            "route_instability"
        )
        .format(
            "console"
        )
        .outputMode(
            "update"
        )
        .option(
            "truncate",
            "false",
        )
        .option(
            "numRows",
            "30",
        )
        .trigger(
            processingTime="10 seconds"
        )
        .start()
    )

    # 9. Print regional activity
    regional_query = (
        regional_activity.writeStream
        .queryName(
            "regional_activity"
        )
        .format(
            "console"
        )
        .outputMode(
            "update"
        )
        .option(
            "truncate",
            "false",
        )
        .option(
            "numRows",
            "30",
        )
        .trigger(
            processingTime="10 seconds"
        )
        .start()
    )

    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()