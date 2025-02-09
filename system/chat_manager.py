from pkg.plugin.context import EventContext
from pkg.provider.entities import Message
from typing import Dict, List
import os
import yaml

class ChatManager:
    def __init__(self):
        """初始化聊天管理器"""
        self.history: Dict[str, List[Message]] = {}
        self.debug_mode = False
        
    def set_debug_mode(self, debug: bool):
        """设置调试模式"""
        self.debug_mode = debug
        
    def debug_print(self, *args, **kwargs):
        """调试信息打印函数"""
        if self.debug_mode:
            print(*args, **kwargs)
            
    def add_message(self, user_id: str, role: str, content: str):
        """添加一条消息到历史记录"""
        if user_id not in self.history:
            self.history[user_id] = []
            
        message = Message(role=role, content=content)
        self.history[user_id].append(message)
        
        # 打印调试信息
        self.debug_print(f"\n=== 聊天管理器: 添加消息 ===")
        self.debug_print(f"用户ID: {user_id}")
        self.debug_print(f"角色: {role}")
        self.debug_print(f"内容: {content[:50]}...")
        self.debug_print(f"当前历史记录数量: {len(self.history[user_id])}")
            
    def clear_history(self, user_id: str):
        """清除用户的对话历史"""
        if user_id in self.history:
            self.history[user_id] = []
            print(f"\n=== 聊天管理器: 清空历史记录 ===")
            print(f"用户ID: {user_id}")
            
    def get_history(self, user_id: str) -> List[Message]:
        """获取用户的对话历史"""
        return self.history.get(user_id, [])
        
    async def build_prompt(self, ctx: EventContext, user_id: str) -> List[Message]:
        """构建提示词"""
        try:
            # 从 user_manager 获取当前角色
            is_group = ctx.event.launcher_type == "group" if hasattr(ctx.event, "launcher_type") else False
            current_character = ctx.plugin.user_manager.get_user_character(user_id, is_group)
            
            # 读取当前角色的 YAML 文件
            juese_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "juese")
            char_file = os.path.join(juese_dir, f"{current_character}.yaml")
            
            self.debug_print(f"\n=== 构建提示词 ===")
            self.debug_print(f"用户ID: {user_id}")
            self.debug_print(f"当前角色: {current_character}")
            self.debug_print(f"角色文件: {char_file}")
            
            if not os.path.exists(char_file):
                self.debug_print(f"角色文件不存在")
                return []
                
            with open(char_file, 'r', encoding='utf-8') as f:
                character_data = yaml.safe_load(f)
                
            # 替换角色数据中的 {{char}}
            for key in character_data:
                if isinstance(character_data[key], str):
                    character_data[key] = character_data[key].replace("{{char}}", current_character)
            
            prompt = []
            # 添加角色扮演提示
            prompt.append(Message(
                role="system",
                content="你将扮演如下：\n" + yaml.dump(character_data, allow_unicode=True, sort_keys=False)
            ))
            
            self.debug_print(f"生成的提示词: {prompt[0].content}")
            
            return prompt
        except Exception as e:
            print(f"构建提示词失败: {e}")
            return []

    def remove_last_message(self, user_id: str) -> None:
        """删除用户的最后一条消息（不管是用户还是助手的消息）"""
        if user_id in self.history and self.history[user_id]:
            removed = self.history[user_id].pop()
            print(f"\n=== 聊天管理器: 删除最后一条消息 ===")
            print(f"用户ID: {user_id}")
            print(f"已删除: [{removed.role}] {removed.content[:50]}...") 