import os
import json
from typing import List, Dict, Any, Tuple
from pkg.provider.entities import Message
import math

class WorldBookEntry:
    def __init__(self, data: Dict[str, Any]):
        self.uid = data.get('uid', 0)
        self.comment = data.get('comment', '')
        self.content = data.get('content', '')
        self.constant = data.get('constant', False)
        self.key = self._parse_keys(data.get('key', []))
        self.enabled = not data.get('disable', False)
        
        self.order = data.get('order', 100)
        self.probability = data.get('probability', 100)
        self.depth = data.get('depth', 4)
        self.group = data.get('group', '')
        
    def _parse_keys(self, keys) -> List[str]:
        if isinstance(keys, str):
            return [k.strip() for k in keys.split('，') if k.strip()]
        elif isinstance(keys, list):
            result = []
            for key in keys:
                if isinstance(key, str):
                    result.extend([k.strip() for k in key.split('，') if k.strip()])
                else:
                    result.append(str(key))
            return result
        return []

    def matches_keywords(self, text: str) -> bool:
        if not self.enabled:
            return False
        return any(keyword in text for keyword in self.key)

    def get_display_info(self, show_keywords: bool = False) -> str:
        status = "✓" if self.enabled else "✗"
        if show_keywords and self.key:
            return f"[{status}] {self.comment} (关键词: {', '.join(self.key)})"
        return f"[{status}] {self.comment}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'uid': self.uid,
            'key': self.key,
            'keysecondary': [],
            'comment': self.comment,
            'content': self.content,
            'constant': self.constant,
            'vectorized': False,
            'selective': True,
            'selectiveLogic': 0,
            'addMemo': True,
            'order': self.order,
            'position': 4,
            'disable': not self.enabled,
            'excludeRecursion': False,
            'preventRecursion': False,
            'delayUntilRecursion': False,
            'probability': self.probability,
            'useProbability': True,
            'depth': self.depth,
            'group': self.group,
            'groupOverride': False,
            'groupWeight': 100,
            'scanDepth': None,
            'caseSensitive': None,
            'matchWholeWords': None,
            'useGroupScoring': None,
            'automationId': '',
            'role': 0,
            'sticky': 0,
            'cooldown': 0,
            'delay': 0,
            'displayIndex': self.uid
        }

class WorldBookProcessor:
    def __init__(self, plugin_dir: str):
        self.world_book_dir = os.path.join(plugin_dir, "shijieshu")
        self.entries: List[WorldBookEntry] = []
        self.ENTRIES_PER_PAGE = 30
        self.debug_mode = False
        self._load_world_books()

    def debug_print(self, *args, **kwargs):
        if self.debug_mode:
            print(*args, **kwargs)
            
    def set_debug_mode(self, debug: bool):
        self.debug_mode = debug

    def _load_world_books(self):
        if not os.path.exists(self.world_book_dir):
            os.makedirs(self.world_book_dir)
            print(f"创建世界书目录: {self.world_book_dir}")
            return

        self.entries = []
        
        for filename in os.listdir(self.world_book_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.world_book_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if not isinstance(data, dict) or 'entries' not in data:
                            print(f"无效的世界书格式 {filename}")
                            continue
                            
                        entries_data = data['entries']
                        self.debug_print(f"\n加载世界书: {filename}")
                        self.debug_print(f"发现 {len(entries_data)} 条条目")
                        
                        for entry_id, entry_data in entries_data.items():
                            try:
                                entry = WorldBookEntry(entry_data)
                                self.entries.append(entry)
                            except Exception as e:
                                print(f"处理条目失败 {filename}#{entry_id}: {e}")
                                continue
                                
                except Exception as e:
                    print(f"加载世界书 {filename} 失败: {e}")
                    continue

        self.entries.sort(key=lambda x: x.uid)
        self.debug_print(f"\n总共加载了 {len(self.entries)} 条世界书条目")

    def _save_world_books(self):
        try:
            entries_by_file = {}
            
            for filename in os.listdir(self.world_book_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.world_book_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and 'entries' in data:
                            entries_by_file[filename] = data
            
            for entry in self.entries:
                found = False
                for filename, data in entries_by_file.items():
                    if str(entry.uid) in data['entries']:
                        data['entries'][str(entry.uid)] = entry.to_dict()
                        found = True
                        break
                
                if not found:
                    if entries_by_file:
                        first_file = next(iter(entries_by_file))
                        entries_by_file[first_file]['entries'][str(entry.uid)] = entry.to_dict()
            
            for filename, data in entries_by_file.items():
                file_path = os.path.join(self.world_book_dir, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
            self.debug_print(f"已保存世界书更改到原始文件")
            
        except Exception as e:
            print(f"保存世界书失败: {e}")
            import traceback
            traceback.print_exc()

    def get_entries_by_type(self, constant: bool = True, page: int = 1) -> Tuple[List[WorldBookEntry], int]:
        filtered_entries = [entry for entry in self.entries if entry.constant == constant]
        
        total_pages = math.ceil(len(filtered_entries) / self.ENTRIES_PER_PAGE)
        
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * self.ENTRIES_PER_PAGE
        end_idx = start_idx + self.ENTRIES_PER_PAGE
        current_page_entries = filtered_entries[start_idx:end_idx]
        
        return current_page_entries, total_pages

    def process_messages(self, messages: List[Message]) -> List[str]:
        inserted_contents = []

        constant_entries = [entry for entry in self.entries if entry.constant and entry.enabled]
        inserted_contents.extend(entry.content for entry in constant_entries)

        if messages:
            all_text = " ".join(msg.content for msg in messages)
            
            keyword_entries = [entry for entry in self.entries if not entry.constant and entry.enabled]
            for entry in keyword_entries:
                if entry.matches_keywords(all_text):
                    inserted_contents.append(entry.content)

        return inserted_contents

    def get_world_book_prompt(self, messages: List[Message]) -> List[Message]:
        contents = self.process_messages(messages)
        if not contents:
            return []

        world_book_text = "\n".join([
            "# 世界设定",
            *contents
        ])

        return [Message(role="system", content=world_book_text)]

    def add_entry(self, entry_data: Dict[str, Any]) -> WorldBookEntry:
        next_uid = max((entry.uid for entry in self.entries), default=-1) + 1
        entry_data['uid'] = next_uid
        
        entry = WorldBookEntry(entry_data)
        self.entries.append(entry)
        
        self.entries.sort(key=lambda x: x.uid)
        self._save_world_books()
        
        return entry

    def update_entry(self, entry_id: int, entry_data: Dict[str, Any]) -> bool:
        if 0 <= entry_id < len(self.entries):
            entry_data['uid'] = self.entries[entry_id].uid
            self.entries[entry_id] = WorldBookEntry(entry_data)
            self._save_world_books()
            return True
        return False

    def delete_entry(self, entry_id: int) -> bool:
        if 0 <= entry_id < len(self.entries):
            self.entries.pop(entry_id)
            self._save_world_books()
            return True
        return False

    def enable_entry(self, entry_id: int) -> bool:
        if 0 <= entry_id < len(self.entries):
            self.entries[entry_id].enabled = True
            self._save_world_books()
            return True
        return False

    def disable_entry(self, entry_id: int) -> bool:
        if 0 <= entry_id < len(self.entries):
            self.entries[entry_id].enabled = False
            self._save_world_books()
            return True
        return False 