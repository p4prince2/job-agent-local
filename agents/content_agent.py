"""Content Agent for Prince AI Team.

Specialized in turning AI/ML engineering, LLMs, Agent architectures,
AI Safety, and MLOps projects into high-engagement LinkedIn and X posts.
Generates multiple hook variations and persists drafts locally in SQLite.
Never publishes without explicit human approval.
"""

import json
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent
from core.database import save_draft
from core.config import TECH_NICHES


CONTENT_AGENT_PROMPT = f"""You are the CONTENT AGENT for Prince's personal AI team.
Prince is an engineer and researcher working in:
{', '.join(TECH_NICHES)}.

Your core responsibilities:
1. Write and improve LinkedIn posts and X (Twitter) threads.
2. Turn complex AI/ML project work, benchmarks, and architecture decisions into engaging, technically accurate content.
3. Eliminate corporate fluff, generic AI buzzwords, and shallow summaries. Keep the tone authentic, direct, insightful, and practical.
4. Structure posts effectively:
   - Strong 1-2 line scroll-stopping hook.
   - Core problem / insight / technical breakdown.
   - Concrete takeaway or lesson learned.
   - Question or discussion starter for fellow AI practitioners.
5. Provide 3 distinct hook variations:
   - Hook A: Contrarian / Counter-intuitive observation
   - Hook B: Build-in-public / Behind-the-scenes engineering reality
   - Hook C: High-impact actionable takeaway
6. ALWAYS maintain the rule: Content is saved as a LOCAL DRAFT for Prince's review. Never publish automatically.

When given a topic or project notes, output your response clearly. Include the primary draft, the 3 hook variations, and recommended technical hashtags.
"""


class ContentAgent(BaseAgent):
    """Specialized Content Creation and Copywriting Agent."""

    def __init__(self):
        super().__init__(
            name="ContentAgent",
            role="Technical Content Creator & Copywriter",
            description="Writes high-engagement LinkedIn and X posts for AI/ML, LLMs, and Agent architectures.",
            system_prompt=CONTENT_AGENT_PROMPT
        )

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes content creation task, generates hooks, and saves draft locally."""
        self.log(f"Received content task: {task[:80]}...")

        # Determine target platform
        task_lower = task.lower()
        if "twitter" in task_lower or "x.com" in task_lower or "tweet" in task_lower:
            platform = "twitter_x"
        else:
            platform = "linkedin"

        # Combine task with any upstream context (e.g., GitHub review findings)
        prompt = f"Task: {task}\n"
        if context:
            if "github_summary" in context:
                prompt += f"\nRelevant GitHub Project Context:\n{context['github_summary']}\n"
            if "recommendations" in context:
                prompt += f"Key Improvements:\n{json.dumps(context['recommendations'])}\n"
            if "additional_notes" in context:
                prompt += f"Additional Notes:\n{context['additional_notes']}\n"

        prompt += f"""
Please generate:
1. Primary post draft for {platform.upper()}.
2. Three alternative hook variations.
3. 3-5 relevant technical tags ({', '.join(TECH_NICHES[:4])}).
Format your output with clear markdown headings:
### Primary Draft
### Hook Variations
### Tags
"""

        # Generate post using LLM
        response_text = self.call_llm(prompt, temperature=0.7)

        # Extract title / hook snippets
        title = f"Post: {task[:50]}"
        hooks = self._extract_hooks(response_text)
        tags = self._extract_tags(response_text)

        # Save draft locally to SQLite
        draft_id = save_draft(
            platform=platform,
            title=title,
            content=response_text,
            hook_variations=hooks,
            tags=tags
        )
        self.log(f"Saved local content draft #{draft_id} for {platform}.", level="INFO")

        return {
            "agent": self.name,
            "status": "success",
            "platform": platform,
            "draft_id": draft_id,
            "title": title,
            "content": response_text,
            "hooks": hooks,
            "tags": tags,
            "published": False,
            "note": f"Draft saved locally (ID: #{draft_id}). Ready for your review."
        }

    def _extract_hooks(self, text: str) -> List[str]:
        """Extracts hook bullet points if detected in output."""
        hooks = []
        in_hooks = False
        for line in text.split("\n"):
            if "### hook" in line.lower():
                in_hooks = True
                continue
            if in_hooks:
                if line.startswith("###"):
                    break
                cleaned = line.strip().lstrip("-*123456789. ")
                if cleaned and len(cleaned) > 10:
                    hooks.append(cleaned)
                    if len(hooks) >= 3:
                        break
        return hooks or [
            "Most AI teams focus on the wrong metric when deploying agents.",
            "Here is what happened when I restructured my AI pipeline.",
            "3 practical lessons from building agentic systems that actually work."
        ]

    def _extract_tags(self, text: str) -> str:
        """Extracts hashtags from text or provides relevant defaults."""
        tags = [word for word in text.split() if word.startswith("#")]
        if tags:
            return " ".join(tags[:6])
        return "#AI #MachineLearning #LLMs #AIAgents #MLOps"
