import subprocess
import json
import os
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
import chess
import chess.pgn
import io
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db.models import Setting


async def get_stockfish_settings(db: AsyncSession) -> Dict[str, Any]:
    """
    Fetch Stockfish configuration settings from the database.

    Args:
        db: Database session

    Returns:
        Dictionary with Stockfish settings
    """
    # Define default values
    defaults = {
        "stockfish_path": "/app/stockfish/stockfish_binary",
        "stockfish_threads": "4",
        "stockfish_hash": "512",
        "analysis_depth": "20",
        "analysis_time_ms": "1000"
    }

    # Fetch settings from database
    result = await db.execute(select(Setting))
    settings_rows = result.scalars().all()

    # Build settings dictionary
    settings = {}
    for row in settings_rows:
        settings[row.key] = row.value

    # Merge with defaults (use DB values if available, otherwise defaults)
    final_settings = {
        "stockfish_path": settings.get("stockfish_path", defaults["stockfish_path"]),
        "stockfish_threads": int(settings.get("stockfish_threads", defaults["stockfish_threads"])),
        "stockfish_hash": int(settings.get("stockfish_hash", defaults["stockfish_hash"])),
        "analysis_depth": int(settings.get("analysis_depth", defaults["analysis_depth"])),
        "analysis_time_ms": int(settings.get("analysis_time_ms", defaults["analysis_time_ms"]))
    }

    return final_settings


class StockfishAnalyzer:
    """
    Service for analyzing chess games using Stockfish engine.
    Handles UCI protocol communication and game analysis.
    """

    def __init__(
        self,
        stockfish_path: str = "/app/stockfish/stockfish_binary",
        threads: int = 4,
        hash_mb: int = 512,
        depth: int = 20,
        time_ms: int = 1000
    ):
        """
        Initialize Stockfish analyzer.

        Args:
            stockfish_path: Path to Stockfish binary
            threads: Number of CPU threads to use
            hash_mb: Hash table size in MB
            depth: Search depth
            time_ms: Time per move in milliseconds
        """
        self.stockfish_path = stockfish_path
        self.threads = threads
        self.hash_mb = hash_mb
        self.depth = depth
        self.time_ms = time_ms
        self.process: Optional[subprocess.Popen] = None

    def start_engine(self):
        """Start the Stockfish engine process."""
        if self.process is not None:
            return  # Already running

        try:
            self.process = subprocess.Popen(
                [self.stockfish_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Initialize UCI
            self._send_command("uci")
            self._wait_for_response("uciok")

            # Configure engine
            self._send_command(f"setoption name Threads value {self.threads}")
            self._send_command(f"setoption name Hash value {self.hash_mb}")
            self._send_command("isready")
            self._wait_for_response("readyok")

        except Exception as e:
            raise RuntimeError(f"Failed to start Stockfish: {str(e)}")

    def stop_engine(self):
        """Stop the Stockfish engine process."""
        if self.process:
            try:
                self._send_command("quit")
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            finally:
                self.process = None

    def _send_command(self, command: str):
        """Send a command to Stockfish."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Stockfish process not running")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def _read_line(self) -> str:
        """Read a line from Stockfish output."""
        if not self.process or not self.process.stdout:
            raise RuntimeError("Stockfish process not running")
        return self.process.stdout.readline().strip()

    def _wait_for_response(self, expected: str, timeout: int = 30):
        """Wait for a specific response from Stockfish."""
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            line = self._read_line()
            if expected in line:
                return line
        raise TimeoutError(f"Timeout waiting for '{expected}'")

    def analyze_position(self, fen: str) -> Dict[str, Any]:
        """
        Analyze a single position.

        Args:
            fen: Position in FEN notation

        Returns:
            Dictionary with analysis results
        """
        try:
            # Set position
            self._send_command(f"position fen {fen}")

            # Start analysis
            self._send_command(f"go depth {self.depth} movetime {self.time_ms}")

            # Read analysis output
            best_move = None
            score_cp = None
            score_mate = None
            pv = []

            while True:
                line = self._read_line()

                if line.startswith("bestmove"):
                    parts = line.split()
                    if len(parts) >= 2:
                        best_move = parts[1]
                    break

                if "score cp" in line:
                    # Extract centipawn score
                    parts = line.split()
                    try:
                        cp_index = parts.index("cp") + 1
                        score_cp = int(parts[cp_index])
                    except (ValueError, IndexError):
                        pass

                if "score mate" in line:
                    # Extract mate score
                    parts = line.split()
                    try:
                        mate_index = parts.index("mate") + 1
                        score_mate = int(parts[mate_index])
                    except (ValueError, IndexError):
                        pass

                if " pv " in line:
                    # Extract principal variation
                    parts = line.split()
                    try:
                        pv_index = parts.index("pv") + 1
                        pv = parts[pv_index:]
                    except (ValueError, IndexError):
                        pass

            # Build result
            result = {
                "fen": fen,
                "best_move": best_move,
                "pv": pv[:5] if pv else []  # First 5 moves of principal variation
            }

            # Add score
            if score_mate is not None:
                result["score"] = f"M{score_mate}"
                result["score_type"] = "mate"
                result["score_value"] = score_mate
            elif score_cp is not None:
                result["score"] = f"{score_cp / 100:.2f}"
                result["score_type"] = "cp"
                result["score_value"] = score_cp
            else:
                result["score"] = "0.00"
                result["score_type"] = "cp"
                result["score_value"] = 0

            return result

        except Exception as e:
            return {
                "fen": fen,
                "error": str(e),
                "best_move": None,
                "score": "0.00",
                "score_type": "error",
                "score_value": 0,
                "pv": []
            }

    def analyze_game(self, pgn_text: str) -> Dict[str, Any]:
        """
        Analyze a complete game from PGN.

        Args:
            pgn_text: Game in PGN format

        Returns:
            Dictionary with complete game analysis
        """
        try:
            # Parse PGN
            pgn_io = io.StringIO(pgn_text)
            game = chess.pgn.read_game(pgn_io)

            if not game:
                raise ValueError("Invalid PGN - could not parse game")

            # Extract game metadata
            white_player = game.headers.get("White", "Unknown")
            black_player = game.headers.get("Black", "Unknown")
            result = game.headers.get("Result", "*")
            date = game.headers.get("Date", "????.??.??")

            # Analyze each position
            board = game.board()
            move_analysis = []
            move_number = 1

            for move in game.mainline_moves():
                # Get current position before move
                fen = board.fen()

                # Analyze position
                analysis = self.analyze_position(fen)

                # Add move information
                move_data = {
                    "move_number": move_number,
                    "move": board.san(move),  # Move in algebraic notation
                    "uci": move.uci(),  # Move in UCI format
                    "fen_before": fen,
                    "analysis": analysis
                }

                # Make the move
                board.push(move)
                move_data["fen_after"] = board.fen()

                move_analysis.append(move_data)
                move_number += 1

            # Build complete analysis
            analysis_result = {
                "game_info": {
                    "white": white_player,
                    "black": black_player,
                    "result": result,
                    "date": date
                },
                "analysis_settings": {
                    "depth": self.depth,
                    "time_ms": self.time_ms,
                    "threads": self.threads,
                    "hash_mb": self.hash_mb
                },
                "moves": move_analysis,
                "total_moves": len(move_analysis),
                "final_fen": board.fen()
            }

            return analysis_result

        except Exception as e:
            raise RuntimeError(f"Failed to analyze game: {str(e)}")


async def analyze_game_async(
    game_id: int,
    pgn_text: str,
    db: AsyncSession,
    data_dir: str = "/app/data"
) -> Dict[str, Any]:
    """
    Asynchronously analyze a game and save results to JSON file.
    Fetches Stockfish settings from the database.

    Args:
        game_id: Database ID of the game
        pgn_text: Game in PGN format
        db: Database session to fetch settings
        data_dir: Directory to save analysis results

    Returns:
        Dictionary with analysis results and file path
    """
    # Create analysis directory if it doesn't exist
    analysis_dir = Path(data_dir) / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    # Fetch settings from database
    settings = await get_stockfish_settings(db)

    # Run analysis in thread pool to avoid blocking
    def run_analysis():
        analyzer = StockfishAnalyzer(
            stockfish_path=settings["stockfish_path"],
            threads=settings["stockfish_threads"],
            hash_mb=settings["stockfish_hash"],
            depth=settings["analysis_depth"],
            time_ms=settings["analysis_time_ms"]
        )

        try:
            analyzer.start_engine()
            result = analyzer.analyze_game(pgn_text)
            return result
        finally:
            analyzer.stop_engine()

    # Run in thread pool
    loop = asyncio.get_event_loop()
    analysis_result = await loop.run_in_executor(None, run_analysis)

    # Save to JSON file
    json_path = analysis_dir / f"{game_id}.json"
    with open(json_path, 'w') as f:
        json.dump(analysis_result, f, indent=2)

    return {
        "game_id": game_id,
        "analysis_file": str(json_path),
        "total_moves": analysis_result.get("total_moves", 0),
        "success": True
    }


def get_game_analysis(game_id: int, data_dir: str = "/app/data") -> Optional[Dict[str, Any]]:
    """
    Load existing analysis from JSON file.

    Args:
        game_id: Database ID of the game
        data_dir: Directory where analysis files are stored

    Returns:
        Analysis dictionary if file exists, None otherwise
    """
    json_path = Path(data_dir) / "analysis" / f"{game_id}.json"

    if not json_path.exists():
        return None

    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading analysis for game {game_id}: {e}")
        return None


def has_game_analysis(game_id: int, data_dir: str = "/app/data") -> bool:
    """
    Check if analysis file exists for a game.

    Args:
        game_id: Database ID of the game
        data_dir: Directory where analysis files are stored

    Returns:
        True if analysis file exists, False otherwise
    """
    json_path = Path(data_dir) / "analysis" / f"{game_id}.json"
    return json_path.exists()
