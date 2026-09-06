import re
from collections import Counter
from pathlib import Path

import chess.pgn

PGN_DIR = Path(__file__).parent / "raw"

# Tournament events embed a unique tournament URL, e.g.
# "Rated Blitz tournament https://lichess.org/tournament/6681yaru"
# Strip it so every tournament of a given type is counted together.
_TOURNAMENT_URL_RE = re.compile(r"\s+https://\S+$")


def normalize_event(event):
    return _TOURNAMENT_URL_RE.sub("", event)


def count_events(pgn_dir):
    event_counts = Counter()
    count = 0
    for pgn_file_path in pgn_dir.iterdir():
        if not pgn_file_path.is_file():
            continue
        with open(pgn_file_path) as pgn_file:
            while True:
                headers = chess.pgn.read_headers(pgn_file)
                if headers is None:  # reached end of file
                    break
                event = normalize_event(headers.get("Event", "Unknown"))
                event_counts[event] += 1
                count += 1
                if count % 1000000 == 0:
                    print(f"Number of checked matches: {count}")

    return event_counts


def main():
    event_counts = count_events(PGN_DIR)
    for event, count in event_counts.most_common():
        print(f"{event}: {count}")


if __name__ == "__main__":
    main()
