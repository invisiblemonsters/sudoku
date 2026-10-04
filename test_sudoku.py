"""Tests for sudoku.py - run with:  python -m unittest test_sudoku.py -v"""

import random
import subprocess
import sys
import unittest
from pathlib import Path

from sudoku import (
    board_to_line,
    count_solutions,
    format_board,
    generate,
    parse_board,
    solve,
    validate_solution,
)

SCRIPT = Path(__file__).resolve().parent / "sudoku.py"
PY = sys.executable

WIKI = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
WIKI_SOLUTION = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
WIKI_GOLDEN = "\n".join([
    " 5 3 . | . 7 . | . . .",
    " 6 . . | 1 9 5 | . . .",
    " . 9 8 | . . . | . 6 .",
    "------+-------+------",
    " 8 . . | . 6 . | . . 3",
    " 4 . . | 8 . 3 | . . 1",
    " 7 . . | . 2 . | . . 6",
    "------+-------+------",
    " . 6 . | . . . | 2 8 .",
    " . . . | 4 1 9 | . . 5",
    " . . . | . 8 . | . 7 9",
])

# Arto Inkala's 2012 "world's hardest" puzzle.
INKALA = "800000000003600000070090200050007000000045700000100030001000068008500010090000400"

# A puzzle with exactly two solutions (four swapped cells form a deadly rectangle).
AMBIGUOUS = "8.25.31463468217591.54.6283289165437613742598457389612521937864738654921964218375"
AMBIGUOUS_SOLUTION_A = "872593146346821759195476283289165437613742598457389612521937864738654921964218375"
AMBIGUOUS_SOLUTION_B = "892573146346821759175496283289165437613742598457389612521937864738654921964218375"

# Locally consistent but unsolvable (a clue of a valid puzzle changed to a wrong digit).
UNSOLVABLE = ".795.3.4.3.68217..1..4.628.28.1..43...37..59.457.....252..3......86.4..19....8.75"

# Clue-count bands per difficulty for the generator sweep.
CLUE_BANDS = {"easy": (38, 42), "medium": (30, 34), "hard": (24, 28)}


def naive_count(board, limit=2):
    """Independent brute-force solution counter (no MRV, no bitmasks)."""
    if isinstance(board, str):
        board = parse_board(board)
    b = list(board)
    solutions = 0

    def rec():
        nonlocal solutions
        if solutions >= limit:
            return
        for i in range(81):
            if b[i] == 0:
                break
        else:
            solutions += 1
            return
        r, c = divmod(i, 9)
        used = set()
        for k in range(9):
            used.add(b[r * 9 + k])
            used.add(b[k * 9 + c])
        br, bc = (r // 3) * 3, (c // 3) * 3
        for dr in range(3):
            for dc in range(3):
                used.add(b[(br + dr) * 9 + bc + dc])
        for d in range(1, 10):
            if d not in used:
                b[i] = d
                rec()
                b[i] = 0

    rec()
    return solutions


class TestParseFormat(unittest.TestCase):
    def test_parse_compact_string(self):
        board = parse_board(WIKI)
        self.assertEqual(len(board), 81)
        self.assertEqual(sum(1 for v in board if v), 30)
        self.assertEqual(board[0], 5)
        self.assertEqual(board[9], 6)
        self.assertEqual(board[80], 9)
        self.assertEqual(board[2], 0)

    def test_parse_pretty_grid(self):
        self.assertEqual(parse_board(WIKI_GOLDEN), parse_board(WIKI))

    def test_parse_dots_zeros_underscores_equivalent(self):
        self.assertEqual(parse_board(WIKI.replace(".", "0")), parse_board(WIKI))
        self.assertEqual(parse_board(WIKI.replace(".", "_")), parse_board(WIKI))

    def test_parse_list(self):
        board = parse_board(list(range(9)) * 9)
        self.assertEqual(len(board), 81)
        self.assertRaises(ValueError, parse_board, [0] * 80)
        self.assertRaises(ValueError, parse_board, [0] * 82)
        self.assertRaises(ValueError, parse_board, [10] + [0] * 80)
        self.assertRaises(TypeError, parse_board, 123)

    def test_parse_wrong_length_raises(self):
        self.assertRaises(ValueError, parse_board, WIKI[:-1])
        self.assertRaises(ValueError, parse_board, WIKI + "5")

    def test_format_board_golden(self):
        self.assertEqual(format_board(parse_board(WIKI)), WIKI_GOLDEN)

    def test_render_roundtrip(self):
        board = parse_board(WIKI)
        self.assertEqual(parse_board(board_to_line(board)), board)
        self.assertEqual(parse_board(format_board(board)), board)


class TestSolve(unittest.TestCase):
    def test_wikipedia_puzzle(self):
        self.assertEqual(solve(WIKI), parse_board(WIKI_SOLUTION))

    def test_famous_hard_puzzle(self):
        board = parse_board(INKALA)
        solution = solve(board)
        self.assertIsNotNone(solution)
        self.assertTrue(validate_solution(solution))
        for given, digit in zip(board, solution):
            if given:
                self.assertEqual(given, digit)

    def test_complete_grid_is_returned(self):
        grid = parse_board(WIKI_SOLUTION)
        self.assertEqual(solve(grid), grid)

    def test_solve_accepts_string(self):
        self.assertEqual(solve(WIKI), solve(parse_board(WIKI)))

    def test_unsolvable_returns_none(self):
        self.assertIsNone(solve(UNSOLVABLE))

    def test_contradictory_givens_return_none(self):
        board = parse_board(WIKI)
        board[1] = 5  # two 5s in the first row
        self.assertIsNone(solve(board))

    def test_input_not_mutated(self):
        board = parse_board(WIKI)
        original = list(board)
        solve(board)
        count_solutions(board, 2)
        self.assertEqual(board, original)


class TestCountSolutions(unittest.TestCase):
    def test_unique_puzzle(self):
        self.assertEqual(count_solutions(WIKI, 2), 1)
        self.assertEqual(naive_count(WIKI, 2), 1)

    def test_ambiguous_puzzle(self):
        puzzle = parse_board(AMBIGUOUS)
        self.assertEqual(count_solutions(puzzle, 5), 2)
        self.assertEqual(naive_count(puzzle, 5), 2)
        sol_a = parse_board(AMBIGUOUS_SOLUTION_A)
        sol_b = parse_board(AMBIGUOUS_SOLUTION_B)
        for sol in (sol_a, sol_b):
            self.assertTrue(validate_solution(sol))
            for given, digit in zip(puzzle, sol):
                if given:
                    self.assertEqual(given, digit)
        diffs = [i for i in range(81) if sol_a[i] != sol_b[i]]
        self.assertEqual(len(diffs), 4)
        for i in diffs:
            self.assertEqual(puzzle[i], 0)
        self.assertIn(solve(puzzle), (sol_a, sol_b))

    def test_unsolvable(self):
        self.assertEqual(count_solutions(UNSOLVABLE, 2), 0)
        self.assertEqual(naive_count(UNSOLVABLE, 2), 0)

    def test_empty_board(self):
        self.assertEqual(count_solutions([0] * 81, 1), 1)
        self.assertEqual(count_solutions([0] * 81, 2), 2)

    def test_matches_naive_counter_on_near_complete_puzzles(self):
        # Random full grids with a few cells removed: both counters must agree.
        for seed in range(10):
            grid = generate("easy", seed=seed)[1]
            for holes in (3, 4, 5):
                rng = random.Random(seed * 100 + holes)
                puzzle = list(grid)
                for h in rng.sample(range(81), holes):
                    puzzle[h] = 0
                fast = count_solutions(puzzle, 4)
                self.assertEqual(fast, naive_count(puzzle, 4))


class TestGenerator(unittest.TestCase):
    def assert_consistent(self, puzzle, solution):
        self.assertTrue(validate_solution(solution))
        for given, digit in zip(puzzle, solution):
            if given:
                self.assertEqual(given, digit)

    def test_sweep_difficulties_and_seeds(self):
        for difficulty, (lo, hi) in CLUE_BANDS.items():
            for seed in range(30):
                with self.subTest(difficulty=difficulty, seed=seed):
                    puzzle, solution = generate(difficulty, seed=seed)
                    self.assertEqual(count_solutions(puzzle, 2), 1)
                    self.assertEqual(solve(puzzle), solution)
                    self.assert_consistent(puzzle, solution)
                    clues = sum(1 for v in puzzle if v)
                    self.assertTrue(
                        lo <= clues <= hi,
                        f"{clues} clues outside band [{lo}, {hi}]",
                    )

    def test_deterministic(self):
        self.assertEqual(generate("medium", seed=7), generate("medium", seed=7))
        generate("hard", seed=99)  # interleave an unrelated call
        self.assertEqual(generate("medium", seed=7), generate("medium", seed=7))

    def test_distinct_across_seeds(self):
        for difficulty in CLUE_BANDS:
            lines = {board_to_line(generate(difficulty, seed=s)[0]) for s in range(30)}
            self.assertEqual(len(lines), 30)

    def test_unknown_difficulty_raises(self):
        self.assertRaises(ValueError, generate, "extreme")


class TestCLI(unittest.TestCase):
    def run_cli(self, *args, **kwargs):
        return subprocess.run(
            [PY, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=str(SCRIPT.parent),
            **kwargs,
        )

    def test_solve_compact(self):
        result = self.run_cli("solve", "--compact", WIKI)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), WIKI_SOLUTION)

    def test_solve_from_stdin(self):
        result = self.run_cli("solve", "--compact", input=WIKI)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), WIKI_SOLUTION)

    def test_solve_pretty_grid_argument(self):
        result = self.run_cli("solve", "--compact", WIKI_GOLDEN)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), WIKI_SOLUTION)

    def test_solve_unsolvable_exits_1(self):
        result = self.run_cli("solve", UNSOLVABLE)
        self.assertEqual(result.returncode, 1)
        self.assertIn("No solution", result.stderr)

    def test_check_unique(self):
        result = self.run_cli("check", WIKI)
        self.assertEqual(result.returncode, 0)
        self.assertIn("30 clues", result.stdout)
        self.assertIn("unique solution", result.stdout)

    def test_check_multiple(self):
        result = self.run_cli("check", AMBIGUOUS)
        self.assertIn("multiple solutions", result.stdout)

    def test_check_no_solution(self):
        result = self.run_cli("check", UNSOLVABLE)
        self.assertIn("no solution", result.stdout)

    def test_generate_seeded(self):
        result = self.run_cli(
            "generate", "-d", "hard", "--seed", "0", "--compact", "-s"
        )
        self.assertEqual(result.returncode, 0)
        puzzle_line, _, solution_line = result.stdout.strip().partition("\n\n")
        self.assertEqual(puzzle_line, board_to_line(generate("hard", seed=0)[0]))
        self.assertEqual(solution_line.strip(), board_to_line(generate("hard", seed=0)[1]))
        self.assertEqual(count_solutions(parse_board(puzzle_line), 2), 1)


if __name__ == "__main__":
    unittest.main()
