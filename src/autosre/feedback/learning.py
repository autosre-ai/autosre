"""
Learning Pipeline - Continuous learning from feedback.

Uses feedback to:
- Identify correction patterns
- Generate fine-tuning data
- Update runbooks
- Improve context
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from autosre.feedback.tracker import (
    FeedbackTracker,
    Feedback,
    IncidentOutcome,
    FeedbackType,
    OutcomeType,
)


class LearningPipeline:
    """
    Continuous learning from feedback.
    
    Processes feedback to improve agent performance.
    """
    
    def __init__(
        self,
        feedback_tracker: FeedbackTracker,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize learning pipeline.
        
        Args:
            feedback_tracker: Feedback tracker instance
            output_dir: Directory for output files
        """
        self.tracker = feedback_tracker
        
        if output_dir is None:
            output_dir = str(Path.home() / ".autosre" / "learning")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_training_data(self, output_file: Optional[str] = None) -> str:
        """
        Export training data in JSONL format.
        
        Generates training data from:
        - Corrections (what should have been said)
        - Successful analyses (thumbs up)
        
        Returns:
            Path to the output file
        """
        import sqlite3
        
        if output_file is None:
            output_file = str(self.output_dir / f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        
        training_examples = []
        
        # Get corrections
        with sqlite3.connect(self.tracker.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Corrections provide direct training signal
            corrections = conn.execute("""
                SELECT * FROM feedback 
                WHERE feedback_type = ? AND correction IS NOT NULL
            """, (FeedbackType.CORRECTION.value,)).fetchall()
            
            for row in corrections:
                if row["agent_analysis"] and row["correction"]:
                    training_examples.append({
                        "type": "correction",
                        "input": row["agent_analysis"],
                        "output": row["correction"],
                        "incident_id": row["incident_id"],
                    })
            
            # Thumbs up with analysis are positive examples
            positive = conn.execute("""
                SELECT f.*, o.root_cause_correct, o.outcome
                FROM feedback f
                LEFT JOIN outcomes o ON f.incident_id = o.incident_id
                WHERE f.feedback_type = ?
            """, (FeedbackType.THUMBS_UP.value,)).fetchall()
            
            for row in positive:
                if row["agent_analysis"]:
                    training_examples.append({
                        "type": "positive",
                        "analysis": row["agent_analysis"],
                        "rating": row["rating"],
                        "root_cause_correct": row["root_cause_correct"],
                        "incident_id": row["incident_id"],
                    })
        
        # Write JSONL
        with open(output_file, 'w') as f:
            for example in training_examples:
                f.write(json.dumps(example) + '\n')
        
        return output_file
    
    def identify_patterns(self) -> dict:
        """
        Identify patterns in feedback.
        
        Returns:
            Dict with identified patterns and recommendations
        """
        import sqlite3
        
        patterns = {
            "common_corrections": [],
            "failure_patterns": [],
            "success_patterns": [],
            "recommendations": [],
        }
        
        with sqlite3.connect(self.tracker.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Find services with most negative feedback
            problem_services = conn.execute("""
                SELECT 
                    incident_id,
                    COUNT(*) as negative_count
                FROM feedback 
                WHERE feedback_type = ?
                GROUP BY incident_id
                ORDER BY negative_count DESC
                LIMIT 5
            """, (FeedbackType.THUMBS_DOWN.value,)).fetchall()
            
            patterns["failure_patterns"] = [
                {"incident_id": row["incident_id"], "negative_count": row["negative_count"]}
                for row in problem_services
            ]
            
            # Find most common correction keywords
            corrections = conn.execute("""
                SELECT correction FROM feedback 
                WHERE feedback_type = ? AND correction IS NOT NULL
            """, (FeedbackType.CORRECTION.value,)).fetchall()
            
            # Simple keyword extraction
            keyword_counts = {}
            for row in corrections:
                words = row["correction"].lower().split()
                for word in words:
                    if len(word) > 4:  # Skip short words
                        keyword_counts[word] = keyword_counts.get(word, 0) + 1
            
            # Top keywords from corrections
            top_keywords = sorted(keyword_counts.items(), key=lambda x: -x[1])[:10]
            patterns["common_corrections"] = [
                {"keyword": k, "count": v} for k, v in top_keywords
            ]
            
            # Outcomes with high success rate
            success_outcomes = conn.execute("""
                SELECT 
                    outcome,
                    COUNT(*) as count,
                    AVG(root_cause_correct) as accuracy
                FROM outcomes
                GROUP BY outcome
                ORDER BY accuracy DESC
            """).fetchall()
            
            patterns["success_patterns"] = [
                {
                    "outcome": row["outcome"],
                    "count": row["count"],
                    "accuracy": row["accuracy"],
                }
                for row in success_outcomes
            ]
        
        # Generate recommendations
        summary = self.tracker.get_summary()
        
        if summary["outcomes"]["root_cause_accuracy"] < 0.7:
            patterns["recommendations"].append(
                "Root cause accuracy is below 70%. Consider improving context gathering."
            )
        
        if summary["outcomes"]["human_override_rate"] > 0.3:
            patterns["recommendations"].append(
                "Human override rate is above 30%. Review agent recommendations."
            )
        
        if summary["feedback"]["corrections"] > summary["feedback"]["thumbs_up"]:
            patterns["recommendations"].append(
                "More corrections than positive feedback. Agent may need retraining."
            )
        
        return patterns
    
    def generate_report(self) -> str:
        """
        Generate a learning report.
        
        Returns:
            Markdown formatted report
        """
        summary = self.tracker.get_summary()
        patterns = self.identify_patterns()
        
        report = f"""# AutoSRE Learning Report
Generated: {datetime.now().isoformat()}

## Feedback Summary

| Metric | Value |
|--------|-------|
| Total Feedback | {summary['feedback']['total']} |
| Thumbs Up | {summary['feedback']['thumbs_up']} |
| Thumbs Down | {summary['feedback']['thumbs_down']} |
| Corrections | {summary['feedback']['corrections']} |
| Approval Rate | {summary['feedback']['approval_rate']:.1%} |

## Outcome Summary

| Metric | Value |
|--------|-------|
| Total Outcomes | {summary['outcomes']['total']} |
| Root Cause Accuracy | {summary['outcomes']['root_cause_accuracy']:.1%} |
| Agent Helpful Rate | {summary['outcomes']['agent_helpful_rate']:.1%} |
| Human Override Rate | {summary['outcomes']['human_override_rate']:.1%} |
| Avg Time Saved | {summary['outcomes']['avg_time_saved_seconds']:.0f}s |

## Patterns

### Common Correction Keywords
"""
        
        for item in patterns["common_corrections"][:5]:
            report += f"- {item['keyword']}: {item['count']} occurrences\n"
        
        report += "\n### Success Patterns\n"
        for item in patterns["success_patterns"]:
            report += f"- {item['outcome']}: {item['count']} incidents, {item['accuracy']:.1%} accuracy\n"
        
        report += "\n## Recommendations\n\n"
        for rec in patterns["recommendations"]:
            report += f"- {rec}\n"
        
        if not patterns["recommendations"]:
            report += "No specific recommendations at this time.\n"
        
        return report
    
    def save_report(self, filename: Optional[str] = None) -> str:
        """
        Save learning report to file.
        
        Returns:
            Path to the saved report
        """
        if filename is None:
            filename = f"learning_report_{datetime.now().strftime('%Y%m%d')}.md"
        
        path = self.output_dir / filename
        report = self.generate_report()
        path.write_text(report)
        
        return str(path)
