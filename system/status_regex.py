import re
from typing import Dict, Optional, List, Tuple

class StatusBlockProcessor:
    def __init__(self):
        self.status_pattern = re.compile(r'<StatusBlock>(.*?)</StatusBlock>', re.DOTALL)
        self.last_status = {}
        
    def process_text(self, text: str, show_status: bool = False) -> Tuple[str, Optional[str]]:
        if not text:
            return text, None
            
        match = self.status_pattern.search(text)
        if not match:
            return text, None
            
        status_content = match.group(1).strip()
        
        processed_text = self.status_pattern.sub('', text).strip()
        
        if show_status:
            return processed_text, status_content
        else:
            return processed_text, None
            
    def save_status(self, user_id: str, status_content: str):
        self.last_status[user_id] = status_content
        
    def get_last_status(self, user_id: str) -> Optional[str]:
        return self.last_status.get(user_id) 