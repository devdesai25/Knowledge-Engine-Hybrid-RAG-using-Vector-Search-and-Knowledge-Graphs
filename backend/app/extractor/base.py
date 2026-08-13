from abc import abstractmethod, ABC

class BaseExtractor(ABC):

    @abstractmethod
    async def extract(self, file):
        pass