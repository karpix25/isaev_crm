"""
OpenRouter API Service for AI-powered lead qualification
"""
import json
import re
import logging
from typing import Optional, Dict, Any, List
import httpx
from datetime import datetime
from langfuse import Langfuse

from src.config import settings

logger = logging.getLogger(__name__)


class OpenRouterService:
    """Service for interacting with OpenRouter API"""
    
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.base_url = getattr(settings, 'openrouter_base_url', 'https://openrouter.ai/api/v1')
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Langfuse Tracing
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            self.langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host
            )
        else:
            self.langfuse = None
    
    async def generate_response(
        self,
        conversation_history: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate AI response based on conversation history
        
        Args:
            conversation_history: List of messages [{"role": "user"/"assistant", "content": "..."}]
            system_prompt: System prompt for AI behavior
            
        Returns:
            {
                "text": "Response text for user",
                "extracted_data": {...},  # Parsed JSON data
                "usage": {"tokens": 123}
            }
        """
        try:
            # Langfuse Trace
            trace = None
            if self.langfuse:
                trace = self.langfuse.trace(
                    id=trace_id,
                    user_id=user_id,
                    name="chat-completion",
                    metadata={"model": model or self.model}
                )

            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt}
            ] + conversation_history
            
            # Langfuse Generation Span
            generation = None
            if trace:
                generation = trace.generation(
                    name="openrouter-generation",
                    model=model or self.model,
                    input=messages,
                    model_parameters={"temperature": 0.7}
                )

            # Call OpenRouter API
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://renovation-crm.com",  # Optional
                    "X-Title": "Renovation CRM"  # Optional
                },
                json={
                    "model": model or self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000,
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract response
            ai_message = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            # End Langfuse Generation
            if generation:
                generation.end(
                    output=ai_message,
                    usage={
                        "input": usage.get("prompt_tokens", 0),
                        "output": usage.get("completion_tokens", 0),
                        "total": usage.get("total_tokens", 0)
                    }
                )


            # Parse JSON from response
            extracted_data = self._extract_json_from_response(ai_message)
            
            logger.debug("AI response received, extracted_data keys: %s", list(extracted_data.keys()) if extracted_data else None)
            
            # PRIORITY 1: If JSON has "message" field, use it (this is the user-facing text)
            if extracted_data and "message" in extracted_data:
                clean_text = str(extracted_data["message"])
            else:
                # PRIORITY 2: Try to get clean text (without JSON block)
                clean_text = self._remove_json_from_response(ai_message)
                
                # PRIORITY 3: If still nothing, use the raw AI message as fallback
                if not clean_text or clean_text.isspace():
                    clean_text = ai_message

            return {
                "text": clean_text,
                "extracted_data": extracted_data,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
            }
            
        except httpx.HTTPStatusError as e:
            logger.error("OpenRouter API error: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Error calling OpenRouter API: %s", e)
            raise
    
    def _extract_json_from_response(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON data from AI response with robust recovery logic.
        Handles markdown blocks, markers, emoji, and common formatting errors.
        """
        try:
            # 1. Try to find content between markers if they exist
            json_str = None
            
            # Primary: ---JSON--- marker
            marker_match = re.search(r'---JSON---(.*?)(?:$|---)', text, re.DOTALL)
            if marker_match:
                json_str = marker_match.group(1).strip()
            
            # Secondary: code blocks
            if not json_str or "{" not in json_str:
                block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
                if block_match:
                    json_str = block_match.group(1).strip()
            
            # Tertiary: raw braces (most aggressive)
            if not json_str or "{" not in json_str:
                raw_match = re.search(r'(\{.*\})', text, re.DOTALL)
                if raw_match:
                    json_str = raw_match.group(1).strip()

            if not json_str:
                return None

            # 2. Cleanup common LLM JSON errors
            
            # Remove markdown formatting if still present inside
            json_str = re.sub(r'^```(?:json)?', '', json_str)
            json_str = re.sub(r'```$', '', json_str)
            
            # Repair trailing commas: {"a": 1,} -> {"a": 1}
            json_str = re.sub(r',\s*\}', '}', json_str)
            json_str = re.sub(r',\s*\]', ']', json_str)
            
            # Extract only the outermost {} to avoid lead-in text
            first_brace = json_str.find('{')
            last_brace = json_str.rfind('}')
            if first_brace != -1 and last_brace != -1:
                json_str = json_str[first_brace:last_brace+1]

            # Parse with strict=False to allow emoji and special characters
            return json.loads(json_str, strict=False)
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON from AI response: %s", e)
            return None
        except Exception as e:
            logger.warning("Unexpected error extracting JSON: %s", e)
            return None
    
    def _remove_json_from_response(self, text: str) -> str:
        """
        Remove JSON block from response to get clean text.
        Also handles cases where the entire response is a JSON object.
        """
        # 1. Remove ---JSON--- marker and everything after
        clean = re.sub(r'---JSON---.*', '', text, flags=re.DOTALL)
        
        # 2. Remove code blocks
        clean = re.sub(r'```(?:json)?.*?```', '', clean, flags=re.DOTALL)
        
        # 3. If the remaining text starts with { and ends with }, and is valid JSON,
        # it might be a raw JSON response that should be fully removed (message field will be used instead)
        clean = clean.strip()
        if clean.startswith('{') and clean.endswith('}'):
            try:
                # If it's the ONLY thing in the message, remove it so we can fallback to extracted_data["message"]
                json.loads(clean)
                return ""
            except:
                pass

        return clean.strip()
    
    def should_handoff(self, extracted_data: Optional[Dict[str, Any]]) -> bool:
        """
        Determine if lead should be handed off to human manager
        
        Criteria:
        - is_hot_lead: true
        - confidence >= 80
        - Has phone number
        """
        if not extracted_data:
            return False
        
        is_hot = extracted_data.get("is_hot_lead", False)
        confidence = extracted_data.get("confidence", 0)
        has_phone = bool(extracted_data.get("phone"))
        
        # Hot lead with high confidence
        if is_hot and confidence >= 70:
            return True
        
        # Very high confidence (all info collected)
        if confidence >= 85 and has_phone:
            return True
        
        return False
    
    async def generate_embeddings(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        Generate vector embeddings for text using OpenRouter SDK
        """
        # Ensure model has provider prefix for OpenRouter
        emb_model = model or getattr(settings, 'openrouter_embedding_model', 'openai/text-embedding-3-small')
        if '/' not in emb_model:
            emb_model = f"openai/{emb_model}"
            
        logger.info(f"Generating embeddings with model: {emb_model}")
        
        try:
            from openrouter import OpenRouter
            
            # Use SDK defaults for server_url to avoid path duplication issues
            openrouter_client = OpenRouter(
                api_key=self.api_key,
                http_referer="https://github.com/karpix25/isaev_crm",
                x_title="Isaev CRM"
            )
            
            # Log key presence (masked)
            key_status = f"{self.api_key[:4]}...{self.api_key[-4:]}" if self.api_key else "MISSING"
            logger.info(f"Using OpenRouter API Key: {key_status} for model: {emb_model}")
            
            res = await openrouter_client.embeddings.generate_async(
                input=text,
                model=emb_model
            )
            
            # Diagnostic: check dimension
            if res and res.data and len(res.data) > 0:
                dim = len(res.data[0].embedding)
                logger.info(f"OpenRouter returned embedding with dimension: {dim} for model: {emb_model}")
                if dim != 1536:
                    logger.warning(f"Embedding dimension mismatch! Got {dim}, expected 1536 for the 'knowledge_base' table.")
            
            # The SDK returns a strongly typed CreateEmbeddingsResponse object
            if not res or not res.data:
                raise ValueError(f"OpenRouter API returned empty data for model {emb_model}")
                
            embedding = res.data[0].embedding
            
            # Dimension Guard: ensure always 1536 dimensions for the database
            target_dim = 1536
            current_dim = len(embedding)
            
            if current_dim < target_dim:
                logger.info(f"Padding embedding from {current_dim} to {target_dim} (zero-padding)")
                # Handle potential immutability or different list types by creating a new list
                embedding = list(embedding)
                embedding.extend([0.0] * (target_dim - current_dim))
            elif current_dim > target_dim:
                logger.warning(f"Truncating embedding from {current_dim} to {target_dim}")
                embedding = embedding[:target_dim]
                
            return embedding
            
        except Exception as e:
            err_str = str(e)
            logger.error(f"Error generating embeddings via OpenRouter SDK: {err_str}")
            
            # Extract common OpenRouter error messages from SDK validation errors
            if "No successful provider responses" in err_str:
                raise ValueError(f"OpenRouter не нашел провайдера для '{emb_model}'. Проверьте баланс кредитов или настройки провайдеров в OpenRouter.")
            
            if "User not found" in err_str or "401" in err_str:
                raise ValueError("OpenRouter сообщает: 'User not found' или 401. Вероятно, ваш API ключ недействителен или неверно указан.")
            
            # Fallback for generic SDK validation errors that might contain the real error inside 'input_value'
            import re
            # Extract from 'message': '...' or any key containing the error text
            match = re.search(r"['\"]message['\"]\s*:\s*['\"]([^'\"]*)['\"]", err_str)
            if match:
                real_msg = match.group(1)
                raise ValueError(f"Ошибка OpenRouter: {real_msg}")
                
            raise ValueError(f"Ошибка OpenRouter: {err_str}")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
openrouter_service = OpenRouterService()
