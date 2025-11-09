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
from math import exp


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

    @staticmethod
    def _expected_points_from_white_eval(score_type: str, score_value: int) -> float:
        """
        Convert engine evaluation (normalized to White perspective) into Expected Points for White.
        Mate scores saturate to 0 or 1. Centipawn scores use a logistic mapping.
        """
        # Handle mate: positive for White, negative for Black
        if score_type == "mate":
            return 1.0 if score_value > 0 else 0.0

        # Centipawns normalized for White: positive = White advantage
        # Convert to pawns
        pawns = score_value / 100.0
        # Logistic mapping: tweak k for sensible curve (about 0.55 per pawn)
        k = 0.55
        ep = 1.0 / (1.0 + exp(-k * pawns))
        # Clamp for safety
        if ep < 0.0:
            ep = 0.0
        if ep > 1.0:
            ep = 1.0
        return ep

    @staticmethod
    def _material_score_from_fen(fen: str, side: str) -> int:
        """
        Compute a simple material score for the given side ('w' or 'b') from a FEN.
        Piece values: P=1, N=3, B=3, R=5, Q=9, K=0
        """
        values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 0}
        board_part = fen.split()[0]
        score = 0
        for ch in board_part:
            if ch == '/' or ch.isdigit():
                continue
            if side == 'w' and ch.isupper():
                score += values.get(ch.lower(), 0)
            if side == 'b' and ch.islower():
                score += values.get(ch, 0)
        return score

    @staticmethod
    def _classify_move_from_ep_loss(ep_loss: float) -> str:
        """
        Classify move according to Expected Points loss thresholds.
        """
        # Best: exactly 0; allow tiny epsilon
        if ep_loss <= 0.005:
            return "Best"
        if ep_loss <= 0.02:
            return "Excellent"
        if ep_loss <= 0.05:
            return "Good"
        if ep_loss <= 0.10:
            return "Inaccuracy"
        if ep_loss <= 0.20:
            return "Mistake"
        return "Blunder"

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

            # Determine whose turn it is from FEN (to normalize score to White's perspective)
            # FEN format: "position w/b ..." where w=white to move, b=black to move
            fen_parts = fen.split()
            is_black_to_move = len(fen_parts) > 1 and fen_parts[1] == 'b'

            # Stockfish returns scores from side-to-move perspective
            # Normalize to always be from White's perspective:
            # - If White to move: keep score as-is
            # - If Black to move: negate score (so positive = white advantage, negative = black advantage)
            score_multiplier = -1 if is_black_to_move else 1

            # Add score
            if score_mate is not None:
                normalized_mate = score_mate * score_multiplier
                result["score"] = f"M{normalized_mate}"
                result["score_type"] = "mate"
                result["score_value"] = normalized_mate
            elif score_cp is not None:
                normalized_cp = score_cp * score_multiplier
                result["score"] = f"{normalized_cp / 100:.2f}"
                result["score_type"] = "cp"
                result["score_value"] = normalized_cp
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

            # Second pass: compute Expected Points and classifications per move
            total_moves = len(move_analysis)
            for i, md in enumerate(move_analysis):
                fen_before = md.get("fen_before")
                fen_after = md.get("fen_after")
                analysis_before = md.get("analysis", {})
                score_type_before = analysis_before.get("score_type", "cp")
                score_value_before = analysis_before.get("score_value", 0)

                # EP for White before this move
                ep_white_before = self._expected_points_from_white_eval(score_type_before, score_value_before)

                # EP for White after this move: use next move's analysis (which analyzes fen_after)
                if i + 1 < total_moves:
                    next_analysis = move_analysis[i + 1].get("analysis", {})
                    ep_white_after = self._expected_points_from_white_eval(
                        next_analysis.get("score_type", "cp"),
                        next_analysis.get("score_value", 0)
                    )
                else:
                    # Last move: derive from game result
                    if result == "1-0":
                        ep_white_after = 1.0
                    elif result == "0-1":
                        ep_white_after = 0.0
                    elif result == "1/2-1/2":
                        ep_white_after = 0.5
                    else:
                        # Unknown; assume unchanged
                        ep_white_after = ep_white_before

                # Determine who moved from FEN before
                side_to_move = fen_before.split()[1] if fen_before else ('w' if i % 2 == 0 else 'w')
                mover = side_to_move  # mover is side to move at fen_before

                # EP from mover perspective
                if mover == 'w':
                    ep_before = ep_white_before
                    ep_after = ep_white_after
                else:
                    ep_before = 1.0 - ep_white_before
                    ep_after = 1.0 - ep_white_after

                ep_loss = max(0.0, ep_before - ep_after)
                ep_gain = max(0.0, ep_after - ep_before)

                # Base classification
                classification = self._classify_move_from_ep_loss(ep_loss)

                # Special classifications
                special = None
                # Great Move: significantly improves outcome or flips evaluation to winning
                if ep_before <= 0.35 and ep_after >= 0.65 and ep_gain >= 0.20:
                    special = "Great Move"

                # Brilliant: a (material) sacrifice that yields/keeps a good outcome
                try:
                    mat_before = self._material_score_from_fen(fen_before, mover)
                    mat_after = self._material_score_from_fen(fen_after, mover)
                    mat_delta = mat_after - mat_before  # negative means sacrifice
                except Exception:
                    mat_delta = 0
                # Sacrifice at least a minor piece and position is not losing after
                if special is None and mat_delta <= -3 and ep_after >= 0.55 and ep_before <= 0.70:
                    special = "Brilliant"

                # Miss: failed to capitalize on strong position (beyond EP thresholds)
                if special is None and ep_before >= 0.65 and ep_after <= (ep_before - 0.10):
                    special = "Miss"

                md["expected_points"] = {
                    "mover_before": round(ep_before, 3),
                    "mover_after": round(ep_after, 3),
                    "white_before": round(ep_white_before, 3),
                    "white_after": round(ep_white_after, 3),
                    "loss": round(ep_loss, 3),
                    "gain": round(ep_gain, 3)
                }
                md["classification"] = classification
                if special:
                    md["special_classification"] = special

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
