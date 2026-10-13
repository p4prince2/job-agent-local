"""Offline / Mock LLM Provider for rapid local development and automated CI testing."""

from typing import Any, Dict, List, Optional
from llm.base import LLMProvider


class MockProvider(LLMProvider):
    """Zero-dependency simulated LLM provider."""

    def __init__(self, model_name: str = "mock-agent-v1"):
        self.model_name = model_name

    def check_status(self) -> Dict[str, Any]:
        return {
            "online": True,
            "provider": "mock",
            "host": "in-memory",
            "model": self.model_name,
            "message": "Offline Mock Provider active (instant responses, zero dependencies)"
        }

    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False
    ) -> str:
        prompt_text = " ".join([m.get("content", "") for m in messages]).lower()

        # Handle Content Agent original post pipeline
        if "original post pipeline" in (system_prompt or "").lower():
            return """
### 1. LinkedIn Post
When building autonomous multi-agent systems, deterministic boundaries matter more than raw model scale.
In production architectures, safety gates and persistent state ensure reliable agent execution.

### 2. Expanded Medium Article
# Scaling Autonomous Engineering Teams with Deterministic Guardrails
Modern agentic workflows require combining generative reasoning with strict architectural safety boundaries.
By isolating human-in-the-loop gates from fast autonomous execution loops, developers maintain high throughput without compromising data integrity.

### 3. Condensed X (Twitter) Post
Autonomous agents without deterministic approval gates are a liability in prod. Build the safety queue first.

### 4. Cover Image Generation Prompt
Minimalist architectural diagram showing agent dispatch queues, state databases, and security gates in sleek neon lines.
"""

        # Handle Content Agent reply pipeline
        if "reply & comment pipeline" in (system_prompt or "").lower():
            return """
### Option 1 (Top Pick - Maximum Specificity)
In our benchmarking across vLLM and TensorRT-LLM, batch latency dropped 38% under high KV-cache utilization.

### Option 2 (Alternative Angle)
The primary bottleneck shifts to memory bandwidth once sequence lengths exceed 8k tokens.

### Option 3 (Brief / Counter-Intuitive Angle)
Speculative decoding reduces TTFT significantly for code generation workloads.
"""

        # Handle GitHub review
        if "github audit" in (system_prompt or "").lower():
            return """
### 1. Executive Summary & Health Score (9/10)
Clean repository structure adhering to modular software engineering patterns.

### 2. Architecture & File Organization
Well-organized separation between domain logic, data models, and web presentations.

### 3. Dependencies & Tooling
Modern lightweight dependencies with comprehensive environment configuration.

### 4. Testing & CI/CD Status
Automated unit tests covering critical path routing and security validation.

### 5. Priority Action Items
1. Maintain regular dependency updates.

### 6. Recommended Branch Name
`feat/architecture-optimization`
"""

        # Default fallback response
        return "Simulated LLM response for: " + prompt_text[:80]
