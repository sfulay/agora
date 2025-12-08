"""
AgoraChat RAG Pipeline

Handles semantic search and medley generation for chat queries.
"""

import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple
import pickle

from django.conf import settings
from pages.models import InterviewSegment, SegmentEmbedding, ChatMedley, ChatMessage
from interviewer_agent.interviewer_utils.settings import get_open_api_keyset
from openai import OpenAI


class EmbeddingService:
    """Service for generating and managing embeddings"""

    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        return self.model.encode(text, convert_to_numpy=True)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)


class VectorSearchService:
    """Service for FAISS-based vector similarity search"""

    def __init__(self, dimension=384):
        self.dimension = dimension
        self.index = None
        self.segment_ids = []

    def build_index(self, embeddings: np.ndarray, segment_ids: List[int]):
        """Build FAISS index from embeddings"""
        # Use L2 distance (equivalent to cosine similarity after normalization)
        self.index = faiss.IndexFlatL2(self.dimension)

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)

        # Add to index
        self.index.add(embeddings)
        self.segment_ids = segment_ids

        print(f"Built FAISS index with {len(segment_ids)} segments")

    def load_from_db(self):
        """Load embeddings from database and build index"""
        segment_embeddings = SegmentEmbedding.objects.all().select_related('segment')

        if not segment_embeddings.exists():
            raise ValueError("No embeddings found in database. Run generate_embeddings command first.")

        embeddings_list = []
        segment_ids = []

        for seg_emb in segment_embeddings:
            # Deserialize binary embedding
            embedding = np.frombuffer(seg_emb.embedding_vector, dtype=np.float32)
            embeddings_list.append(embedding)
            segment_ids.append(seg_emb.segment_id)

        embeddings = np.array(embeddings_list)
        self.build_index(embeddings, segment_ids)

    def search(self, query_embedding: np.ndarray, top_k: int = 50) -> List[int]:
        """Search for most similar segments"""
        if self.index is None:
            raise ValueError("Index not built. Call build_index() or load_from_db() first.")

        # Normalize query
        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        faiss.normalize_L2(query_embedding)

        # Search
        distances, indices = self.index.search(query_embedding, top_k)

        # Return segment IDs
        return [self.segment_ids[i] for i in indices[0]]


class ChatMedleyGenerator:
    """Generates medleys for chat queries using hybrid RAG"""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_search = VectorSearchService(dimension=self.embedding_service.dimension)
        self.client = OpenAI(api_key=get_open_api_keyset()['key'])

        # Load prompts
        prompt_path = os.path.join(
            settings.BASE_DIR,
            'generating_v2',
            'prompts',
            'chat_medley_selection.txt'
        )
        with open(prompt_path, 'r') as f:
            self.selection_prompt = f.read()

    def _build_context_aware_query(self, query: str, conversation_history: List[Dict]) -> str:
        """Build a context-aware query from conversation history"""
        if not conversation_history:
            return query

        # Include last 3 messages for context
        recent_messages = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history

        context = "\n".join([
            f"{'User' if msg['is_user'] else 'Agora'}: {msg['query_text']}"
            for msg in recent_messages
        ])

        return f"Previous conversation:\n{context}\n\nNew question: {query}"

    def generate_medley(
        self,
        query: str,
        conversation_history: List[Dict] = None,
        top_k: int = 50,
        target_segments: int = 10
    ) -> Dict:
        """
        Generate a medley for a chat query

        Args:
            query: User's question
            conversation_history: List of previous messages
            top_k: Number of candidates to retrieve
            target_segments: Number of segments to select for medley

        Returns:
            Dict with selected_segments, reasoning, relevance_score, total_duration
        """
        conversation_history = conversation_history or []

        # Step 1: Build context-aware query
        context_query = self._build_context_aware_query(query, conversation_history)

        # Step 2: Embed query
        query_embedding = self.embedding_service.embed_text(context_query)

        # Step 3: Vector search
        if self.vector_search.index is None:
            self.vector_search.load_from_db()

        candidate_segment_ids = self.vector_search.search(query_embedding, top_k=top_k)

        # Step 4: Fetch segment data
        segments = InterviewSegment.objects.filter(
            id__in=candidate_segment_ids
        ).select_related('audio__question__interview__participant')

        # Build segment data for GPT
        segments_data = []
        for seg in segments:
            participant = seg.audio.question.interview.participant
            segments_data.append({
                'segment_id': seg.id,
                'participant_username': participant.username,
                'participant_display_name': participant.display_name,
                'segment_text': seg.segment_text,
                'duration': seg.duration,
                'sequence_number': seg.sequence_number
            })

        # Step 5: GPT reranking and selection
        result = self._gpt_select_segments(
            query=query,
            conversation_history=conversation_history,
            segments=segments_data,
            target_segments=target_segments
        )

        return result

    def _gpt_select_segments(
        self,
        query: str,
        conversation_history: List[Dict],
        segments: List[Dict],
        target_segments: int
    ) -> Dict:
        """Use GPT to select and rerank best segments"""

        # Format conversation history
        history_text = ""
        if conversation_history:
            history_text = "Conversation history:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = "User" if msg['is_user'] else "Agora"
                history_text += f"{role}: {msg['query_text']}\n"
            history_text += "\n"

        # Format segments
        segments_text = json.dumps(segments, indent=2)

        # Build prompt
        prompt = self.selection_prompt.format(
            conversation_history=history_text,
            query=query,
            segments_data=segments_text,
            target_segments=target_segments
        )

        # Call GPT
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at selecting relevant interview segments."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        result = json.loads(response.choices[0].message.content)

        # Add full segment data to selected segments
        segment_map = {seg['segment_id']: seg for seg in segments}
        for selected in result['selected_segments']:
            seg_id = selected['segment_id']
            if seg_id in segment_map:
                selected.update(segment_map[seg_id])

        return result
