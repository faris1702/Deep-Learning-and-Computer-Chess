from collections import namedtuple
from pathlib import Path
from collections import Counter
import chess.pgn
import re

PGN_DIR = Path(__file__).parent / "raw"
OUTPUT_PATH = "filtered" / "midgame_positions_fen.txt"  # Not in use
NUM_OF_GAMES = 200000    # Not in use
MIN_RATING = 2100
MAX_NUM_OF_GAMES = 100000
MAX_NUM_OF_POSITIONS = 200000    # maximum number of positions to extract from each game

# For Game Phase detection (Opening, Midgame, Endgame)
# Use Lichess thresholds
MAJORS_MINORS_ENDGAME_THRESHOLD = 6
MAJORS_MINORS_MIDGAME_THRESHOLD = 10
BACKRANK_SPARSE_THRESHOLD = 4
MIXEDNESS_THRESHOLD = 150

# 2x2 window (a1, b1, a2, b2) slid across the board to score mixedness
_MIXEDNESS_WINDOW = 0x0303

# ---------------- Game phase detection  --------------------
# Use Lichess algorithm, conditions and thresholds (open source in GitHub)

DividedBoard = namedtuple("DividedBoard", ["start", "middle", "end"])

# Major: Queen & Rook
# Minor: Bishop & Knight
def _majors_and_minors(board):
    non_king_pawn = board.occupied & ~(board.kings | board.pawns)
    return bin(non_king_pawn).count("1")


# The function counts how many pieces are in the back rank
def _backrank_sparse(board):
    white_backrank = bin(chess.BB_RANK_1 & board.occupied_co[chess.WHITE]).count("1")
    black_backrank = bin(chess.BB_RANK_8 & board.occupied_co[chess.BLACK]).count("1")
    return white_backrank < BACKRANK_SPARSE_THRESHOLD or black_backrank < BACKRANK_SPARSE_THRESHOLD

# Follow algorithm from LiChess 
def _mixedness_score(y, white, black):
    if white == 0:
        if black == 1:
            return 1 + y
        if black == 2:
            return 2 + (6 - y) if y < 6 else 0
        if black == 3:
            return 3 + (7 - y) if y < 7 else 0
        if black == 4:
            return 3 + (7 - y) if y < 7 else 0
        return 0
    if white == 1:
        if black == 0:
            return 1 + (8 - y)
        if black == 1:
            return 5 + abs(4 - y)
        if black == 2:
            return 4 + (7 - y)
        if black == 3:
            return 5 + (7 - y)
        return 0
    if white == 2:
        if black == 0:
            return 2 + (y - 2) if y > 2 else 0
        if black == 1:
            return 4 + (y - 1)
        if black == 2:
            return 7
        return 0
    if white == 3:
        if black == 0:
            return 3 + (y - 1) if y > 1 else 0
        if black == 1:
            return 5 + (y - 1)
        return 0
    if white == 4:
        if black == 0:
            return 3 + (y - 1) if y > 1 else 0
        return 0
    return 0

# Use a 2x2 window that iterates through the whole board
# From each iteration, will calculate the mixedness
def _mixedness(board):
    white_bb = board.occupied_co[chess.WHITE]
    black_bb = board.occupied_co[chess.BLACK]
    total = 0
    for y in range(7):
        for x in range(7):
            region = _MIXEDNESS_WINDOW << (x + 8 * y)
            white_count = bin(white_bb & region).count("1")
            black_count = bin(black_bb & region).count("1")
            total += _mixedness_score(y + 1, white_count, black_count)
    return total


# Endgame begins when there are <= 6 major/minor pieces
# King and Pawns excluded from count
def check_if_endgame(board):
    return _majors_and_minors(board) <= MAJORS_MINORS_ENDGAME_THRESHOLD


# Midgame has 3 conditions
# 1. Piece count: <= 10 major/minor pieces (exclude King and Pawns)
# 2. Back-Rank Sparseness: <= 4 pieces left in either back rank (includes King)
# 3. Board Mixedness: > 150
def check_if_midgame(board):
    return (
        _majors_and_minors(board) <= MAJORS_MINORS_MIDGAME_THRESHOLD
        or _backrank_sparse(board)
        or _mixedness(board) > MIXEDNESS_THRESHOLD
    )

# Not midgame or endgame
def check_if_opening(board):
    return not check_if_midgame(board) and not check_if_endgame(board)


# Scans one game's positions (FEN strings, in ply order) and returns 
# a named tuple of lists of opening, midgame and endgame
def divide_game(fens):
    boards = [chess.Board(fen) for fen in fens]
    opening = []
    midgame = []
    endgame = []

    for board in boards:
        if check_if_endgame(board):
            endgame.append(board.fen())
        elif check_if_midgame(board):
            midgame.append(board.fen())
        else:
            opening.append(board.fen())

    return DividedBoard(start=opening, middle=midgame, end=endgame)
# ----------------------------------------------------------------------------

# ------------------ Helper Functions to get event type ----------------------
_TOURNAMENT_URL_RE = re.compile(r"\s+https://\S+$")

def normalize_event(event):
    return _TOURNAMENT_URL_RE.sub("", event)

def count_event(event_counts, header):
    event = normalize_event(header)
    event_counts[event] += 1
    return event_counts
# ----------------------------------------------------------------------------

# Takes a pgn file and returns a 2D list
# It will be a list of games
# Each game will be a list of boards in FEN format
def filter_rating(pgn_file):
    total_count = 0
    game_count = 0
    filtered_count = 0
    event_counts = Counter()
    games = []

    while True:
        headers = chess.pgn.read_headers(pgn_file)
        if headers is None:  # headers == None: end of file
            break 

        total_count += 1
        white_elo = headers.get("WhiteElo")
        black_elo = headers.get("BlackElo")
        event = headers.get("Event", "Unknown")

        # Check if players rating is high
        if ((white_elo.isdigit()) and (black_elo.isdigit()) and 
            (int(white_elo) >= MIN_RATING) and (int(black_elo) >= MIN_RATING)):

            event_counts = count_event(event_counts, event)
            game_count += 1

            game = chess.pgn.read_game(pgn_file)
            boards = []
            # move_count = 1
            board = game.board()
            
            # print(f"Game {num_of_games}")
            # print(f"count: {total_count}, w_elo: {white_elo}, b_elo: {black_elo}, time_control: {time_control}")

            for move in game.mainline_moves():
                # print(f"{move_count}: {board.fen()}")  ## format to save the current position
                boards.append(board.fen())
                board.push(move)
                # filtered_count += 1
                # if (filtered_count % 50000 == 0):
                #     print(f"Extracted {filtered_count} rating filtered positions...")
                # move_count += 1
                # print(f"White:{board.occupied_co[chess.WHITE]}")
                # print(f"Black:{board.occupied_co[chess.BLACK]}")

            # Since push() called after print, need print 1 extra after loop     
            # print(f"{move_count}: {board.fen()}")
            # filtered_count += 1
            # move_count += 1
            boards.append(board.fen())  
            games.append(boards)

            if (game_count % 10000 == 0):
                print(f"Extracted {game_count} rating filtered games...")


        if game_count >= MAX_NUM_OF_GAMES:
            break

        # if filtered_count > (4 * MAX_NUM_OF_POSITIONS):
        #     break

    return games, event_counts

# Read raw pgn files stored in directory
# Extract midgame positions in FEN format
# Return a list of the positions in FEN format
def get_midgame_fen():
    midgame_boards = [] # Stores midgame positions in FEN format
    position_set = set()
    midgame_boards_count = 0
    duplicate_count = 0

    for pgn_file_path in PGN_DIR.iterdir():
        if pgn_file_path.is_file():
            if "2013" in str(pgn_file_path):  # skip file (FOR TESTING) #############################################################
                continue
            print(f"Reading {pgn_file_path}.....")

            # Read pgn file and get the midgame positions in FEN format
            with open(pgn_file_path) as pgn_file:
                print("Start") 
                games, event_counts = filter_rating(pgn_file)  # Get the games with high rating players
                game_count = len(games)

                for game in games:  # Iterate every game
                    divided_game = divide_game(game)

                    for item in divided_game.middle: # Iterate every midgame position
                        temp_str = item.split(' ')[0] + item.split(' ')[1] # position and turn (e.g. black's turn)
                        if temp_str in position_set:  # if position already exist
                            duplicate_count += 1
                            continue
                        else:
                            position_set.add(temp_str)
                        midgame_boards.append(item)
                        midgame_boards_count += 1

                        if midgame_boards_count % 100000 == 0:  # Check progress
                            print(f"Extracted {midgame_boards_count} midgame positions so far...")

                        # if midgame_boards_count >= MAX_NUM_OF_POSITIONS: # Enough sample collected
                        #     print()
                        #     for event, count in event_counts.most_common():
                        #         print(f"{event}: {count}")
                        #     print(f"Number of extracted games: {game_count}")
                        #     print(f"Number of midgame positions extracted: {MAX_NUM_OF_POSITIONS}")
                        #     return midgame_boards

    # If have not reach MAX_NUM_OF_POSITIONS but no more files to read
    print()
    for event, count in event_counts.most_common():
        print(f"{event}: {count}")
    print(f"Number of extracted games: {game_count}")
    print(f"Number of midgame positions extracted: {midgame_boards_count}")
    print(f"Number of duplicate positions removed: {duplicate_count}")
    return midgame_boards
                
def save_midgame_fen(midgame_boards):
    with open(OUTPUT_PATH, "w") as file:
        for fen in midgame_boards:
            file.write(fen)
            file.write("\n")
        print("File saved to midgame_positions_fen.txt")






def main():
    midgame_fens = get_midgame_fen()
    save_midgame_fen(midgame_fens)
                
    

if __name__ == "__main__":
    main()
                
