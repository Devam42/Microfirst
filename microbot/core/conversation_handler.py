"""
Conversation Handler Module
Pure AI-driven conversation processing without pattern matching
"""

from __future__ import annotations
from typing import Optional, Tuple

# Import legacy handlers for table functionality only
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "legacy_code"))

try:
    from ..utils.handlers import parse_table_request, render_table
    from ..utils.persona import childify, looks_serious
except ImportError:
    from handlers import parse_table_request, render_table
    from persona import childify, looks_serious


class ConversationHandler:
    """
    Pure AI-driven conversation handler - no pattern matching
    """
    
    def __init__(self):
        # Only keep table functionality - everything else handled by AI
        pass
    
    def get_special_response(self, user_input: str) -> Optional[str]:
        """
        Get special/deterministic response for user input
        Only handles multiplication tables - everything else goes to AI
        """
        # Only handle table requests - let AI handle everything else
        table_response = self._handle_table_request(user_input)
        if table_response is not None:
            return table_response
        
        # Everything else handled by AI
        return None
    
    def _handle_table_request(self, user_input: str) -> Optional[str]:
        """Handle multiplication table requests"""
        table_request = parse_table_request(user_input)
        if table_request is not None:
            n, upto = table_request
            answer = render_table(n, upto)
            
            # Apply childification if not serious (only for Hinglish)
            if not looks_serious(user_input):
                try:
                    from ..utils import ConfigStore
                    config = ConfigStore()
                    answer = childify(answer, config.language())
                except:
                    answer = childify(answer)
            
            return answer
        
        return None
    
    def is_serious_query(self, user_input: str) -> bool:
        """Check if the query is serious (technical/formal)"""
        return looks_serious(user_input)
    
    def apply_childification(self, text: str) -> str:
        """Apply childification to text"""
        return childify(text)
