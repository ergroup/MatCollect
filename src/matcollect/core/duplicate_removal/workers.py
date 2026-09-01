"""Internal worker functions for duplicate removal to avoid pickling issues with multiprocessing."""  # noqa: E501

from pymatgen.analysis.structure_matcher import StructureMatcher

_worker_sm: StructureMatcher = None

def worker_init(tolerances: dict):
    """Initialize worker processes to set up a global StructureMatcher instance."""
    global _worker_sm  # noqa: PLW0603
    _worker_sm = StructureMatcher(**tolerances)

def check_pair_worker(args: tuple) -> tuple[int, int, bool]:
    """Check if a pair of structures are duplicates using the global StructureMatcher instance."""
    i, j, s1, s2 = args
    result = _worker_sm.fit(s1, s2)
    return i, j, result
