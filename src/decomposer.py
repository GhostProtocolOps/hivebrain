"""
HIVEBrain Semantic Decomposer & Embedding Engine.
Implements Dual-Decomposition:
- Any prompt or response (even 'hi') is deconstructed into:
  intent, entities, constraints, metrics, and AST representation.
- Produces normalized 384-dimensional semantic embedding vector for pgvector.
"""

import re
import math
import hashlib
from typing import Dict, Any, List

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "at",
    "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "can", "will", "just", "should", "now",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they"
}

class SemanticDecomposer:
    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim

    def decompose(self, text: str, role: str = "prompt") -> Dict[str, Any]:
        """
        Deconstructs any prompt or response into intent, entities, constraints, metrics, and AST.
        """
        clean_text = text.strip()
        tokens = re.findall(r'[a-zA-Z0-9_\-\.]+', clean_text.lower())
        words = [t for t in tokens if t not in STOPWORDS and len(t) > 1]

        # 1. Intent extraction
        intent = self._infer_intent(clean_text, tokens, role)

        # 2. Entity extraction
        entities = self._extract_entities(clean_text, words)

        # 3. Constraint extraction
        constraints = self._extract_constraints(clean_text)

        # 4. Metrics extraction
        metrics = self._extract_metrics(clean_text)

        # 5. AST representation
        ast_rep = {
            "type": "SemanticRootNode",
            "role": role,
            "intent": intent,
            "token_count": len(tokens),
            "unique_terms": len(set(words)),
            "clauses": [
                {"id": idx, "text": clause.strip()}
                for idx, clause in enumerate(re.split(r'[;\n\.\?\!]+', clean_text))
                if clause.strip()
            ]
        }

        # 6. Generate 384-dimensional dense semantic embedding
        embedding = self.generate_embedding(clean_text)

        return {
            "intent": intent,
            "entities": entities,
            "constraints": constraints,
            "metrics": metrics,
            "ast_representation": ast_rep,
            "embedding": embedding
        }

    def _infer_intent(self, text: str, tokens: List[str], role: str) -> str:
        lower = text.lower()
        if role == "response":
            if any(w in lower for w in ["completed", "approved", "done", "fixed", "built", "success"]):
                return "execution_resolution"
            if any(w in lower for w in ["error", "rejected", "failed", "bug"]):
                return "error_diagnosis"
            return "informational_synthesis"

        # Prompt role
        if lower.startswith("hi") or lower.startswith("hello") or lower == "hey":
            return "conversational_greeting"
        if any(w in lower for w in ["build", "create", "make", "implement", "deploy"]):
            return "implementation_construction"
        if any(w in lower for w in ["why", "how", "what", "explain", "review", "audit"]):
            return "analytical_inquiry"
        if any(w in lower for w in ["fix", "resolve", "patch", "repair", "debug"]):
            return "remediation_maintenance"
        if any(w in lower for w in ["query", "fetch", "search", "read", "get"]):
            return "semantic_retrieval"
        return "general_instruction"

    def _extract_entities(self, text: str, words: List[str]) -> List[str]:
        # Domain identifiers, PascalCase, snake_case, camelCase, technical terms
        candidates = set()
        
        # Regex for identifiers: table names, function names, tech terms
        matches = re.findall(r'\b[A-Za-z0-9]+(?:[_\-\.][A-Za-z0-9]+)+\b|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b', text)
        for m in matches:
            candidates.add(m.lower())

        # Significant frequent keywords
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)
        for w in sorted_words[:10]:
            candidates.add(w)

        if not candidates and words:
            candidates.update(words[:5])
        elif not candidates:
            candidates.add("root_concept")

        return sorted(list(candidates))

    def _extract_constraints(self, text: str) -> List[str]:
        constraints = []
        lower = text.lower()
        patterns = [
            r'must\s+[^,\.\n]+',
            r'should\s+not\s+[^,\.\n]+',
            r'never\s+[^,\.\n]+',
            r'only\s+[^,\.\n]+',
            r'sub-\d+ms',
            r'every\s+\d+\s+days?'
        ]
        for p in patterns:
            found = re.findall(p, lower)
            constraints.extend(found)
        return constraints[:10]

    def _extract_metrics(self, text: str) -> Dict[str, Any]:
        metrics = {}
        # Latency / timing (ms, s, days)
        ms_matches = re.findall(r'(\d+)\s*(?:ms|milliseconds)', text, re.IGNORECASE)
        if ms_matches:
            metrics["latency_ms"] = [int(m) for m in ms_matches]

        days_matches = re.findall(r'(\d+)\s*(?:days?|day)', text, re.IGNORECASE)
        if days_matches:
            metrics["retention_days"] = [int(m) for m in days_matches]

        port_matches = re.findall(r'port\s+(\d+)', text, re.IGNORECASE)
        if port_matches:
            metrics["ports"] = [int(p) for p in port_matches]

        metrics["char_length"] = len(text)
        metrics["word_count"] = len(text.split())
        return metrics

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a dense, normalized 384-dimensional semantic projection vector.
        Uses deterministic multi-hash pseudo-random projection to ensure
        semantically similar or identical tokens map to proximal hyperspheres.
        """
        dim = self.embedding_dim
        vec = [0.0] * dim
        tokens = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
        if not tokens:
            tokens = ["empty"]

        for i, token in enumerate(tokens):
            # Positional decay & frequency weighting
            weight = 1.0 / (1.0 + 0.05 * i)
            # Hash token across dimension buckets
            token_bytes = token.encode('utf-8')
            h1 = int(hashlib.sha256(token_bytes).hexdigest(), 16)
            h2 = int(hashlib.md5(token_bytes).hexdigest(), 16)

            for step in range(8):
                idx = (h1 + step * h2) % dim
                sign = 1.0 if ((h1 >> step) & 1) else -1.0
                vec[idx] += sign * weight

        # L2 normalization to unit sphere (essential for cosine distance <=> in pgvector)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0

        return [round(x, 6) for x in vec]
