"""AI text processor for generating creative work summaries."""

import logging
import os
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class TextProcessor:
    """Generate creative work summaries using AI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5.1",
        max_tokens: int = 500,
        use_ai: bool = True,
    ):
        """
        Initialize text processor.
        """
        final_api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.use_ai = use_ai and final_api_key is not None

        if self.use_ai:
            try:
                self.client = self.client = OpenAI(
                    api_key=final_api_key,
                    max_retries=5,  # Let GPT handle rate-limit & server retries
                    timeout=30,
                )
                self.model = model
                self.max_tokens = max_tokens
                logger.info(
                    f"Initialized OpenAI client with model={model}, "
                    f"max_tokens={max_tokens}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize OpenAI client: {e}. Falling back."
                )
                self.use_ai = False
                self.client = None
        else:
            self.client = None
            if not final_api_key:
                logger.info("No API key—using simple text processing.")
            else:
                logger.info("AI summarization disabled—using simple text processing.")

    def generate_project_summary(self, project_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate creative work summary for a project."""

        logger.info(f"Generating summary for project {project_data.get('project_key')}")

        commit_messages = project_data.get("commit_messages", [])
        ticket_summaries = project_data.get("ticket_summaries", [])
        ticket_descriptions = project_data.get("ticket_descriptions", [])

        # Build input text
        all_text = []

        if ticket_summaries:
            all_text.append("Jira Ticket Summaries:")
            all_text.extend([f"- {s}" for s in ticket_summaries[:10]])

        if ticket_descriptions:
            all_text.append("\nJira Ticket Descriptions:")
            all_text.extend([f"- {d[:200]}" for d in ticket_descriptions[:5]])

        if commit_messages:
            all_text.append("\nCommit Messages:")
            all_text.extend([f"- {m[:150]}" for m in commit_messages[:20]])

        input_text = "\n".join(all_text)

        # If no text exists
        if not input_text.strip():
            return {
                "description": f"Work on {project_data.get('project_name', 'project')}",
                "creative_work_details": "Various development tasks and improvements.",
                "technical_summary": "No detailed information available.",
            }

        if not self.use_ai:
            return self._generate_simple_summary(
                project_data, commit_messages, ticket_summaries
            )

        # Build prompt with more context and examples
        project_name = project_data.get("project_name", "Unknown")
        metrics = project_data.get("metrics", {})
        total_commits = metrics.get("total_commits", len(commit_messages))
        total_tickets = len(ticket_summaries)

        prompt = f"""You are a technical writer creating professional summaries of software development work for a Creative Work Report.

PROJECT: {project_name}
STATISTICS: {total_commits} commits, {total_tickets} ticket(s)

WORK DETAILS:
{input_text}

TASK: Analyze the work above and create a professional summary with three sections:

1. DESCRIPTION: Write a concise, business-friendly description of what this project/work is about (1-2 sentences). Focus on the purpose and value of the work.

2. DETAILS: Describe the specific creative work accomplished (2-4 sentences). Be specific about features, improvements, fixes, or enhancements. Reference specific tickets or commits when relevant. Avoid generic phrases like "various improvements" - be concrete.

3. TECHNICAL: Provide a brief technical summary for internal tracking (1-2 sentences). Mention key technologies, patterns, or technical achievements.

IMPORTANT FORMATTING REQUIREMENTS:
- Start each section with exactly: "DESCRIPTION:", "DETAILS:", or "TECHNICAL:" (all caps, followed by colon)
- Write the content on the same line or following lines
- Be specific and concrete - avoid generic phrases
- Use professional, business-friendly language

Example format:
DESCRIPTION: [Your description here]
DETAILS: [Your details here]
TECHNICAL: [Your technical summary here]
"""

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                max_output_tokens=self.max_tokens,
            )

            content = response.output_text
            if not content:
                raise ValueError("Empty response from OpenAI API")

            logger.debug(f"AI response received (length: {len(content)} chars)")
            logger.debug(f"AI response preview: {content[:200]}...")

            summary = self._parse_summary_response(content)

            # Log if we got generic fallback values
            if (
                summary.get("creative_work_details")
                == "Various improvements and features were implemented."
            ):
                logger.warning(
                    f"Received generic summary for {project_name}. Raw response: {content[:500]}"
                )

            return summary

        except Exception as e:
            logger.error(f"AI request failed (fallback used): {e}")
            return self._generate_simple_summary(
                project_data, commit_messages, ticket_summaries
            )

    def _generate_simple_summary(self, project_data, commit_messages, ticket_summaries):
        """Fallback summary generator (non-AI)."""

        project_name = project_data.get("project_name", "project")

        if ticket_summaries:
            description = (
                f"Development work on {project_name}. {ticket_summaries[0][:100]}"
            )
        else:
            description = f"Development work on {project_name}"

        details_parts = []

        if ticket_summaries:
            details_parts.append(
                f"Completed {len(ticket_summaries)} ticket(s) including: {', '.join(ticket_summaries[:3])}"
            )

        if commit_messages:
            commit_types = {}
            for msg in commit_messages[:20]:
                msg_lower = msg.lower()
                if msg_lower.startswith("feat") or "feature" in msg_lower:
                    commit_types["features"] = commit_types.get("features", 0) + 1
                elif msg_lower.startswith("fix") or "bug" in msg_lower:
                    commit_types["fixes"] = commit_types.get("fixes", 0) + 1
                elif msg_lower.startswith("refactor"):
                    commit_types["refactoring"] = commit_types.get("refactoring", 0) + 1
                else:
                    commit_types["improvements"] = (
                        commit_types.get("improvements", 0) + 1
                    )

            if commit_types:
                type_desc = ", ".join(
                    [f"{count} {t}" for t, count in commit_types.items()]
                )
                details_parts.append(
                    f"Made {len(commit_messages)} commit(s) with {type_desc}."
                )

        creative_work_details = (
            ". ".join(details_parts)
            if details_parts
            else "Various development tasks and improvements were implemented."
        )

        metrics = project_data.get("metrics", {})
        total_commits = metrics.get("total_commits", len(commit_messages))
        total_tickets = len(ticket_summaries)

        technical_summary = f"Technical work included {total_commits} commit(s)"
        if total_tickets > 0:
            technical_summary += f" across {total_tickets} ticket(s)"
        technical_summary += "."

        return {
            "description": description[:200],
            "creative_work_details": creative_work_details[:500],
            "technical_summary": technical_summary,
        }

    def _parse_summary_response(self, content: str) -> Dict[str, str]:
        """Parse AI output into structured fields with improved robustness."""

        description = ""
        details = ""
        technical = ""

        # Normalize content - remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```"):
            # Remove markdown code blocks
            lines = content.split("\n")
            content = "\n".join([l for l in lines if not l.strip().startswith("```")])

        lines = content.split("\n")
        current = None
        buff = []

        def flush(section, buf):
            text = " ".join(buf).strip()
            if section == "description":
                return text, None, None
            if section == "details":
                return None, text, None
            if section == "technical":
                return None, None, text
            return None, None, None

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Check for section headers (case-insensitive, with or without colon)
            line_upper = stripped.upper()

            if line_upper.startswith("DESCRIPTION"):
                if current and buff:
                    d, dt, t = flush(current, buff)
                    if d:
                        description = d
                    if dt:
                        details = dt
                    if t:
                        technical = t
                current = "description"
                # Extract text after "DESCRIPTION:" or "DESCRIPTION"
                if ":" in stripped:
                    buff = [stripped.split(":", 1)[1].strip()]
                else:
                    buff = []
                continue

            if line_upper.startswith("DETAILS"):
                if current and buff:
                    d, dt, t = flush(current, buff)
                    if d:
                        description = d
                    if dt:
                        details = dt
                    if t:
                        technical = t
                current = "details"
                if ":" in stripped:
                    buff = [stripped.split(":", 1)[1].strip()]
                else:
                    buff = []
                continue

            if line_upper.startswith("TECHNICAL"):
                if current and buff:
                    d, dt, t = flush(current, buff)
                    if d:
                        description = d
                    if dt:
                        details = dt
                    if t:
                        technical = t
                current = "technical"
                if ":" in stripped:
                    buff = [stripped.split(":", 1)[1].strip()]
                else:
                    buff = []
                continue

            # If we're in a section, add the line to the buffer
            if current:
                buff.append(stripped)

        # Flush the last section
        if current and buff:
            d, dt, t = flush(current, buff)
            if d:
                description = d
            if dt:
                details = dt
            if t:
                technical = t

        # If parsing failed, try to extract from unstructured text
        if not description and not details and not technical:
            logger.warning(
                "Failed to parse structured response, attempting fallback extraction"
            )
            # Try to find any meaningful content
            all_text = content.strip()
            if len(all_text) > 50:  # If there's substantial content
                # Split by paragraphs and try to assign
                paragraphs = [p.strip() for p in all_text.split("\n\n") if p.strip()]
                if paragraphs:
                    description = paragraphs[0][:200] if len(paragraphs) >= 1 else ""
                    details = (
                        ". ".join(paragraphs[1:3])[:500] if len(paragraphs) >= 2 else ""
                    )
                    technical = paragraphs[-1][:200] if len(paragraphs) >= 1 else ""

        # Final validation - ensure we have meaningful content
        if description and len(description) < 20:
            description = ""  # Too short, likely not real content
        if details and len(details) < 20:
            details = ""  # Too short, likely not real content
        if technical and len(technical) < 10:
            technical = ""  # Too short, likely not real content

        return {
            "description": description or "Development work on project.",
            "creative_work_details": details
            or "Various improvements and features were implemented.",
            "technical_summary": technical or "Technical work completed.",
        }

    def normalize_text(self, text: str) -> str:
        """Normalize whitespace."""
        if not text:
            return ""
        return " ".join(text.split()).strip()
