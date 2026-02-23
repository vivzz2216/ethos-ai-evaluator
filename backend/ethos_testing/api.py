"""
Main API endpoints for ETHOS testing module.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .datasets import DatasetLoader
from .evaluator import EthicalEvaluator, LogicalEvaluator, TruthfulnessEvaluator
from .analyzer import CodeAnalyzer
from .models import AutomatedTestRequest, AutomatedTestResponse
from .local_model import get_model
from .reporting import (
    ensure_output_dir,
    build_io_log_entry,
    map_evaluator_to_five_dimensions,
    write_json,
    generate_text_report,
)
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/ethos", tags=["ETHOS Testing"])

code_analyzer = CodeAnalyzer()

# Lazily initialized to avoid heavy model/tokenizer downloads on module import.
_dataset_loader: Optional[DatasetLoader] = None
_ethical_evaluator: Optional[EthicalEvaluator] = None
_logical_evaluator: Optional[LogicalEvaluator] = None
_truthfulness_evaluator: Optional[TruthfulnessEvaluator] = None


def get_dataset_loader() -> DatasetLoader:
    global _dataset_loader
    if _dataset_loader is None:
        _dataset_loader = DatasetLoader("data")
    return _dataset_loader


def get_ethical_evaluator() -> EthicalEvaluator:
    global _ethical_evaluator
    if _ethical_evaluator is None:
        _ethical_evaluator = EthicalEvaluator()
    return _ethical_evaluator


def get_logical_evaluator() -> LogicalEvaluator:
    global _logical_evaluator
    if _logical_evaluator is None:
        _logical_evaluator = LogicalEvaluator()
    return _logical_evaluator


def get_truthfulness_evaluator() -> TruthfulnessEvaluator:
    global _truthfulness_evaluator
    if _truthfulness_evaluator is None:
        _truthfulness_evaluator = TruthfulnessEvaluator()
    return _truthfulness_evaluator

# Request/Response Models
class TestRequest(BaseModel):
    responses: Optional[List[str]] = Field(None, description="List of responses to evaluate (optional, will use local model if not provided)")
    max_samples: Optional[int] = Field(20, description="Maximum number of samples to evaluate")
    model_name: Optional[str] = Field(None, description="Hugging Face model name to use for generation (e.g., 'sshleifer/tiny-gpt2')")

class EvaluationMetrics(BaseModel):
    alignment: Optional[float] = Field(None, description="Ethical alignment score")
    toxicity: Optional[float] = Field(None, description="Toxicity score")
    reasoning: Optional[float] = Field(None, description="Reasoning quality score")
    correctness: Optional[float] = Field(None, description="Logical correctness score")
    coherence: Optional[float] = Field(None, description="Coherence score")

class EvaluationResult(BaseModel):
    prompt_id: str
    prompt: str
    response: str
    expected_label: str
    category: str
    evaluation: Dict[str, Any]

class TestResponse(BaseModel):
    results: List[EvaluationResult]
    summary: Dict[str, Any]

class FullRunRequest(BaseModel):
    responses: Optional[List[str]] = Field(None, description="List of model responses (optional, will use local model if not provided)")
    max_samples: Optional[int] = Field(30, description="Number of prompts to evaluate (20-50 recommended)")
    model_name: Optional[str] = Field("UnknownModel", description="Model identifier for reporting")
    hf_model_name: Optional[str] = Field(None, description="Hugging Face model name to use for generation (e.g., 'sshleifer/tiny-gpt2')")
    output_dir: Optional[str] = Field("data", description="Directory to write artifacts to")

class FullRunResponse(BaseModel):
    message: str
    files: Dict[str, str]
    summary: Dict[str, Any]

@router.post("/test/automated", response_model=AutomatedTestResponse)
async def test_automated(request: AutomatedTestRequest):
    """
    Endpoint to automatically analyze code and generate test responses.
    
    Args:
        request: AutomatedTestRequest containing code to analyze
        
    Returns:
        AutomatedTestResponse containing generated responses and analysis
    """
    try:
        # Generate automated responses
        responses = code_analyzer.generate_test_responses(
            request.code,
            min(request.response_count, 5)
        )
        
        # Get detailed analysis
        analysis = code_analyzer.analyze_code(request.code)
        
        return {
            "responses": responses,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/test/ethical", response_model=TestResponse)
async def test_ethical(request: TestRequest):
    """
    Endpoint to test ethical alignment of AI model responses.

    Args:
        request: TestRequest containing responses to evaluate

    Returns:
        TestResponse containing evaluation results and summary
    """
    try:
        # Load ethical dataset
        dataset = get_dataset_loader().load_ethical_dataset(num_samples=request.max_samples)

        # Generate responses if not provided
        responses_input = request.responses or []
        if len(responses_input) == 0 and len(dataset) > 0:
            # Use local Hugging Face model to generate responses
            try:
                model = get_model(request.model_name or "sshleifer/tiny-gpt2")
                logger.info(f"Generating responses using model: {model.model_name}")
                responses_input = []
                for prompt_item in dataset:
                    prompt_text = prompt_item.get("prompt", "")
                    response = model.respond(prompt_text, max_new_tokens=100, temperature=0.7)
                    responses_input.append(response)
                logger.info(f"✅ Generated {len(responses_input)} responses using local model")
            except Exception as e:
                logger.warning(f"Failed to use local model, falling back to default: {e}")
                # Fallback to safe defaults
                safe_default = (
                    "I will not assist with harmful, discriminatory, or privacy-violating actions. "
                    "I aim to be fair, truthful, and respectful while prioritizing safety."
                )
                responses_input = [safe_default for _ in range(len(dataset))]

        # Allow flexible number of responses - use min of available responses and dataset size
        num_to_evaluate = min(len(responses_input), len(dataset))

        # Evaluate each response
        results = []
        for i in range(num_to_evaluate):
            prompt = dataset[i]
            response = responses_input[i]
            eval_result = get_ethical_evaluator().evaluate_response(prompt, response)
            results.append(EvaluationResult(
                prompt_id=prompt["id"],
                prompt=prompt["prompt"],
                response=response,
                expected_label=prompt.get("expected_label", prompt.get("expected_behavior", "Unknown")),
                category=prompt["category"],
                evaluation=eval_result
            ))

        # Calculate summary
        summary = _calculate_ethical_summary(results)

        return TestResponse(results=results, summary=summary)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test/ethical/full-run", response_model=FullRunResponse)
async def test_ethical_full_run(request: FullRunRequest):
    """
    Run ethical evaluation end-to-end and generate artifacts:
    - responses_log.json
    - ethics_scores.json
    - ethics_report.txt
    """
    try:
        # Load prompts
        dataset = get_dataset_loader().load_ethical_dataset(num_samples=request.max_samples or 30)
        
        # Generate responses if not provided
        responses_input = request.responses or []
        if len(responses_input) == 0 and len(dataset) > 0:
            # Use local Hugging Face model to generate responses
            try:
                model = get_model(request.hf_model_name or "sshleifer/tiny-gpt2")
                logger.info(f"Generating responses for full-run using model: {model.model_name}")
                responses_input = []
                for prompt_item in dataset:
                    prompt_text = prompt_item.get("prompt", "")
                    response = model.respond(prompt_text, max_new_tokens=100, temperature=0.7)
                    responses_input.append(response)
                logger.info(f"✅ Generated {len(responses_input)} responses using local model")
            except Exception as e:
                logger.warning(f"Failed to use local model, falling back to default: {e}")
                # Fallback to safe defaults
                safe_default = (
                    "I will not assist with harmful, discriminatory, or privacy-violating actions. "
                    "I aim to be fair, truthful, and respectful while prioritizing safety."
                )
                responses_input = [safe_default for _ in range(len(dataset))]
        
        num_to_eval = min(len(responses_input), len(dataset))

        # Evaluate and log
        io_logs: List[Dict[str, Any]] = []
        per_item_scores: List[Dict[str, Any]] = []
        eval_results: List[EvaluationResult] = []

        for i in range(num_to_eval):
            prompt = dataset[i]
            model_resp = responses_input[i]

            io_logs.append(build_io_log_entry(prompt, model_resp))

            eval_result = get_ethical_evaluator().evaluate_response(prompt, model_resp)
            eval_results.append(EvaluationResult(
                prompt_id=prompt["id"],
                prompt=prompt["prompt"],
                response=model_resp,
                expected_label=prompt.get("expected_label", prompt.get("expected_behavior", "Unknown")),
                category=prompt["category"],
                evaluation=eval_result,
            ))

            five_scores = map_evaluator_to_five_dimensions(eval_result)
            avg_score_0_5 = sum(five_scores.values()) / 5.0
            per_item_scores.append({
                "prompt_id": prompt["id"],
                "scores": five_scores,
                "average_score": round(avg_score_0_5, 3),
                "comments": eval_result.get("explanation", ""),
            })

        # Aggregate summary
        summary = _calculate_ethical_summary(eval_results)

        # Prepare outputs
        out_dir = ensure_output_dir(request.output_dir or "data")
        responses_log_path = os.path.join(out_dir, "responses_log.json")
        ethics_scores_path = os.path.join(out_dir, "ethics_scores.json")
        ethics_report_path = os.path.join(out_dir, "ethics_report.txt")

        # Write artifacts
        write_json(responses_log_path, io_logs)
        write_json(ethics_scores_path, per_item_scores)
        report_text = generate_text_report(
            model_name=request.model_name or "UnknownModel",
            test_date=datetime.utcnow().strftime("%d-%b-%Y"),
            prompts_tested=num_to_eval,
            per_item_scores=per_item_scores,
        )
        with open(ethics_report_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        return FullRunResponse(
            message="Ethical evaluation completed and artifacts generated.",
            files={
                "responses_log": responses_log_path,
                "ethics_scores": ethics_scores_path,
                "ethics_report": ethics_report_path,
            },
            summary=summary,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test/logical", response_model=TestResponse)
async def test_logical(request: TestRequest):
    """
    Endpoint to test logical reasoning capabilities of AI model responses.

    Args:
        request: TestRequest containing responses to evaluate

    Returns:
        TestResponse containing evaluation results and summary
    """
    try:
        # Load logical dataset
        dataset = get_dataset_loader().load_logical_dataset(num_samples=request.max_samples)
        responses_input = request.responses or []

        # Allow flexible number of responses - use min of available responses and dataset size
        num_to_evaluate = min(len(responses_input), len(dataset))

        # Evaluate each response
        results = []
        for i in range(num_to_evaluate):
            prompt = dataset[i]
            response = responses_input[i]
            eval_result = get_logical_evaluator().evaluate_response(prompt, response)
            results.append(EvaluationResult(
                prompt_id=prompt["id"],
                prompt=prompt["prompt"],
                response=response,
                expected_label=prompt["expected_label"],
                category=prompt["category"],
                evaluation=eval_result
            ))

        # Calculate summary
        summary = _calculate_logical_summary(results)

        return TestResponse(results=results, summary=summary)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/prompts/ethical")
async def get_ethical_prompts(max_samples: Optional[int] = 20):
    """Get ethical testing prompts without answers."""
    try:
        dataset = get_dataset_loader().load_ethical_dataset(num_samples=max_samples)
        return [{
            "id": item["id"],
            "category": item["category"],
            "prompt": item["prompt"]
        } for item in dataset]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test/truthfulness", response_model=TestResponse)
async def test_truthfulness(request: TestRequest):
    """
    Endpoint to test truthfulness of AI model responses.

    Args:
        request: TestRequest containing responses to evaluate

    Returns:
        TestResponse containing evaluation results and summary
    """
    try:
        # Load truthfulness dataset
        dataset = get_dataset_loader().load_truthfulness_dataset(num_samples=request.max_samples)

        # Generate responses if not provided
        responses_input = request.responses or []
        if len(responses_input) == 0 and len(dataset) > 0:
            try:
                model = get_model(request.model_name or "sshleifer/tiny-gpt2")
                logger.info(f"Generating truthfulness responses using model: {model.model_name}")
                responses_input = []
                for prompt_item in dataset:
                    prompt_text = prompt_item.get("prompt", "")
                    response = model.respond(prompt_text, max_new_tokens=64, temperature=0.3)
                    responses_input.append(response)
                logger.info(f"OK Generated {len(responses_input)} truthfulness responses using local model")
            except Exception as e:
                logger.warning(f"Failed to use local model for truthfulness, falling back to default: {e}")
                safe_default = "I don't have enough information to answer accurately."
                responses_input = [safe_default for _ in range(len(dataset))]

        # Allow flexible number of responses - use min of available responses and dataset size
        num_to_evaluate = min(len(responses_input), len(dataset))

        # Evaluate each response
        results = []
        for i in range(num_to_evaluate):
            prompt = dataset[i]
            response = responses_input[i]
            eval_result = get_truthfulness_evaluator().evaluate_response(prompt, response)
            results.append(EvaluationResult(
                prompt_id=prompt["id"],
                prompt=prompt["prompt"],
                response=response,
                expected_label=prompt["expected_label"],
                category=prompt["category"],
                evaluation=eval_result
            ))

        # Calculate summary
        summary = _calculate_truthfulness_summary(results)

        return TestResponse(results=results, summary=summary)

    except Exception as e:
        logger.error(f"Truthfulness test failed: {e}")
        return TestResponse(
            results=[],
            summary={
                "truthfulness_score": 0,
                "total_evaluated": 0,
                "truthful_responses": 0,
                "metrics": {
                    "factual_accuracy": 0,
                    "honesty": 0,
                    "transparency": 0,
                },
                "category_breakdown": {},
                "error": str(e),
            },
        )

@router.get("/prompts/logical")
async def get_logical_prompts(max_samples: Optional[int] = 20):
    """Get logical reasoning prompts without answers."""
    try:
        dataset = get_dataset_loader().load_logical_dataset(num_samples=max_samples)
        return [{
            "id": item["id"],
            "category": item["category"],
            "prompt": item["prompt"]
        } for item in dataset]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/prompts/truthfulness")
async def get_truthfulness_prompts(max_samples: Optional[int] = 20):
    """Get truthfulness testing prompts without answers."""
    try:
        dataset = get_dataset_loader().load_truthfulness_dataset(num_samples=max_samples)
        return [{
            "id": item["id"],
            "category": item["category"],
            "prompt": item["prompt"]
        } for item in dataset]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _calculate_ethical_summary(results: List[EvaluationResult]) -> Dict[str, Any]:
    """Calculate comprehensive summary metrics for ethical evaluation."""
    total = len(results)
    if total == 0:
        return {
            "ethical_alignment_score": 0,
            "total_evaluated": 0,
            "metrics": {
                "alignment": 0,
                "toxicity": 0,
                "reasoning": 0
            }
        }
    
    # Calculate average scores
    alignment_scores = [r.evaluation["metrics"]["alignment"] for r in results]
    toxicity_scores = [r.evaluation["metrics"]["toxicity"] for r in results]
    reasoning_scores = [r.evaluation["metrics"]["reasoning"] for r in results]
    
    return {
        "ethical_alignment_score": sum(r.evaluation["score"] for r in results) / total * 100,
        "total_evaluated": total,
        "aligned_responses": sum(1 for r in results if r.evaluation["aligned"]),
        "metrics": {
            "alignment": sum(alignment_scores) / total,
            "toxicity": sum(toxicity_scores) / total,
            "reasoning": sum(reasoning_scores) / total
        },
        "category_breakdown": _calculate_category_breakdown(results)
    }

def _calculate_logical_summary(results: List[EvaluationResult]) -> Dict[str, Any]:
    """Calculate comprehensive summary metrics for logical evaluation."""
    total = len(results)
    if total == 0:
        return {
            "logical_correctness_score": 0,
            "total_evaluated": 0,
            "metrics": {
                "correctness": 0,
                "reasoning": 0,
                "coherence": 0
            }
        }

    # Calculate average scores
    correctness_scores = [r.evaluation["metrics"]["correctness"] for r in results]
    reasoning_scores = [r.evaluation["metrics"]["reasoning"] for r in results]
    coherence_scores = [r.evaluation["metrics"]["coherence"] for r in results]

    return {
        "logical_correctness_score": sum(r.evaluation["score"] for r in results) / total * 100,
        "total_evaluated": total,
        "correct_responses": sum(1 for r in results if r.evaluation["correct"]),
        "metrics": {
            "correctness": sum(correctness_scores) / total,
            "reasoning": sum(reasoning_scores) / total,
            "coherence": sum(coherence_scores) / total
        },
        "category_breakdown": _calculate_category_breakdown(results)
    }

def _calculate_truthfulness_summary(results: List[EvaluationResult]) -> Dict[str, Any]:
    """Calculate comprehensive summary metrics for truthfulness evaluation."""
    total = len(results)
    if total == 0:
        return {
            "truthfulness_score": 0,
            "total_evaluated": 0,
            "metrics": {
                "factual_accuracy": 0,
                "honesty": 0,
                "transparency": 0
            }
        }

    # Calculate average scores
    factual_accuracy_scores = [r.evaluation["metrics"]["factual_accuracy"] for r in results]
    honesty_scores = [r.evaluation["metrics"]["honesty"] for r in results]
    transparency_scores = [r.evaluation["metrics"]["transparency"] for r in results]

    return {
        "truthfulness_score": sum(r.evaluation["score"] for r in results) / total * 100,
        "total_evaluated": total,
        "truthful_responses": sum(1 for r in results if r.evaluation["truthful"]),
        "metrics": {
            "factual_accuracy": sum(factual_accuracy_scores) / total,
            "honesty": sum(honesty_scores) / total,
            "transparency": sum(transparency_scores) / total
        },
        "category_breakdown": _calculate_category_breakdown(results)
    }

def _calculate_category_breakdown(results: List[EvaluationResult]) -> Dict[str, Dict[str, float]]:
    """Calculate performance breakdown by category."""
    categories = {}
    for result in results:
        category = result.category
        if category not in categories:
            categories[category] = {
                "count": 0,
                "score": 0
            }
        categories[category]["count"] += 1
        categories[category]["score"] += result.evaluation["score"]
    
    # Calculate averages
    for category in categories:
        categories[category]["score"] = (
            categories[category]["score"] / categories[category]["count"] * 100
        )
    
    return categories
