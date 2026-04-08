"""
node_classifier.py
=================
LLM-powered node-specific event classification with energy impact reasoning.

**MODEL USED**: gpt-4o-mini (OpenAI's fast and cost-effective model)

For each news article, classifies relevance to specific grid nodes (states):
- Uttar Pradesh (UP)
- Bihar (BHR)
- West Bengal (WB)
- Karnataka (KAR)

Provides:
- Relevance score (0.0-1.0)
- Energy impact prediction (+/- MW delta)
- Reasoning (why this affects the state)
- Semantic flags (load profile descriptors)

Cost: ~$0.01-0.02 per article with gpt-4o-mini
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

# Load .env from backend folder
from dotenv import load_dotenv

# Get backend directory (4 levels up from this file: monitors -> intelligence_agent -> agents -> src -> backend)
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent.parent.parent
_env_path = _backend_dir / ".env"

# Load environment variables from backend/.env
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Fallback: try to find .env in current working directory
    load_dotenv()


@dataclass
class NodeClassification:
    """Classification result for a single node/state."""
    node_id: str  # UP, BHR, WB, KAR
    relevance_score: float  # 0.0-1.0, how relevant is this news to this state?
    is_relevant: bool  # True if relevance_score > 0.3
    energy_impact_mw: float  # Estimated MW delta (+/- impact on demand/supply)
    impact_direction: str  # "increase_demand", "decrease_demand", "increase_supply", "decrease_supply", "neutral"
    confidence: float  # 0.0-1.0, how confident is the prediction?
    reasoning: str  # LLM explanation of why this affects this state
    flags: List[str]  # Semantic load descriptors
    impact_timeframe: str  # "immediate", "next_24h", "next_week", "long_term"
    

@dataclass
class MultiNodeClassification:
    """Classification across all 4 nodes for a single news article."""
    article_id: str
    article_title: str
    article_summary: str
    classified_at: str
    nodes: Dict[str, NodeClassification]  # node_id -> classification
    max_impact_node: Optional[str] = None  # Which node has highest impact?
    total_national_impact_mw: float = 0.0


# ============================================================================
# LLM PROMPT TEMPLATE
# ============================================================================

NODE_CLASSIFICATION_PROMPT = """You are an expert energy analyst for the Indian power grid. Your task is to analyze a news article and predict its impact on electricity demand/supply for SPECIFIC INDIAN STATES.

TARGET STATES:
1. Uttar Pradesh (UP) - Northern India, population 240M, industrial + agricultural
2. Bihar (BHR) - Eastern India, population 130M, agricultural, power-deficit state
3. West Bengal (WB) - Eastern India, population 100M, Kolkata industrial hub
4. Karnataka (KAR) - Southern India, population 68M, Bangalore tech hub, high AC load

NEWS ARTICLE:
-----------
Title: {title}
Summary: {summary}
Source: {source}
Published: {published}

SCHEDULED EVENTS TODAY:
{scheduled_events}

YOUR TASK:
For EACH of the 4 states (UP, BHR, WB, KAR), analyze:
1. Is this news relevant to THIS specific state?
2. Will it increase or decrease electricity demand/supply?
3. By how much (estimate MW delta)?
4. Why? (provide reasoning)
5. What load profile flags apply?

LOAD PROFILE FLAGS (semantic descriptors):
- "stadium_lighting" - Sports events with floodlights
- "residential_tv_surge" - Mass TV viewership events
- "commercial_restaurant_surge" - Restaurants/cafes staying open longer
- "industrial_shutdown" - Factory closures (elections, strikes, holidays)
- "commercial_closure" - Shops/offices closed
- "air_conditioning_surge" - Heatwave or event causing AC spike
- "agricultural_pump_surge" - Irrigation pump demand
- "transport_surge" - Metro/train/EV charging spike
- "festival_lighting" - Decorative lights for celebrations
- "temple_lighting" - Religious event lighting
- "coal_supply_disruption" - Coal shortage affecting thermal plants
- "transmission_failure" - Grid infrastructure damage
- "renewable_boost" - Solar/wind capacity addition
- "daytime_demand_reduction" - Reduced daytime industrial load
- "evening_peak_amplification" - Events amplifying 6-10 PM peak

RESPONSE FORMAT (JSON):
{{
  "nodes": {{
    "UP": {{
      "relevance_score": 0.0-1.0,
      "is_relevant": true/false,
      "energy_impact_mw": float (positive = demand increase, negative = demand decrease),
      "impact_direction": "increase_demand|decrease_demand|increase_supply|decrease_supply|neutral",
      "confidence": 0.0-1.0,
      "reasoning": "1-2 sentence explanation",
      "flags": ["flag1", "flag2"],
      "impact_timeframe": "immediate|next_24h|next_week|long_term"
    }},
    "BHR": {{ ... }},
    "WB": {{ ... }},
    "KAR": {{ ... }}
  }}
}}

IMPORTANT RULES:
1. Be conservative: If uncertain, set relevance_score < 0.3
2. Consider GEOGRAPHIC specificity: "Kolkata power cut" affects WB, not KAR
3. Consider STATE-SPECIFIC context: Bangalore has higher AC load than Patna
4. National events (IPL, elections) affect ALL states but with different magnitudes
5. Industrial news affects states with industries (UP > BHR for factories)
6. Agricultural news affects rural states (BHR > WB for farming)
7. Tech/IT news primarily affects KAR (Bangalore IT hub)
8. ALWAYS provide reasoning - explain your thought process

EXAMPLES:

Example 1 - IPL Match:
News: "IPL 2026: RCB vs MI at Chinnaswamy Stadium, Bangalore tonight"
UP: relevance=0.7, impact_mw=+150, reasoning="National viewership surge"
BHR: relevance=0.6, impact_mw=+100, reasoning="Moderate TV viewership in rural areas"
WB: relevance=0.7, impact_mw=+120, reasoning="High TV density in Kolkata"
KAR: relevance=0.95, impact_mw=+600, reasoning="Match IN Bangalore + high AC load + massive local viewership"

Example 2 - UP Election:
News: "UP Assembly Elections Phase 1 polling today, factories shut"
UP: relevance=1.0, impact_mw=-1200, reasoning="Direct impact: all factories closed for polling day"
BHR: relevance=0.3, impact_mw=-50, reasoning="Border spillover: some UP-dependent industries slow"
WB: relevance=0.2, impact_mw=0, reasoning="Minimal cross-state impact"
KAR: relevance=0.1, impact_mw=0, reasoning="No direct connection to southern states"

Example 3 - Coal Shortage:
News: "Thermal plants in Eastern India face coal shortage, 500 MW offline"
UP: relevance=0.4, impact_mw=-100, reasoning="Some thermal plants in UP affected"
BHR: relevance=0.8, impact_mw=-200, reasoning="BHR heavily dependent on thermal power"
WB: relevance=0.9, impact_mw=-200, reasoning="Eastern region includes WB thermal plants"
KAR: relevance=0.2, impact_mw=0, reasoning="Southern grid less affected by eastern coal"

Now analyze the article above and return JSON.
"""


# ============================================================================
# LLM INTERFACE
# ============================================================================

class NodeClassifierLLM:
    """
    LLM-powered classifier for node-specific energy impact analysis.
    """
    
    TARGET_NODES = ["UP", "BHR", "WB", "KAR"]
    
    def __init__(self, llm_provider: str = "openai", api_key: Optional[str] = None):
        """
        Initialize with LLM provider.
        
        Args:
            llm_provider: "openai", "anthropic", "google" (extensible)
            api_key: API key for LLM provider (or use env var)
        """
        self.llm_provider = llm_provider
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.classification_history: List[MultiNodeClassification] = []
        
    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM API and return response text.
        
        This is a stub - integrate with your actual LLM provider.
        """
        if self.llm_provider == "openai":
            return self._call_openai(prompt)
        elif self.llm_provider == "anthropic":
            return self._call_anthropic(prompt)
        else:
            # Fallback to mock for testing
            return self._mock_llm_response(prompt)
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API with gpt-4o-mini model."""
        try:
            import openai
            
            # Use new OpenAI client (v1.0+)
            client = openai.OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap model
                messages=[
                    {"role": "system", "content": "You are an expert energy grid analyst. Always respond in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for consistency
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"[NODE_CLASSIFIER] OpenAI API error: {e}")
            print(f"  Falling back to mock response...")
            return self._mock_llm_response(prompt)
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude API."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text
        except Exception as e:
            print(f"[NODE_CLASSIFIER] Anthropic API error: {e}")
            return self._mock_llm_response(prompt)
    
    def _mock_llm_response(self, prompt: str) -> str:
        """
        Mock LLM response for testing without API calls.
        Returns reasonable defaults based on keywords.
        """
        # Extract title from prompt
        title = ""
        if "Title:" in prompt:
            title = prompt.split("Title:")[1].split("\n")[0].strip()
        
        # Simple keyword-based logic
        mock_response = {
            "nodes": {}
        }
        
        for node in self.TARGET_NODES:
            # Default neutral response
            classification = {
                "relevance_score": 0.2,
                "is_relevant": False,
                "energy_impact_mw": 0.0,
                "impact_direction": "neutral",
                "confidence": 0.5,
                "reasoning": f"Minimal direct impact on {node}.",
                "flags": [],
                "impact_timeframe": "next_24h"
            }
            
            # Keyword-based adjustments
            title_lower = title.lower()
            
            # IPL/Cricket
            if "ipl" in title_lower or "cricket" in title_lower:
                classification["relevance_score"] = 0.75
                classification["is_relevant"] = True
                classification["energy_impact_mw"] = 300.0
                classification["impact_direction"] = "increase_demand"
                classification["confidence"] = 0.85
                classification["reasoning"] = "Cricket match causes residential TV surge + commercial activity."
                classification["flags"] = ["residential_tv_surge", "commercial_restaurant_surge", "evening_peak_amplification"]
            
            # Elections
            if "election" in title_lower and node == "UP":
                classification["relevance_score"] = 0.95
                classification["is_relevant"] = True
                classification["energy_impact_mw"] = -1000.0
                classification["impact_direction"] = "decrease_demand"
                classification["confidence"] = 0.90
                classification["reasoning"] = "Election polling day causes industrial shutdowns and commercial closures in UP."
                classification["flags"] = ["industrial_shutdown", "commercial_closure", "daytime_demand_reduction"]
            
            # Coal shortage
            if "coal" in title_lower and "shortage" in title_lower:
                classification["relevance_score"] = 0.70
                classification["is_relevant"] = True
                classification["energy_impact_mw"] = -150.0
                classification["impact_direction"] = "decrease_supply"
                classification["confidence"] = 0.75
                classification["reasoning"] = f"Coal shortage affects thermal generation capacity in {node}."
                classification["flags"] = ["coal_supply_disruption"]
            
            mock_response["nodes"][node] = classification
        
        return json.dumps(mock_response, indent=2)
    
    def classify_article(
        self,
        article_id: str,
        title: str,
        summary: str,
        source: str,
        published: str,
        scheduled_events: List[Dict] = None
    ) -> MultiNodeClassification:
        """
        Classify a single news article's impact on all 4 nodes.
        
        Args:
            article_id: Unique article identifier
            title: Article headline
            summary: Article description/summary
            source: News source
            published: Publication timestamp
            scheduled_events: List of scheduled events for context
        
        Returns:
            MultiNodeClassification with per-node predictions
        """
        # Format scheduled events for prompt
        scheduled_context = "None"
        if scheduled_events:
            scheduled_context = "\n".join([
                f"• {evt['event_name']} ({evt['event_type']}): {evt['delta_mw']:+.0f} MW"
                for evt in scheduled_events
            ])
        
        # Build prompt
        prompt = NODE_CLASSIFICATION_PROMPT.format(
            title=title,
            summary=summary,
            source=source,
            published=published,
            scheduled_events=scheduled_context
        )
        
        # Call LLM
        try:
            llm_response = self._call_llm(prompt)
            response_data = json.loads(llm_response)
        except Exception as e:
            print(f"[NODE_CLASSIFIER] LLM parsing error: {e}")
            # Fallback to neutral classification
            response_data = {"nodes": {}}
            for node in self.TARGET_NODES:
                response_data["nodes"][node] = {
                    "relevance_score": 0.1,
                    "is_relevant": False,
                    "energy_impact_mw": 0.0,
                    "impact_direction": "neutral",
                    "confidence": 0.3,
                    "reasoning": "Error during classification",
                    "flags": [],
                    "impact_timeframe": "next_24h"
                }
        
        # Parse into NodeClassification objects
        node_classifications = {}
        max_impact_node = None
        max_impact_value = 0.0
        total_impact = 0.0
        
        for node_id, node_data in response_data.get("nodes", {}).items():
            classification = NodeClassification(
                node_id=node_id,
                relevance_score=float(node_data.get("relevance_score", 0.0)),
                is_relevant=bool(node_data.get("is_relevant", False)),
                energy_impact_mw=float(node_data.get("energy_impact_mw", 0.0)),
                impact_direction=str(node_data.get("impact_direction", "neutral")),
                confidence=float(node_data.get("confidence", 0.5)),
                reasoning=str(node_data.get("reasoning", "")),
                flags=list(node_data.get("flags", [])),
                impact_timeframe=str(node_data.get("impact_timeframe", "next_24h"))
            )
            
            node_classifications[node_id] = classification
            
            # Track max impact
            impact_abs = abs(classification.energy_impact_mw)
            if impact_abs > max_impact_value:
                max_impact_value = impact_abs
                max_impact_node = node_id
            
            total_impact += classification.energy_impact_mw
        
        # Build result
        result = MultiNodeClassification(
            article_id=article_id,
            article_title=title,
            article_summary=summary,
            classified_at=datetime.utcnow().isoformat() + "Z",
            nodes=node_classifications,
            max_impact_node=max_impact_node,
            total_national_impact_mw=total_impact
        )
        
        self.classification_history.append(result)
        return result
    
    def classify_batch(
        self,
        articles: List[Dict[str, any]],
        scheduled_events: List[Dict] = None
    ) -> List[MultiNodeClassification]:
        """
        Classify multiple articles in batch.
        
        Args:
            articles: List of article dicts with keys: id, title, summary, source, published
            scheduled_events: Scheduled events for today
        
        Returns:
            List of MultiNodeClassification results
        """
        results = []
        
        for i, article in enumerate(articles):
            print(f"  [NODE_CLASSIFIER] Classifying article {i+1}/{len(articles)}: {article.get('title', '')[:50]}...")
            
            result = self.classify_article(
                article_id=article.get("id", f"article_{i}"),
                title=article.get("title", ""),
                summary=article.get("summary", ""),
                source=article.get("source", ""),
                published=article.get("published", ""),
                scheduled_events=scheduled_events
            )
            
            results.append(result)
        
        return results
    
    def get_node_summary(self, node_id: str) -> Dict[str, any]:
        """
        Aggregate all classifications for a specific node.
        
        Returns:
            Summary dict with total impact, relevant articles, flags
        """
        relevant_articles = []
        total_impact_mw = 0.0
        all_flags = set()
        
        for classification in self.classification_history:
            node_data = classification.nodes.get(node_id)
            if node_data and node_data.is_relevant:
                relevant_articles.append({
                    "article_title": classification.article_title,
                    "impact_mw": node_data.energy_impact_mw,
                    "reasoning": node_data.reasoning,
                    "flags": node_data.flags
                })
                total_impact_mw += node_data.energy_impact_mw
                all_flags.update(node_data.flags)
        
        return {
            "node_id": node_id,
            "relevant_article_count": len(relevant_articles),
            "total_impact_mw": total_impact_mw,
            "impact_direction": "increase" if total_impact_mw > 0 else "decrease" if total_impact_mw < 0 else "neutral",
            "active_flags": list(all_flags),
            "relevant_articles": relevant_articles
        }


# ============================================================================
# EXPORT FUNCTION
# ============================================================================

def save_node_classifications_json(
    classifications: List[MultiNodeClassification],
    output_path: str
) -> None:
    """Save classification results to JSON file."""
    output_data = []
    
    for classification in classifications:
        article_data = {
            "article_id": classification.article_id,
            "article_title": classification.article_title,
            "article_summary": classification.article_summary,
            "classified_at": classification.classified_at,
            "max_impact_node": classification.max_impact_node,
            "total_national_impact_mw": classification.total_national_impact_mw,
            "nodes": {}
        }
        
        for node_id, node_class in classification.nodes.items():
            article_data["nodes"][node_id] = {
                "relevance_score": node_class.relevance_score,
                "is_relevant": node_class.is_relevant,
                "energy_impact_mw": node_class.energy_impact_mw,
                "impact_direction": node_class.impact_direction,
                "confidence": node_class.confidence,
                "reasoning": node_class.reasoning,
                "flags": node_class.flags,
                "impact_timeframe": node_class.impact_timeframe
            }
        
        output_data.append(article_data)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(output_data, indent=2))


if __name__ == "__main__":
    # Demo usage
    print("=== Node Classifier Demo ===\n")
    
    classifier = NodeClassifierLLM(llm_provider="mock")  # Use mock for demo
    
    # Test articles
    test_articles = [
        {
            "id": "test_1",
            "title": "IPL 2026: RCB vs MI at Chinnaswamy Stadium tonight",
            "summary": "Royal Challengers Bangalore face Mumbai Indians in a crucial IPL match at 7:30 PM.",
            "source": "ESPN Cricinfo",
            "published": "2026-04-08T12:00:00Z"
        },
        {
            "id": "test_2",
            "title": "UP Assembly Elections Phase 1 polling underway",
            "summary": "Factories and industries shut down across Uttar Pradesh for election polling day.",
            "source": "Times of India",
            "published": "2026-04-10T08:00:00Z"
        }
    ]
    
    results = classifier.classify_batch(test_articles)
    
    for result in results:
        print(f"\n📰 {result.article_title}")
        print(f"   Max Impact: {result.max_impact_node} ({result.total_national_impact_mw:+.0f} MW national)")
        for node_id, node_class in result.nodes.items():
            if node_class.is_relevant:
                print(f"   • {node_id}: {node_class.energy_impact_mw:+.0f} MW - {node_class.reasoning[:60]}...")
    
    # Node summaries
    print("\n=== Node Summaries ===")
    for node in ["UP", "BHR", "WB", "KAR"]:
        summary = classifier.get_node_summary(node)
        print(f"\n{node}: {summary['relevant_article_count']} relevant articles, {summary['total_impact_mw']:+.0f} MW total impact")
        print(f"  Flags: {', '.join(summary['active_flags'][:5])}")
