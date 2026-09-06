from pathlib import Path

PGN_DIR = Path(__file__).parent / "raw"

for pgn_file_path in PGN_DIR.iterdir():
    if pgn_file_path.is_file():
        if "2013" in str(pgn_file_path):  # skip file (FOR TESTING) #############################################################
            continue
        print(f"Reading {pgn_file_path}.....")