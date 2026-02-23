from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .analyzer import CodeAnalyzer

class AutomatedTestRequest(BaseModel):
    code: str = Field(..., description="Python code to analyze")
    response_count: Optional[int] = Field(3, description="Number of responses to generate (max 5)")

class AutomatedTestResponse(BaseModel):
    responses: List[str]
    analysis: Dict[str, Any]