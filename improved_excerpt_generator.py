#!/usr/bin/env python3
"""
Improved excerpt generator with advanced pre-processing, prompt engineering, and post-processing
Based on Grok's recommendations for reducing redundancy and improving quality
"""

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

logger = logging.getLogger(__name__)

class ImprovedExcerptGenerator:
    """Advanced excerpt generator with redundancy reduction and quality improvement"""
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", model: str = "llama3.1:8b"):
        self.ollama_url = ollama_url
        self.model = model
        self.target_words = 100
        self.tolerance = 0.15  # 15% tolerance
        
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        
        # Also download punkt_tab for newer NLTK versions
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            try:
                nltk.download('punkt_tab', quiet=True)
            except:
                pass  # Fallback to punkt if punkt_tab fails
    
    def generate_neutral_excerpt(self, url: str) -> Dict[str, Any]:
        """Generate a high-quality neutral excerpt from article URL"""
        try:
            # Step 1: Fetch article content from URL
            article_content = self._fetch_article_content(url)
            if not article_content:
                return {"success": False, "error": "Failed to fetch article content"}
            
            # Step 2: Advanced pre-processing to clean content
            cleaned_content = self._clean_web_content(article_content)
            
            # Step 3: Extract key information with deduplication
            extracted_info = self._extract_article_info_advanced(cleaned_content)
            
            # Step 4: Generate excerpts using improved LLM pipeline
            neutral_excerpt = self._generate_excerpt_with_advanced_llm(
                extracted_info.get("content", ""), 
                extracted_info.get("original_title", "")
            )
            
            if not neutral_excerpt:
                return {"success": False, "error": "LLM failed to generate excerpt"}
            
            # Step 5: Post-process to remove redundancy
            final_excerpt = self._post_process_summary(neutral_excerpt)
            
            # Step 6: Validate quality
            quality_score = self._evaluate_excerpt_quality(final_excerpt)
            
            return {
                "success": True,
                "neutral_excerpt": final_excerpt,
                "word_count": len(final_excerpt.split()),
                "quality_score": quality_score,
                "original_url": url,
                "extracted_info": extracted_info,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating neutral excerpt: {e}")
            return {"success": False, "error": str(e)}
    
    def _fetch_article_content(self, url: str) -> Optional[str]:
        """Fetch article content from URL using synchronous requests"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"❌ Error fetching article content: {e}")
            return None
    
    def _clean_web_content(self, html_content: str) -> str:
        """Advanced content cleaning to remove boilerplate and deduplicate"""
        try:
            # Parse HTML and extract main text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove navigation, footer, ads, and scripts
            for elem in soup(['nav', 'footer', 'script', 'style', 'header', 'aside']):
                elem.decompose()
            
            # Remove elements with common ad/navigation classes
            for elem in soup.find_all(class_=re.compile(r'(ad|nav|menu|footer|sidebar|social)', re.I)):
                elem.decompose()
            
            # Extract main content
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'(content|article|story)', re.I))
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace and normalize
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Split into sentences and deduplicate
            try:
                sentences = sent_tokenize(text)
            except:
                # Fallback to simple sentence splitting if NLTK fails
                sentences = re.split(r'[.!?]+', text)
                sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) > 10:  # Only deduplicate if we have enough sentences
                # Compute TF-IDF and cosine similarity for deduplication
                vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
                tfidf_matrix = vectorizer.fit_transform(sentences)
                similarity_matrix = cosine_similarity(tfidf_matrix)
                
                # Keep sentences with similarity < 0.8
                unique_sentences = []
                used_indices = set()
                for i, sent in enumerate(sentences):
                    if i not in used_indices and len(sent.strip()) > 20:  # Minimum sentence length
                        unique_sentences.append(sent.strip())
                        # Mark similar sentences (threshold 0.8)
                        for j, sim in enumerate(similarity_matrix[i]):
                            if sim > 0.8 and i != j:
                                used_indices.add(j)
                
                # Limit to top 10 most relevant sentences
                return ' '.join(unique_sentences[:10])
            else:
                return ' '.join(sentences)
                
        except Exception as e:
            logger.error(f"❌ Error cleaning content: {e}")
            return html_content
    
    def _extract_article_info_advanced(self, content: str) -> Dict[str, Any]:
        """Extract key information with advanced processing"""
        try:
            # Extract title from content (look for common patterns)
            title_match = re.search(r'^([^.!?]{10,100})', content)
            title = title_match.group(1).strip() if title_match else "Article"
            
            # Clean and limit content for processing
            content_clean = content[:2000]  # Limit for processing
            
            return {
                "original_title": title,
                "content": content_clean,
                "source_domain": ""
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting article info: {e}")
            return {"original_title": "Article", "content": content[:1000], "source_domain": ""}
    
    def _generate_excerpt_with_advanced_llm(self, content: str, original_title: str) -> str:
        """Generate excerpt using improved LLM pipeline with better prompting"""
        try:
            # Step 1: Extract key points first
            key_points_prompt = f"""Extract 3-5 unique, non-redundant key points from this article. Each point should be a single sentence, concise, and distinct. Avoid boilerplate, repetitive phrases, or irrelevant details.

Title: {original_title}
Content: {content[:800]}

Key points:"""
            
            key_points = self._call_ollama(key_points_prompt)
            
            # Step 2: Generate summary based on key points
            summary_prompt = f"""Using only these key points, write a 100-word summary that captures the core arguments, key quotes, and implications without repetition or redundancy:

Key points: {key_points}

Summary:"""
            
            summary = self._call_ollama(summary_prompt)
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error in advanced LLM excerpt generation: {e}")
            return ""
    
    def _post_process_summary(self, summary: str) -> str:
        """Post-process to remove redundancy and enforce word limits"""
        try:
            # Clean up the summary
            summary = summary.strip()
            
            # Remove common LLM artifacts
            summary = re.sub(r'^(Summary:|Key points:|Excerpt:)', '', summary, flags=re.IGNORECASE)
            summary = summary.strip()
            
            # Tokenize and count words
            try:
                words = word_tokenize(summary)
            except:
                # Fallback to simple word splitting if NLTK fails
                words = summary.split()
            word_count = len(words)
            
            # Calculate target range (85-115 words with 15% tolerance)
            min_words = int(self.target_words * (1 - self.tolerance))
            max_words = int(self.target_words * (1 + self.tolerance))
            
            if word_count > max_words:
                # Truncate intelligently by sentences
                try:
                    sentences = sent_tokenize(summary)
                except:
                    # Fallback to simple sentence splitting
                    sentences = re.split(r'[.!?]+', summary)
                    sentences = [s.strip() for s in sentences if s.strip()]
                current_words = []
                for sent in sentences:
                    try:
                        sent_words = word_tokenize(sent)
                    except:
                        sent_words = sent.split()
                    if len(current_words) + len(sent_words) <= max_words:
                        current_words.extend(sent_words)
                    else:
                        break
                summary = ' '.join(current_words)
            
            elif word_count < min_words:
                # Add context if too short
                summary += " Additional details available in the full article."
            
            # Check for redundancy (repeated phrases)
            try:
                words_lower = [w.lower() for w in word_tokenize(summary)]
            except:
                words_lower = [w.lower() for w in summary.split()]
            word_counts = Counter(words_lower)
            common_words = [word for word, count in word_counts.items() 
                          if count > 3 and word not in {'the', 'and', 'of', 'to', 'a', 'in', 'is', 'it', 'that', 'for', 'as', 'with', 'by'}]
            
            if common_words:
                logger.warning(f"⚠️ Potential redundancy detected: {common_words}")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error in post-processing: {e}")
            return summary
    
    def _evaluate_excerpt_quality(self, excerpt: str) -> float:
        """Evaluate excerpt quality based on various metrics"""
        try:
            try:
                words = word_tokenize(excerpt)
            except:
                words = excerpt.split()
            word_count = len(words)
            
            # Quality score based on:
            # 1. Word count appropriateness (0-1)
            target_range = (85, 115)
            if target_range[0] <= word_count <= target_range[1]:
                word_score = 1.0
            else:
                word_score = max(0, 1 - abs(word_count - 100) / 50)
            
            # 2. Sentence diversity (0-1)
            try:
                sentences = sent_tokenize(excerpt)
            except:
                sentences = re.split(r'[.!?]+', excerpt)
                sentences = [s.strip() for s in sentences if s.strip()]
            if len(sentences) > 1:
                # Calculate sentence length diversity
                try:
                    sent_lengths = [len(word_tokenize(sent)) for sent in sentences]
                except:
                    sent_lengths = [len(sent.split()) for sent in sentences]
                length_variance = sum((l - sum(sent_lengths)/len(sent_lengths))**2 for l in sent_lengths) / len(sent_lengths)
                diversity_score = min(1.0, length_variance / 100)
            else:
                diversity_score = 0.5
            
            # 3. Redundancy check (0-1)
            word_counts = Counter([w.lower() for w in words])
            unique_words = len(set(w.lower() for w in words))
            redundancy_score = unique_words / len(words) if words else 0
            
            # Combined quality score
            quality_score = (word_score * 0.4 + diversity_score * 0.3 + redundancy_score * 0.3)
            
            return round(quality_score, 2)
            
        except Exception as e:
            logger.error(f"❌ Error evaluating quality: {e}")
            return 0.5
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API with improved prompting"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional news editor. Write concise, factual summaries. Avoid repetition and redundancy. Focus on key facts and implications."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Lower temperature for more focused output
                        "max_tokens": 200
                    }
                },
                timeout=45
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', '').strip()
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Ollama API call timed out after 45 seconds.")
            return ""
        except Exception as e:
            logger.error(f"❌ Error calling Ollama: {e}")
            return ""
