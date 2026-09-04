import hashlib
import os

CHUNK_SIZE = 64 * 1024  # 64 KB

def get_file_hash(file_path: str) -> str:
    """
    Computes a SHA-256 hash using the file size, first 64KB, and last 64KB.
    For small files (< 128KB), computes full file SHA-256.
    This guarantees constant-time hashing even for 1GB+ PDF files, preserving identity
    across renames and moves.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)
    hasher = hashlib.sha256()

    if file_size <= CHUNK_SIZE * 2:
        with open(file_path, "rb") as f:
            hasher.update(f.read())
    else:
        hasher.update(str(file_size).encode("utf-8"))
        with open(file_path, "rb") as f:
            # Read first chunk
            hasher.update(f.read(CHUNK_SIZE))
            # Read last chunk
            f.seek(file_size - CHUNK_SIZE)
            hasher.update(f.read(CHUNK_SIZE))

    return hasher.hexdigest()
