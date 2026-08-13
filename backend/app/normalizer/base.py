from abc import ABC

class BaseNormalizer(ABC):

    @abstractmethod
    async def normalize(self, document):
        pass