import requests
from typing import List, Dict, Any, Optional
import chess.pgn
from io import StringIO
from datetime import datetime


class ChessComAPI:
    """Service for interacting with Chess.com public API"""

    BASE_URL = "https://api.chess.com/pub"

    def __init__(self, username: str):
        self.username = username.lower()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Local Chess Analyzer/1.0'
        })

    def get_monthly_archives(self) -> List[str]:
        """
        Fetch list of monthly archive URLs for the user.
        Returns list of URLs like: https://api.chess.com/pub/player/{username}/games/2024/01
        """
        url = f"{self.BASE_URL}/player/{self.username}/games/archives"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('archives', [])
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch archives for {self.username}: {str(e)}")

    def get_games_from_archive(self, archive_url: str) -> List[Dict[str, Any]]:
        """
        Fetch all games from a specific monthly archive.
        Returns list of game objects from Chess.com API.
        """
        try:
            response = self.session.get(archive_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('games', [])
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch games from archive {archive_url}: {str(e)}")

    def get_all_games(self, limit_months: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch all games for the user across all monthly archives.

        Args:
            limit_months: If specified, only fetch games from the most recent N months

        Returns:
            List of game objects from Chess.com API
        """
        archives = self.get_monthly_archives()

        if limit_months:
            archives = archives[-limit_months:]

        all_games = []
        for archive_url in archives:
            games = self.get_games_from_archive(archive_url)
            all_games.extend(games)

        return all_games

    @staticmethod
    def extract_game_data(game: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant data from a Chess.com game object.

        Args:
            game: Raw game object from Chess.com API

        Returns:
            Dictionary with extracted game data
        """
        # Get PGN string
        pgn_text = game.get('pgn', '')

        # Parse PGN to extract metadata
        pgn_io = StringIO(pgn_text)
        chess_game = chess.pgn.read_game(pgn_io)

        # Extract players and result
        white_player = game.get('white', {}).get('username', 'Unknown')
        black_player = game.get('black', {}).get('username', 'Unknown')

        # Get game result
        result = chess_game.headers.get('Result', '*') if chess_game else '*'

        # Get game date from timestamp or headers
        game_timestamp = game.get('end_time')
        if game_timestamp:
            game_date = datetime.fromtimestamp(game_timestamp).strftime('%Y.%m.%d')
        else:
            game_date = chess_game.headers.get('Date', '') if chess_game else ''

        # Create unique Chess.com ID from URL
        game_url = game.get('url', '')
        chess_com_id = game_url.split('/')[-1] if game_url else f"{white_player}_{black_player}_{game_timestamp}"

        return {
            'chess_com_id': chess_com_id,
            'pgn': pgn_text,
            'white_player': white_player,
            'black_player': black_player,
            'result': result,
            'game_date': game_date,
            'url': game_url,
            'time_control': game.get('time_control', ''),
            'time_class': game.get('time_class', ''),
        }
