from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interdomain.ingestion.ripe_client import RipeRisClient
from interdomain.processing.normalize import normalize_bgp_event
from interdomain.storage.postgres import insert_events


def main():
    client = RipeRisClient()
    while True:
        try:
            print("Connecting to RIPE RIS Live...")
            client.connect()
            print("Connected. Streaming BGP updates...")
            for message in client.messages():
                rows = normalize_bgp_event(message)
                inserted = insert_events(rows)
                if inserted:
                    first = rows[0]
                    print(f"{first['observed_at'].isoformat()} {first['event_type']} {first['prefix']} peer_asn={first['peer_asn']} (+{inserted - 1} more)")
        except KeyboardInterrupt:
            print("\nStopping ingestion.")
            break
        except Exception as exc:
            print(f"Stream error: {exc}")
            print("Reconnecting in 5 seconds...")
            time.sleep(5)
        finally:
            client.close()


if __name__ == "__main__":
    main()
