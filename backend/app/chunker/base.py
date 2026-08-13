from abc import ABC, abstractmethod
from typing import Any

class BaseChunker(ABC):

    @abstractmethod
    def chunk(self, document: Any):
        pass