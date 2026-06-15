from abc import ABC, abstractmethod

class Register(ABC):
    @abstractmethod
    def session_end(self, session_id: str):
        pass