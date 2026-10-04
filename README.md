# sudoku

A zero-dependency Sudoku solver, checker, and generator in pure Python. Standard library only — no install step, no dependencies.

## Features

- **Solve** any puzzle — backtracking with a minimum-remaining-values heuristic and bitmask candidates; even famously hard puzzles finish in milliseconds
- **Check** a puzzle — counts solutions to distinguish unique puzzles from ambiguous ones
- **Generate** puzzles by difficulty (`easy` / `medium` / `hard`) with a guaranteed-unique solution; deterministic with `--seed`
- Accepts input as an 81-character string, a pretty 9-line grid (pasted as-is), or stdin; `.`, `0`, and `_` all mean "empty"

Requires Python 3.10+.

## Usage

Solve a puzzle:

    python sudoku.py solve "530070000600195000098000060800060003400803001700020006060000280000419005000080079"

Solve from a file or pipe (same for `check`):

    python sudoku.py solve < puzzle.txt

Check a puzzle — prints e.g. `30 clues - unique solution.`:

    python sudoku.py check < puzzle.txt

Generate a hard puzzle, with its solution:

    python sudoku.py generate --difficulty hard --seed 42 --show-solution

Pretty grids can be pasted directly:

    python sudoku.py solve " 5 3 . | . 7 . | . . .
    6 . . | 1 9 5 | . . ."

## Tests

    python -m unittest test_sudoku.py -v

The suite covers parsing/rendering round-trips, known puzzles (including a famously hard one), solution counting cross-checked against an independent naive enumerator, generator sweeps across all difficulties and many seeds (uniqueness, determinism, distinctness), and the CLI end to end.

## License

MIT
