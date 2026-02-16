import psutil

from config import P_CORES

def estimate_spacy_params(texts: list[str], p_cores: int = P_CORES, model_size_gb: float = 0.5):
    """
    Estimate optimal n_process and batch_size for spaCy's nlp.pipe based on available system resources and text
    characteristics.

    :param texts: List of texts to be processed.
    :param p_cores: Number of performance CPU cores available.
    :param model_size_gb: Estimated size of the loaded spaCy model in GB.
    :return: Tuple of (n_process, batch_size).
    """
    n_process = max(1, p_cores - 1)
    available_ram_gb = psutil.virtual_memory().available / (1024 ** 3)
    usable_ram = max(1, available_ram_gb - (model_size_gb*n_process) - 2)  # Safety buffer: leave 2GB for the OS
    batch_size = int((usable_ram / n_process) * _density_factor(texts))

    return n_process, min(batch_size, 1024)  # Cap at 1024 to keep latency reasonable


def _density_factor(texts: list[str]):
    """Compute a density factor for texts to adjust batch sizes based on average text length."""
    avg_len = sum(len(t) for t in texts) / len(texts)
    return 150000 / avg_len