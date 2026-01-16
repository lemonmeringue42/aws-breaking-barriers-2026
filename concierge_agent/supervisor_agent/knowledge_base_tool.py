"""
Knowledge Base Tool for Citizens Advice

Queries local and national knowledge bases for Citizens Advice information.
"""

import os
import logging
import boto3
from typing import Optional

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-east-1")
LOCAL_KB_ID = os.getenv("LOCAL_KB_ID", "")
NATIONAL_KB_ID = os.getenv("NATIONAL_KB_ID", "")

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=REGION)


def query_knowledge_base(kb_id: str, query: str, max_results: int = 5) -> str:
    """Query a Bedrock knowledge base and return formatted results."""
    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        )
        
        results = []
        for item in response.get('retrievalResults', []):
            content = item.get('content', {}).get('text', '')
            score = item.get('score', 0)
            location = item.get('location', {})
            
            source = location.get('s3Location', {}).get('uri', 'Unknown source')
            
            results.append({
                'content': content,
                'score': score,
                'source': source
            })
        
        if not results:
            return "No relevant information found in knowledge base."
        
        # Format results
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"[Result {i}] (Relevance: {result['score']:.2f})")
            formatted.append(result['content'])
            formatted.append(f"Source: {result['source']}")
            formatted.append("")
        
        return "\n".join(formatted)
        
    except Exception as e:
        logger.error(f"Error querying knowledge base {kb_id}: {e}")
        return f"Error accessing knowledge base: {str(e)}"


def query_national_kb(query: str) -> str:
    """
    Query the national Citizens Advice knowledge base.
    
    Use this for general UK-wide advice on:
    - Benefits and financial support
    - Employment rights
    - Consumer rights
    - Housing law
    - Debt management
    - Immigration
    
    Args:
        query: The question or topic to search for
        
    Returns:
        Relevant information from the national knowledge base
    """
    if not NATIONAL_KB_ID:
        logger.warning("NATIONAL_KB_ID not configured")
        return "National knowledge base not configured."
    
    logger.info(f"Querying national KB: {query[:100]}...")
    return query_knowledge_base(NATIONAL_KB_ID, query)


def query_local_kb(query: str, region: Optional[str] = None) -> str:
    """
    Query the local Citizens Advice knowledge base.
    
    Use this for region-specific information:
    - Local bureau contact details
    - Regional services and support
    - Local authority specific guidance
    - Area-specific resources
    
    Args:
        query: The question or topic to search for
        region: Optional region to filter results (e.g., "London", "Scotland")
        
    Returns:
        Relevant local information
    """
    if not LOCAL_KB_ID:
        logger.warning("LOCAL_KB_ID not configured")
        return "Local knowledge base not configured."
    
    # Enhance query with region if provided
    enhanced_query = f"{query} {region}" if region else query
    
    logger.info(f"Querying local KB: {enhanced_query[:100]}...")
    return query_knowledge_base(LOCAL_KB_ID, enhanced_query)
