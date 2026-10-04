#!/usr/bin/env python3
"""sudoku - a zero-dependency Sudoku solver, generator, and checker.

A tiny toolkit that can solve any puzzle, count solutions (to tell unique
puzzles from ambiguous ones), and generate fresh puzzles by difficulty with
a guaranteed-unique solution.

The solver uses backtracking with a minimum-remaining-values heuristic and
bitmask candidate sets, so even famously hard puzzles resolve in well under
a second of pure Python.

Usage:
    python sudoku.py solve "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
    python sudoku.py check < puzzle.txt
    python sudoku.py generate --difficulty hard --seed 42 --show-solution

Puzzles can be an 81-character string, a pretty 9-line grid (pasted as-is),
or piped via stdin. '.', '0', and '_' all mean "empty".

Standard library only. Requires Python 3.10+.
"""

from __future__ import annotations

import argparse
import random
import sys

CELLS = 81
ALL = 0b1111111110  # candidate bits for digits 1..9 (bit 0 unused)

EMPTY_CHARS = ".0_"
DIGIT_CHARS = "123456789"


def _build_peers_and_units():
    """Precompute, for every cell: its 20 peers and its 3 units (row/col/box)."""
    peers = []
    units = []
    for i in range(CELLS):
        r, c = divmod(i, 9)
        row = tuple(r * 9 + k for k in range(9))
        col = tuple(k * 9 + c for k in range(9))
        br, bc = (r // 3) * 3, (c // 3) * 3
        box = tuple((br + dr) * 9 + (bc + dc) for dr in range(3) for dc in range(3))
        units.append((row, col, box))
        peers.append(frozenset(set(row) | set(col) | set(box)) - {i})
    rows = tuple(tuple(range(r * 9, r * 9 + 9)) for r in range(9))
    cols = tuple(tuple(range(c, CELLS, 9)) for c in range(9))
    boxes = tuple(
        units[r * 9 + c][2] for r in (0, 3, 6) for c in (0, 3, 6)
    )
    return tuple(peers), tuple(units), rows + cols + boxes


PEERS, UNITS, ALL_UNITS = _build_peers_and_units()


# --------------------------------------------------------------------------
# Parsing and rendering
# --------------------------------------------------------------------------

def parse_board(text):
    """Parse a puzzle into a list of 81 ints (0 = empty).

    Accepts an 81-character string, a 9-line grid (separators such as
    '|', '+' and '-' and surrounding whitespace are ignored), or a
    sequence of 81 ints. Raises ValueError if the input does not contain
    exactly 81 cells.
    """
    if isinstance(text, (list, tuple)):
        if len(text) != CELLS:
            raise ValueError(f"expected {CELLS} cells, got {len(text)}")
        for v in text:
            if not isinstance(v, int) or not 0 <= v <= 9:
                raise ValueError(f"cell values must be integers in 0..9, got {v!r}")
        return list(text)
    if isinstance(text, str):
        chars = [ch for ch in text if ch in DIGIT_CHARS + EMPTY_CHARS]
        if len(chars) != CELLS:
            raise ValueError(
                f"expected {CELLS} cells, found {len(chars)} "
                "(characters other than 1-9, '.', '0', '_' are ignored)"
            )
        return [0 if ch in EMPTY_CHARS else int(ch) for ch in chars]
    raise TypeError("board must be a string, list, or tuple")


def board_to_line(board):
    """Render a board as a compact 81-character string ('.' for empty)."""
    return "".join(str(v) if v else "." for v in board)


def format_board(board):
    """Render a board as a human-friendly 9x9 grid with box separators."""
    lines = []
    for r in range(9):
        if r in (3, 6):
            lines.append("------+-------+------")
        cells = [
            str(board[r * 9 + c]) if board[r * 9 + c] else "." for c in range(9)
        ]
        lines.append(
            f" {cells[0]} {cells[1]} {cells[2]} | {cells[3]} {cells[4]} {cells[5]}"
            f" | {cells[6]} {cells[7]} {cells[8]}"
        )
    return "\n".join(lines)


def _as_board(board):
    """Normalize a board argument (string or sequence) to a list of 81 ints."""
    if isinstance(board, str):
        return parse_board(board)
    if isinstance(board, (list, tuple)):
        return parse_board(board)
    raise TypeError("board must be a string, list, or tuple")


# --------------------------------------------------------------------------
# Core solver
# --------------------------------------------------------------------------

def _initial_candidates(board):
    """Return (candidates, ok) for a board.

    candidates[i] holds the bitmask of allowed digits for empty cell i
    (0 for filled cells). ok is False when the givens are contradictory
    or some empty cell has no candidate at all.
    """
    rows = [0] * 9
    cols = [0] * 9
    boxes = [0] * 9
    for i, v in enumerate(board):
        if v:
            bit = 1 << v
            r, c = divmod(i, 9)
            bx = (r // 3) * 3 + c // 3
            if (rows[r] | cols[c] | boxes[bx]) & bit:
                return None, False
            rows[r] |= bit
            cols[c] |= bit
            boxes[bx] |= bit
    cand = [0] * CELLS
    for i in range(CELLS):
        if not board[i]:
            r, c = divmod(i, 9)
            bx = (r // 3) * 3 + c // 3
            mask = ALL & ~(rows[r] | cols[c] | boxes[bx])
            if not mask:
                return None, False
            cand[i] = mask
    return cand, True


def _iter_solutions(board):
    """Yield every solution of board (up to the caller's consumption)."""
    cand, ok = _initial_candidates(board)
    if not ok:
        return
    b0 = list(board)

    def rec(b, cand):
        best = -1
        best_mask = 0
        best_cnt = 10
        for i in range(CELLS):
            if b[i]:
                continue
            m = cand[i]
            if not m:
                return  # dead branch
            cnt = m.bit_count()
            if cnt < best_cnt:
                best_cnt = cnt
                best = i
                best_mask = m
                if cnt == 1:
                    break
        if best == -1:
            yield list(b)
            return
        m = best_mask
        while m:
            bit = m & -m
            m ^= bit
            b2 = list(b)
            c2 = list(cand)
            b2[best] = bit.bit_length() - 1
            dead = False
            for j in PEERS[best]:
                if not b2[j] and (c2[j] & bit):
                    c2[j] &= ~bit
                    if not c2[j]:
                        dead = True
                        break
            if not dead:
                yield from rec(b2, c2)

    yield from rec(b0, cand)


def solve(board):
    """Return one solution as a new list of 81 ints, or None if unsolvable.

    Accepts a string, list, or tuple; the input is never mutated.
    """
    for sol in _iter_solutions(_as_board(board)):
        return sol
    return None


def count_solutions(board, limit=2):
    """Count solutions, stopping at limit. Returns min(#solutions, limit).

    count_solutions(puzzle) == 1 means the puzzle has a unique solution;
    0 means unsolvable or contradictory; 2 means at least two solutions.
    """
    n = 0
    for _ in _iter_solutions(_as_board(board)):
        n += 1
        if n >= limit:
            break
    return n


def validate_solution(board):
    """True if board is a fully filled, constraint-valid grid."""
    try:
        b = _as_board(board)
    except (TypeError, ValueError):
        return False
    if any(v == 0 for v in b):
        return False
    for unit in ALL_UNITS:
        if sorted(b[i] for i in unit) != list(range(1, 10)):
            return False
    return True


# --------------------------------------------------------------------------
# Generator
# --------------------------------------------------------------------------

DIFFICULTY_TARGETS = {"easy": 40, "medium": 32, "hard": 26}


def _random_complete(rng):
    """Build a random fully solved grid."""

    def rec(b, cand):
        best = -1
        best_mask = 0
        best_cnt = 10
        for i in range(CELLS):
            if b[i]:
                continue
            m = cand[i]
            if not m:
                return None
            cnt = m.bit_count()
            if cnt < best_cnt:
                best_cnt = cnt
                best = i
                best_mask = m
                if cnt == 1:
                    break
        if best == -1:
            return b
        digits = []
        m = best_mask
        while m:
            bit = m & -m
            m ^= bit
            digits.append(bit.bit_length() - 1)
        rng.shuffle(digits)
        for d in digits:
            bit = 1 << d
            b2 = list(b)
            c2 = list(cand)
            b2[best] = d
            dead = False
            for j in PEERS[best]:
                if not b2[j] and (c2[j] & bit):
                    c2[j] &= ~bit
                    if not c2[j]:
                        dead = True
                        break
            if not dead:
                out = rec(b2, c2)
                if out is not None:
                    return out
        return None

    return rec([0] * CELLS, [ALL] * CELLS)


def generate(difficulty="medium", seed=None):
    """Generate a puzzle with a unique solution.

    Returns (puzzle, solution) as lists of 81 ints. Digging stops once the
    clue target for the difficulty is reached (hard targets may not always
    be reached; the result is still unique). Same seed = same puzzle.
    """
    if difficulty not in DIFFICULTY_TARGETS:
        raise ValueError(
            f"unknown difficulty {difficulty!r}; choose from "
            f"{', '.join(sorted(DIFFICULTY_TARGETS))}"
        )
    rng = random.Random(seed)
    full = _random_complete(rng)
    target = DIFFICULTY_TARGETS[difficulty]
    puzzle = list(full)
    clues = CELLS
    order = list(range(CELLS))
    rng.shuffle(order)
    for i in order:
        if clues <= target:
            break
        saved = puzzle[i]
        puzzle[i] = 0
        if count_solutions(puzzle, limit=2) == 1:
            clues -= 1
        else:
            puzzle[i] = saved
    return puzzle, full


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _read_puzzle(arg):
    if arg is not None:
        return parse_board(arg)
    return parse_board(sys.stdin.read())


def cmd_solve(args):
    try:
        board = _read_puzzle(args.puzzle)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    solution = solve(board)
    if solution is None:
        print("No solution.", file=sys.stderr)
        return 1
    print(board_to_line(solution) if args.compact else format_board(solution))
    return 0


def cmd_check(args):
    try:
        board = _read_puzzle(args.puzzle)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    clues = sum(1 for v in board if v)
    n = count_solutions(board, limit=2)
    if n == 0:
        status = "no solution (unsolvable or contradictory givens)"
    elif n == 1:
        status = "unique solution"
    else:
        status = "multiple solutions (at least 2)"
    print(f"{clues} clues - {status}.")
    if args.show_solution and n == 1:
        print(format_board(solve(board)))
    return 0


def cmd_generate(args):
    puzzle, solution = generate(args.difficulty, seed=args.seed)
    print(board_to_line(puzzle) if args.compact else format_board(puzzle))
    if args.show_solution:
        print()
        print(board_to_line(solution) if args.compact else format_board(solution))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="sudoku",
        description="Sudoku solver, checker, and generator. Zero dependencies.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("solve", help="solve a puzzle")
    sp.add_argument("puzzle", nargs="?", default=None,
                    help="81-cell string, 9-line grid, or stdin")
    sp.add_argument("--compact", action="store_true",
                    help="print an 81-character line instead of a grid")
    sp.set_defaults(func=cmd_solve)

    cp = sub.add_parser("check", help="validate a puzzle and count its solutions")
    cp.add_argument("puzzle", nargs="?", default=None)
    cp.add_argument("-s", "--show-solution", action="store_true",
                    help="print the solution when it is unique")
    cp.set_defaults(func=cmd_check)

    gp = sub.add_parser("generate", help="generate a unique-solution puzzle")
    gp.add_argument("-d", "--difficulty", choices=("easy", "medium", "hard"),
                    default="medium")
    gp.add_argument("--seed", type=int, default=None,
                    help="seed for deterministic generation")
    gp.add_argument("-s", "--show-solution", action="store_true")
    gp.add_argument("--compact", action="store_true",
                    help="print 81-character lines instead of grids")
    gp.set_defaults(func=cmd_generate)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
