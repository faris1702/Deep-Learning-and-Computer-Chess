import chess
import chess.engine
from pathlib import Path
import time

import threading
from concurrent.futures import ThreadPoolExecutor

STOCKFISH_PATH = "/home/fazli1702/faris-projects/FYP/stockfish/stockfish-ubuntu-x86-64-avx2"
# STOCKFISH_PATH = "/home/faris1702/stockfish/stockfish-ubuntu-x86-64-avx2"
DATASET_PATH = PGN_DIR = Path(__file__).parent / "dataset" / "filtered" / "midgame_positions_fen.txt"
LABELLED_DATA_PATH = Path(__file__).parent / "dataset" / "filtered" / "labelled_data.txt"
ENGINE_TIME_LIMIT = 0.1  # Seconds
NUM_WORKERS = 8          # max = 16 - 4 = 12 (for background processes)
BATCH_SIZE = 5000        # cap on in-flight futures, to bound memory on large datasets

categories = {"0":0, "1":0, "2":0, "3":0, "4":0, "5":0, "6":0}
categories_lock = threading.Lock()
file_lock = threading.Lock()

# Each worker thread gets its own Stockfish subprocess (engines aren't thread-safe)
thread_local = threading.local()
engines = []
engines_lock = threading.Lock()

def get_engine():
    if not hasattr(thread_local, "engine"):
        thread_local.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        with engines_lock:
            engines.append(thread_local.engine)
    return thread_local.engine

def write_to_file(file, fen, score, category):
    file.write(f"{fen.strip()},{category},{score}")
    file.write("\n")

def categorise_result(score):
    if score >= 500:    # white is winning
        return "0"
    elif score >= 300:  # white has an advantage
        return "1"
    elif score >= 100:  # white is better
        return "2"
    elif score >= -100: # position is equal
        return "3"
    elif score >= -300: # black is better
        return "4"
    elif score >= -500: # black has an advantage
        return "5"
    else:               # black is winning
        return "6"

def process_position(position_fen, labelled_file):
    engine = get_engine()
    board = chess.Board(position_fen)
    analysis = engine.analyse(board, chess.engine.Limit(depth=16))
    white_score = analysis["score"].white().score(mate_score=10000)  # black's score is the negative of white score (e.g. W:+25, B:-25) # set mate_score else will return None for forced mate position
    category = categorise_result(white_score)

    with categories_lock:
        categories[category] += 1
    with file_lock:
        write_to_file(labelled_file, position_fen, white_score, category)

print(f"Engine time: {ENGINE_TIME_LIMIT}s, workers: {NUM_WORKERS}")

def batched(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch

start = time.perf_counter()
i = 0
with open(DATASET_PATH) as file, open(LABELLED_DATA_PATH, "w") as labelled_file:
    lines = (line for line in file if line.strip())

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Submit in bounded batches so we never hold millions of futures in memory at once
        for batch in batched(lines, BATCH_SIZE):
            futures = [executor.submit(process_position, fen, labelled_file) for fen in batch]
            for future in futures:
                future.result()  # surfaces exceptions from worker threads
                i += 1
                if i % 5000 == 0: # To check progress of analysis
                    print(f"Labelled {i} positions so far ...")
        print(f"Total positions labelled: {i}")

end = time.perf_counter()
total_time = round(end - start)
total_min = total_time // 60
total_sec = total_time % 60

for cat, count in categories.items():
    print(f"Category {cat}: {count}")
print(f"Results saved to {LABELLED_DATA_PATH}")
print(f"Total time taken: {total_min}:{total_sec}")

for engine in engines:
    engine.quit()
