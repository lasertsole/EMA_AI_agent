import logging
from ..graph import Node
from datetime import datetime
from typing import Dict, Any, List
from .base_stage import BaseStage, StageOutput

logger = logging.getLogger("asr-got-stage1")

class InitializationStage(BaseStage):
    stage_name: str = "InitializationStage"

    def __init__(self):
        super().__init__()
        self.root_node_label = "Task Understanding"
        self.initial_confidence_values = [0.9, 0.9, 0.9, 0.9]
        self.initial_layer = "initial_layer"