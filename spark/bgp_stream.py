import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    count,
    element_at,
    explode_outer,
    from_json,
    lit,
    size,
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
        StructField("next_hop", StringType(), True),
        StructField(
            "prefixes",
            ArrayType(StringType()),
            True,
        ),
    ]
)


bgp_schema = StructType(
    [
        StructField("timestamp", DoubleType(), True),
        StructField("peer", StringType(), True),
        StructField("peer_asn", StringType(), True),
        StructField("id", StringType(), True),
        StructField("host", StringType(), True),
        StructField("type", StringType(), True),
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
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    print("Interdomain Spark processor started")
    print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {KAFKA_TOPIC}")

    # 1. Read Kafka stream
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option(
            "kafka.bootstrap.servers",
            KAFKA_BOOTSTRAP_SERVERS,
        )
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
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
            col("timestamp").alias("kafka_timestamp"),
        )
        .select(
            timestamp_seconds(
                col("bgp.timestamp")
            ).alias("event_time"),
            col("bgp.peer"),
            col("bgp.peer_asn"),
            col("bgp.host"),
            col("bgp.path"),
            col("bgp.announcements"),
            col("bgp.withdrawals"),
            col("kafka_timestamp"),
        )
    )

    # 3. Turn announcements into individual route events
    announcements = (
        parsed
        .withColumn(
            "announcement",
            explode_outer(col("announcements")),
        )
        .withColumn(
            "prefix",
            explode_outer(col("announcement.prefixes")),
        )
        .filter(col("prefix").isNotNull())
        .select(
            "event_time",
            "peer",
            "peer_asn",
            "host",
            "prefix",
            lit("announcement").alias("event_type"),
            col("announcement.next_hop").alias("next_hop"),
            size(col("path")).alias("path_length"),
            element_at(
                col("path"),
                -1,
            ).alias("origin_asn"),
            "kafka_timestamp",
        )
    )

    # 4. Turn withdrawals into individual route events
    withdrawals = (
        parsed
        .withColumn(
            "prefix",
            explode_outer(col("withdrawals")),
        )
        .filter(col("prefix").isNotNull())
        .select(
            "event_time",
            "peer",
            "peer_asn",
            "host",
            "prefix",
            lit("withdrawal").alias("event_type"),
            lit(None).cast("string").alias("next_hop"),
            size(col("path")).alias("path_length"),
            element_at(
                col("path"),
                -1,
            ).alias("origin_asn"),
            "kafka_timestamp",
        )
    )

    # 5. Unified route-level stream
    route_events = announcements.unionByName(
        withdrawals
    )

    # 6. Detect route instability
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
            col("prefix"),
            col("peer_asn"),
        )
        .agg(
            count("*").alias("updates"),

            spark_sum(
                when(
                    col("event_type") == "announcement",
                    1,
                ).otherwise(0)
            ).alias("announcements"),

            spark_sum(
                when(
                    col("event_type") == "withdrawal",
                    1,
                ).otherwise(0)
            ).alias("withdrawals"),
        )
        .filter(
            col("updates") >= 10
        )
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            "prefix",
            "peer_asn",
            "updates",
            "announcements",
            "withdrawals",
        )
    )

    # 7. Print unstable routes every 10 seconds
    query = (
        instability.writeStream
        .format("console")
        .outputMode("update")
        .option("truncate", "false")
        .option("numRows", "30")
        .trigger(processingTime="10 seconds")
        .start()
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()