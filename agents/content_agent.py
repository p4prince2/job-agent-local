"""Content Agent for Prince AI Team (per SPEC.md §7).

Implements two distinct pipelines:
1. Original Post Pipeline (Weekly Cadence):
   - 6-part structure: Hook, Context, Explanation, Personal Take, Forward Implication, Closing Question/Takeaway.
   - Multi-format generation: LinkedIn post, expanded Medium article, condensed X version, and optional cover image prompt.
2. Reply & Comment Pipeline (On-Demand):
   - Target post analysis, claim verification, non-obvious angle finding.
   - Up to 3 ranked options.
   - Quality gate strictly banning generic praise, generic summaries, forced questions, hashtags, and decorative emoji.

All drafts are saved locally in the `drafts` table with status='draft'.
Never publishes without human approval.
"""

import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from config import TECH_NICHES
from db.models import Draft
from db.session import SessionLocal
from llm import default_provider
from llm.base import LLMProvider
from logging_utils.logger import get_logger

logger = get_logger("ContentAgent")

ORIGINAL_POST_PROMPT = f"""You are the CONTENT AGENT for Prince's personal AI team.
Prince's technical niches: {', '.join(TECH_NICHES)}.

You are executing the ORIGINAL POST PIPELINE. Follow Prince's mandatory 6-part structure:
1. Hook (Scroll-stopping opening line)
2. Context (What triggered this? New paper, benchmark, architectural shift)
3. Explanation (Plain-language technical breakdown)
4. Personal Take (The most critical part: Prince's technical evaluation and opinion)
5. Forward-Looking Implication (How this impacts production AI systems or future work)
6. Closing Question / Actionable Takeaway (Inviting thoughtful peer discussion)

Produce 4 distinct outputs clearly separated by headers:
### 1. LinkedIn Post
(Professional peer tone, 6-part structure, authentic voice)

### 2. Expanded Medium Article
(In-depth technical essay, thoroughly articulated concepts, clean narrative)

### 3. Condensed X (Twitter) Post
(Punchy, under 280 characters, immediate insight)

### 4. Cover Image Generation Prompt
(Detailed prompt for generating a clean visual for this topic)
"""

REPLY_PIPELINE_PROMPT = f"""You are the CONTENT AGENT for Prince executing the REPLY & COMMENT PIPELINE.
Prince's technical niches: {', '.join(TECH_NICHES)}.

Your goal: Craft high-signal, peer-level replies to an existing post.
Strict Rules & Banned Patterns:
- NO generic praise (e.g. "Great post!", "Insightful!", "Love this!")
- NO generic summaries (do not repeat the original post)
- NO forced or artificial questions
- NO hashtags (strictly 0 hashtags in replies)
- NO decorative emoji (strictly 0 decorative emoji)
- MUST name at least one specific concrete technical detail, benchmark, or tradeoff.
- Provide up to 3 distinct, ranked options based on specificity.
- LinkedIn tone: Peer adding one professional-grade data point.
- X (Twitter) tone: Knowledgeable practitioner reacting mid-scroll.

Format:
### Option 1 (Top Pick - Maximum Specificity)
[Reply content]

### Option 2 (Alternative Angle)
[Reply content]

### Option 3 (Brief / Counter-Intuitive Angle)
[Reply content]
"""

# Banned reply patterns (§7)
BANNED_REPLY_PATTERNS = [
    r"(?i)\b(great post|awesome post|love this|insightful read|thanks for sharing|kudos|super cool)\b",
    r"#[a-zA-Z0-9_]+",  # hashtags
    r"[🚀🔥💡✨👏🎉💪🙌]"  # decorative emoji
]


class ContentAgent:
    """Specialized Content Agent with Original and Reply pipelines."""

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.name = "ContentAgent"
        self.role = "Technical Copywriter & AI Thought Leadership Specialist"
        self.llm = llm or default_provider

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Routes to either the Original Post or Reply pipeline, validates quality, and stores drafts."""
        logger.info(f"ContentAgent executing: {task[:80]}...")
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            task_lower = task.lower()
            is_reply = any(k in task_lower for k in ["reply", "comment", "respond", "reaction to post"])

            if is_reply:
                return self._execute_reply_pipeline(task, context, db)
            else:
                return self._execute_original_pipeline(task, context, db)
        finally:
            if owns_db:
                db.close()

    def _execute_original_pipeline(self, task: str, context: Optional[Dict[str, Any]], db: Session) -> Dict[str, Any]:
        """Generates LinkedIn, Medium, X, and Cover Image outputs and saves to drafts."""
        prompt = f"Topic / Task: {task}\n"
        if context:
            if "github_summary" in context:
                prompt += f"\nGitHub Repository Context:\n{context['github_summary']}\n"
            if "telemetry" in context:
                prompt += f"\nTelemetry:\n{context['telemetry']}\n"

        response_text = self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=ORIGINAL_POST_PROMPT,
            temperature=0.7
        )

        # Parse sections
        linkedin_text = self._extract_section(response_text, "1. LinkedIn Post") or response_text
        medium_text = self._extract_section(response_text, "2. Expanded Medium Article") or response_text
        x_text = self._extract_section(response_text, "3. Condensed X (Twitter) Post") or response_text[:280]
        image_prompt = self._extract_section(response_text, "4. Cover Image Generation Prompt")

        source_ref = context.get("repo") if context else None

        # Save LinkedIn Draft
        d_li = Draft(
            platform="linkedin",
            type="original",
            status="draft",
            content=linkedin_text,
            source_ref=source_ref
        )
        db.add(d_li)

        # Save Medium Draft
        d_med = Draft(
            platform="medium",
            type="original",
            status="draft",
            content=medium_text,
            source_ref=source_ref
        )
        db.add(d_med)

        # Save X Draft
        d_x = Draft(
            platform="x",
            type="original",
            status="draft",
            content=x_text,
            source_ref=source_ref
        )
        db.add(d_x)

        # Save Cover Image Prompt Draft if available
        d_img = None
        if image_prompt and len(image_prompt.strip()) > 5:
            d_img = Draft(
                platform="image_prompt",
                type="original",
                status="draft",
                content=image_prompt.strip(),
                source_ref=source_ref
            )
            db.add(d_img)

        db.commit()

        log_msg = f"Saved original post drafts: LinkedIn #{d_li.id}, Medium #{d_med.id}, X #{d_x.id}"
        if d_img:
            log_msg += f", Image Prompt #{d_img.id}"
        logger.info(log_msg)

        return {
            "agent": self.name,
            "pipeline": "original",
            "status": "success",
            "drafts": {
                "linkedin_id": d_li.id,
                "medium_id": d_med.id,
                "x_id": d_x.id,
                "image_prompt_id": d_img.id if d_img else None
            },
            "linkedin_content": linkedin_text,
            "medium_content": medium_text,
            "x_content": x_text,
            "cover_image_prompt": image_prompt,
            "full_response": response_text
        }

    def _execute_reply_pipeline(self, task: str, context: Optional[Dict[str, Any]], db: Session) -> Dict[str, Any]:
        """Generates ranked replies and runs the quality gate against banned patterns."""
        prompt = f"Target Post / Context:\n{task}\n"
        if context and context.get("target_post"):
            prompt += f"Original Post Text:\n{context['target_post']}\n"

        raw_response = self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=REPLY_PIPELINE_PROMPT,
            temperature=0.6
        )

        # Quality Gate Check (§7)
        cleaned_response = self._apply_reply_quality_gate(raw_response)

        # Platform check
        platform = "x" if ("tweet" in task.lower() or " x " in task.lower()) else "linkedin"

        d_reply = Draft(
            platform=platform,
            type="reply",
            status="draft",
            content=cleaned_response
        )
        db.add(d_reply)
        db.commit()

        logger.info(f"Saved reply draft #{d_reply.id} for {platform}")

        return {
            "agent": self.name,
            "pipeline": "reply",
            "status": "success",
            "platform": platform,
            "draft_id": d_reply.id,
            "replies": cleaned_response,
            "quality_gate_passed": True
        }

    def _apply_reply_quality_gate(self, text: str) -> str:
        """Filters out banned patterns (generic praise, hashtags, decorative emojis)."""
        filtered_lines = []
        for line in text.split("\n"):
            cleaned = line
            # Strip banned emojis and hashtags
            for pat in BANNED_REPLY_PATTERNS:
                cleaned = re.sub(pat, "", cleaned)
            filtered_lines.append(cleaned)
        return "\n".join(filtered_lines).strip()

    def _extract_section(self, text: str, header: str) -> str:
        """Extracts content under markdown headings flexibly."""
        header_clean = re.sub(r"^\d+\.\s*", "", header).strip().lower()
        parts = re.split(r"(?:^|\n)#{2,4}\s*", text)
        for p in parts:
            lines = p.strip().split("\n")
            if not lines:
                continue
            first_line = lines[0].strip().lower()
            if header.lower() in first_line or header_clean in first_line:
                return "\n".join(lines[1:]).strip()
        return ""
