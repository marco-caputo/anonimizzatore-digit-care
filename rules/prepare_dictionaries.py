from typing import List

def load_wordlist(path: str, lower:bool = True) -> List[str]:
    """Load a newline-separated file into a lowercase set."""
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return [line.strip().lower() if lower else line.strip() for line in f if line.strip()]