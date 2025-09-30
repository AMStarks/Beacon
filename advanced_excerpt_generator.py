#!/usr/bin/env python3
"""
Advanced excerpt generator using intelligent text processing without LLM dependency
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

logger = logging.getLogger(__name__)

class AdvancedExcerptGenerator:
    """Advanced excerpt generator with intelligent text processing and redundancy reduction"""
    
    def __init__(self):
        self.target_words = 100
        self.tolerance = 0.15  # 15% tolerance
    
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
            
            # Step 4: Generate excerpt using advanced text processing
            neutral_excerpt = self._generate_excerpt_with_advanced_processing(
                extracted_info.get("content", ""), 
                extracted_info.get("original_title", "")
            )
            
            if not neutral_excerpt:
                return {"success": False, "error": "Failed to generate excerpt"}
            
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
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]
            
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
    
    def _generate_excerpt_with_advanced_processing(self, content: str, original_title: str) -> str:
        """Generate excerpt using advanced text processing without LLM"""
        try:
            # Split content into sentences
            sentences = re.split(r'[.!?]+', content)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]
            
            if not sentences:
                return f"{original_title}. Latest news update."
            
            # Remove duplicate sentences first
            unique_sentences = []
            seen = set()
            for sent in sentences:
                sent_lower = sent.lower().strip()
                if sent_lower not in seen and len(sent_lower) > 20:
                    unique_sentences.append(sent)
                    seen.add(sent_lower)
            
            # Score sentences based on relevance and uniqueness
            scored_sentences = []
            for i, sent in enumerate(unique_sentences[:20]):  # Limit to first 20 unique sentences
                score = self._score_sentence(sent, original_title)
                scored_sentences.append((score, sent))
            
            # Sort by score and take top sentences
            scored_sentences.sort(reverse=True)
            top_sentences = [sent for score, sent in scored_sentences[:3]]  # Take top 3 sentences
            
            # If we don't have enough good sentences, take the first few unique ones
            if len(top_sentences) < 2:
                top_sentences = unique_sentences[:3]
            
            # Combine into excerpt
            excerpt = '. '.join(top_sentences)
            if excerpt and not excerpt.endswith('.'):
                excerpt += '.'
            
            return excerpt
            
        except Exception as e:
            logger.error(f"❌ Error in advanced processing: {e}")
            return f"{original_title}. Latest news update."
    
    def _score_sentence(self, sentence: str, title: str) -> float:
        """Score a sentence based on relevance and quality"""
        try:
            score = 0.0
            
            # Length score (prefer medium-length sentences)
            word_count = len(sentence.split())
            if 10 <= word_count <= 30:
                score += 0.3
            elif 5 <= word_count <= 50:
                score += 0.1
            
            # Title relevance (sentences that mention key terms from title)
            title_words = set(title.lower().split())
            sentence_words = set(sentence.lower().split())
            common_words = title_words.intersection(sentence_words)
            if common_words:
                score += 0.2 * (len(common_words) / len(title_words))
            
            # Avoid boilerplate and navigation
            boilerplate_terms = ['share', 'save', 'follow', 'subscribe', 'newsletter', 'advertisement', 'click here', 'read more', 'photograph:', 'view image', 'skip to', 'sign up', 'follow our']
            if not any(term in sentence.lower() for term in boilerplate_terms):
                score += 0.2
            
            # Prefer sentences with key news indicators
            news_indicators = ['announced', 'reported', 'said', 'according to', 'revealed', 'confirmed', 'warned', 'urged', 'called for', 'told', 'stated', 'explained']
            if any(indicator in sentence.lower() for indicator in news_indicators):
                score += 0.3
            
            # Prefer sentences with quotes or direct speech
            if '"' in sentence or "'" in sentence:
                score += 0.2
            
            # Avoid repetitive phrases and low-quality content
            words = sentence.lower().split()
            word_counts = Counter(words)
            unique_ratio = len(set(words)) / len(words) if words else 0
            score += 0.1 * unique_ratio
            
            # Penalize very short or very long sentences
            if word_count < 5 or word_count > 100:
                score -= 0.2
            
            return max(0.0, score)  # Ensure non-negative score
            
        except Exception as e:
            logger.error(f"❌ Error scoring sentence: {e}")
            return 0.0
    
    def _post_process_summary(self, summary: str) -> str:
        """Post-process to remove redundancy and enforce word limits"""
        try:
            # Clean up the summary
            summary = summary.strip()
            
            # Remove common artifacts
            summary = re.sub(r'^(Summary:|Key points:|Excerpt:)', '', summary, flags=re.IGNORECASE)
            summary = summary.strip()
            
            # Tokenize and count words
            words = summary.split()
            word_count = len(words)
            
            # Calculate target range (85-115 words with 15% tolerance)
            min_words = int(self.target_words * (1 - self.tolerance))
            max_words = int(self.target_words * (1 + self.tolerance))
            
            if word_count > max_words:
                # Truncate intelligently by sentences
                sentences = re.split(r'[.!?]+', summary)
                sentences = [s.strip() for s in sentences if s.strip()]
                current_words = []
                for sent in sentences:
                    sent_words = sent.split()
                    if len(current_words) + len(sent_words) <= max_words:
                        current_words.extend(sent_words)
                    else:
                        break
                summary = ' '.join(current_words)
                if summary and not summary.endswith('.'):
                    summary += '.'
            
            elif word_count < min_words:
                # Add context if too short
                summary += " Additional details available in the full article."
            
            # Check for redundancy (repeated phrases)
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
            sentences = re.split(r'[.!?]+', excerpt)
            sentences = [s.strip() for s in sentences if s.strip()]
            if len(sentences) > 1:
                # Calculate sentence length diversity
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
