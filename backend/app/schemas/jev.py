from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class JevChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: str
    criteria: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of choice keys to descriptions or definitions"
    )

class JevScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: str
    criteria: List[str] = Field(
        default_factory=list,
        description="Ordered list of rubric levels / scale labels"
    )

class JevNoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: str

class JevRequest(BaseModel):
    model: str
    state: Union[str, Dict[str, Any], List[Any]]
    questions: Dict[str, Any] = Field(
        description="Map of question IDs to their definitions (choice, score, or noul)"
    )

class JevChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    probabilities: Dict[str, float] = Field(default_factory=dict)
    confidence: Optional[float] = None

class JevScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: Union[int, float]
    probabilities: Dict[str, float] = Field(default_factory=dict)
    confidence: Optional[float] = None

class JevNoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    answer: bool
    probability: float

class JevUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

class JevResponse(BaseModel):
    id: str
    model: str
    answers: Dict[str, Any]
    usage: Optional[JevUsage] = None
    latency_ms: Optional[float] = None
