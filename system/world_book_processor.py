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
        self.key = self._parse_keys(data.get('key', []))  # 处理关键词列表
        self.enabled = not data.get('disable', False)  # 从disable字段转换
        
        # 保存其他可能有用的字段
        self.order = data.get('order', 100)
        self.probability = data.get('probability', 100)
        self.depth = data.get('depth', 4)
        self.group = data.get('group', '')
        
    def _parse_keys(self, keys) -> List[str]:
        """处理关键词列表，支持字符串和列表格式"""
        if isinstance(keys, str):
            # 如果是字符串，按逗号分割
            return [k.strip() for k in keys.split('，') if k.strip()]
        elif isinstance(keys, list):
            # 如果是列表，处理每个元素
            result = []
            for key in keys:
                if isinstance(key, str):
                    # 如果元素是字符串，按逗号分割
                    result.extend([k.strip() for k in key.split('，') if k.strip()])
                else:
                    # 其他类型直接转字符串
                    result.append(str(key))
            return result
        return []

    def matches_keywords(self, text: str) -> bool:
        """检查文本是否包含任何关键词"""
        if not self.enabled:  # 如果条目被禁用，不匹配关键词
            return False
        return any(keyword in text for keyword in self.key)

    def get_display_info(self, show_keywords: bool = False) -> str:
        """获取显示信息"""
        status = "✓" if self.enabled else "✗"
        if show_keywords and self.key:
            return f"[{status}] {self.comment} (关键词: {', '.join(self.key)})"
        return f"[{status}] {self.comment}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，保持原始格式"""
        return {
            'uid': self.uid,
            'key': self.key,
            'keysecondary': [],  # 保持原格式
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
        """初始化世界书处理器"""
        self.world_book_dir = os.path.join(plugin_dir, "shijieshu")  # 修正路径
        self.entries: List[WorldBookEntry] = []
        self.ENTRIES_PER_PAGE = 30  # 每页显示的条目数
        self.debug_mode = False
        self._load_world_books()

    def debug_print(self, *args, **kwargs):
        """调试信息打印函数"""
        if self.debug_mode:
            print(*args, **kwargs)
            
    def set_debug_mode(self, debug: bool):
        """设置调试模式"""
        self.debug_mode = debug

    def _load_world_books(self):
        """加载所有世界书文件"""
        if not os.path.exists(self.world_book_dir):
            os.makedirs(self.world_book_dir)
            print(f"创建世界书目录: {self.world_book_dir}")
            return

        # 清空现有条目
        self.entries = []
        
        # 遍历目录下的所有JSON文件
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
                        
                        # 处理每个条目
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

        # 按UID排序
        self.entries.sort(key=lambda x: x.uid)
        self.debug_print(f"\n总共加载了 {len(self.entries)} 条世界书条目")

    def _save_world_books(self):
        """保存世界书条目的更改到原始文件"""
        try:
            # 按文件名组织条目
            entries_by_file = {}
            
            # 遍历目录下的所有JSON文件，读取它们的原始结构
            for filename in os.listdir(self.world_book_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.world_book_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and 'entries' in data:
                            entries_by_file[filename] = data
            
            # 更新每个文件中的条目
            for entry in self.entries:
                # 查找该条目所在的文件
                found = False
                for filename, data in entries_by_file.items():
                    if str(entry.uid) in data['entries']:
                        # 更新条目
                        data['entries'][str(entry.uid)] = entry.to_dict()
                        found = True
                        break
                
                if not found:
                    # 如果是新条目，添加到第一个文件
                    if entries_by_file:
                        first_file = next(iter(entries_by_file))
                        entries_by_file[first_file]['entries'][str(entry.uid)] = entry.to_dict()
            
            # 保存更改到文件
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
        """获取指定类型的条目
        
        Args:
            constant: True获取常开条目，False获取关键词条目
            page: 页码（从1开始）
            
        Returns:
            Tuple[List[WorldBookEntry], int]: 条目列表和总页数
        """
        # 过滤条目
        filtered_entries = [entry for entry in self.entries if entry.constant == constant]
        
        # 计算总页数
        total_pages = math.ceil(len(filtered_entries) / self.ENTRIES_PER_PAGE)
        
        # 确保页码有效
        page = max(1, min(page, total_pages))
        
        # 计算当前页的条目
        start_idx = (page - 1) * self.ENTRIES_PER_PAGE
        end_idx = start_idx + self.ENTRIES_PER_PAGE
        current_page_entries = filtered_entries[start_idx:end_idx]
        
        return current_page_entries, total_pages

    def process_messages(self, messages: List[Message]) -> List[str]:
        """处理消息列表，返回应该插入的世界书内容"""
        inserted_contents = []

        # 首先添加所有constant为true且enabled为true的条目
        constant_entries = [entry for entry in self.entries if entry.constant and entry.enabled]
        inserted_contents.extend(entry.content for entry in constant_entries)

        # 然后检查关键词触发的条目
        if messages:
            # 将所有消息内容合并成一个字符串
            all_text = " ".join(msg.content for msg in messages)
            
            # 检查每个非constant且enabled为true的条目
            keyword_entries = [entry for entry in self.entries if not entry.constant and entry.enabled]
            for entry in keyword_entries:
                if entry.matches_keywords(all_text):
                    inserted_contents.append(entry.content)

        return inserted_contents

    def get_world_book_prompt(self, messages: List[Message]) -> List[Message]:
        """获取世界书提示词"""
        if not messages:
            return []

        # 将所有消息内容合并成一个字符串
        all_text = " ".join(msg.content for msg in messages)
        
        # 获取所有匹配的世界书内容
        contents = []
        
        # 首先添加所有constant为true且enabled为true的条目
        constant_entries = [entry for entry in self.entries if entry.constant and entry.enabled]
        contents.extend(entry.content for entry in constant_entries)

        # 然后检查关键词触发的条目
        keyword_entries = [entry for entry in self.entries if not entry.constant and entry.enabled]
        for entry in keyword_entries:
            if entry.matches_keywords(all_text):
                contents.append(entry.content)

        if not contents:
            return []

        # 将所有内容组合成一个提示词
        world_book_text = "\n".join([
            "# 世界设定",
            *contents
        ])

        return [Message(
            role="system",
            content=world_book_text
        )]

    def add_entry(self, entry_data: Dict[str, Any]) -> WorldBookEntry:
        """添加新条目"""
        # 分配新的UID
        next_uid = max((entry.uid for entry in self.entries), default=-1) + 1
        entry_data['uid'] = next_uid
        
        # 创建新条目
        entry = WorldBookEntry(entry_data)
        self.entries.append(entry)
        
        # 重新排序并保存
        self.entries.sort(key=lambda x: x.uid)
        self._save_world_books()
        
        return entry

    def update_entry(self, entry_id: int, entry_data: Dict[str, Any]) -> bool:
        """更新条目"""
        if 0 <= entry_id < len(self.entries):
            # 保持原有的UID
            entry_data['uid'] = self.entries[entry_id].uid
            self.entries[entry_id] = WorldBookEntry(entry_data)
            self._save_world_books()
            return True
        return False

    def delete_entry(self, entry_id: int) -> bool:
        """删除条目"""
        if 0 <= entry_id < len(self.entries):
            self.entries.pop(entry_id)
            self._save_world_books()
            return True
        return False

    def enable_entry(self, entry_id: int) -> bool:
        """启用条目"""
        if 0 <= entry_id < len(self.entries):
            self.entries[entry_id].enabled = True
            self._save_world_books()
            return True
        return False

    def disable_entry(self, entry_id: int) -> bool:
        """禁用条目"""
        if 0 <= entry_id < len(self.entries):
            self.entries[entry_id].enabled = False
            self._save_world_books()
            return True
        return False 