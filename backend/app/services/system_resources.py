import psutil
import os
from typing import Dict, Any, Tuple


def get_cpu_info() -> Dict[str, Any]:
    """
    Get CPU information including core counts and recommended threads.

    Returns:
        Dictionary with CPU information
    """
    physical_cores = psutil.cpu_count(logical=False) or 1
    logical_cores = psutil.cpu_count(logical=True) or 1

    # Recommend leaving 1-2 cores for system
    recommended_threads = max(1, logical_cores - 2)

    return {
        "physical_cores": physical_cores,
        "logical_cores": logical_cores,
        "recommended_threads": recommended_threads,
        "usage_percent": psutil.cpu_percent(interval=0.1)
    }


def get_memory_info() -> Dict[str, Any]:
    """
    Get memory information including total, available, and recommended hash size.

    Returns:
        Dictionary with memory information
    """
    memory = psutil.virtual_memory()

    total_mb = int(memory.total / (1024 * 1024))
    available_mb = int(memory.available / (1024 * 1024))
    used_mb = int(memory.used / (1024 * 1024))

    # Recommend 10-20% of available RAM for hash, capped at 2048 MB
    recommended_hash_mb = min(int(available_mb * 0.15), 2048)
    recommended_hash_mb = max(recommended_hash_mb, 128)  # Minimum 128 MB

    return {
        "total_mb": total_mb,
        "available_mb": available_mb,
        "used_mb": used_mb,
        "usage_percent": memory.percent,
        "recommended_hash_mb": recommended_hash_mb
    }


def validate_stockfish_path(path: str) -> Tuple[bool, str]:
    """
    Validate that the Stockfish binary path exists and is executable.

    Args:
        path: Path to the Stockfish binary

    Returns:
        Tuple of (is_valid, message)
    """
    if not path:
        return False, "Stockfish path is empty"

    if not os.path.exists(path):
        return False, f"Stockfish binary not found at: {path}"

    if not os.path.isfile(path):
        return False, f"Path is not a file: {path}"

    if not os.access(path, os.X_OK):
        return False, f"Stockfish binary is not executable: {path}"

    return True, "Stockfish binary is valid"


def get_stockfish_info(path: str) -> Dict[str, Any]:
    """
    Get information about the Stockfish binary.

    Args:
        path: Path to the Stockfish binary

    Returns:
        Dictionary with Stockfish information
    """
    is_valid, message = validate_stockfish_path(path)

    info = {
        "path": path,
        "exists": os.path.exists(path) if path else False,
        "is_file": os.path.isfile(path) if path and os.path.exists(path) else False,
        "executable": os.access(path, os.X_OK) if path and os.path.exists(path) else False,
        "valid": is_valid,
        "message": message
    }

    # Get file size if it exists
    if info["exists"] and info["is_file"]:
        try:
            size_bytes = os.path.getsize(path)
            info["size_mb"] = round(size_bytes / (1024 * 1024), 2)
        except Exception:
            info["size_mb"] = None

    return info


def get_system_resources(stockfish_path: str = None) -> Dict[str, Any]:
    """
    Get complete system resource information.

    Args:
        stockfish_path: Optional path to Stockfish binary to validate

    Returns:
        Dictionary with all system resource information
    """
    cpu_info = get_cpu_info()
    memory_info = get_memory_info()

    result = {
        "cpu": cpu_info,
        "memory": memory_info
    }

    # Add Stockfish info if path provided
    if stockfish_path:
        result["stockfish"] = get_stockfish_info(stockfish_path)

    return result


def validate_settings(settings: Dict[str, Any]) -> Tuple[bool, list]:
    """
    Validate Stockfish settings against system resources.

    Args:
        settings: Dictionary of settings to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Validate threads
    if "stockfish_threads" in settings:
        try:
            threads = int(settings["stockfish_threads"])
            logical_cores = psutil.cpu_count(logical=True) or 1

            if threads < 1:
                errors.append("Stockfish threads must be at least 1")
            elif threads > logical_cores:
                errors.append(
                    f"Stockfish threads ({threads}) exceeds available CPU cores ({logical_cores})"
                )
        except ValueError:
            errors.append("Stockfish threads must be a valid number")

    # Validate hash size
    if "stockfish_hash_mb" in settings:
        try:
            hash_mb = int(settings["stockfish_hash_mb"])
            memory = psutil.virtual_memory()
            available_mb = int(memory.available / (1024 * 1024))

            if hash_mb < 16:
                errors.append("Stockfish hash size must be at least 16 MB")
            elif hash_mb > available_mb:
                errors.append(
                    f"Stockfish hash size ({hash_mb} MB) exceeds available memory ({available_mb} MB)"
                )
            elif hash_mb > 8192:
                errors.append("Stockfish hash size should not exceed 8192 MB")
        except ValueError:
            errors.append("Stockfish hash size must be a valid number")

    # Validate Stockfish path
    if "stockfish_path" in settings:
        path = settings["stockfish_path"]
        is_valid, message = validate_stockfish_path(path)
        if not is_valid:
            errors.append(f"Stockfish path invalid: {message}")

    # Validate analysis depth
    if "analysis_depth" in settings:
        try:
            depth = int(settings["analysis_depth"])
            if depth < 1:
                errors.append("Analysis depth must be at least 1")
            elif depth > 50:
                errors.append("Analysis depth should not exceed 50 (very slow)")
        except ValueError:
            errors.append("Analysis depth must be a valid number")

    # Validate analysis time
    if "analysis_time_ms" in settings:
        try:
            time_ms = int(settings["analysis_time_ms"])
            if time_ms < 100:
                errors.append("Analysis time must be at least 100 ms")
            elif time_ms > 60000:
                errors.append("Analysis time should not exceed 60000 ms (1 minute)")
        except ValueError:
            errors.append("Analysis time must be a valid number")

    return len(errors) == 0, errors
