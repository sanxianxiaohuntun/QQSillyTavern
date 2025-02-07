import os
import yaml
import json
from typing import Dict, List, Tuple
from pkg.provider.entities import Message
from datetime import datetime
from collections import Counter
import re
from pkg.provider.modelmgr.modelmgr import ModelManager

class Memory:
    def __init__(self, character_path: str, ap=None):
        self.character_path = character_path
        self.short_term_file = os.path.join(character_path, "short_term.json")
        self.long_term_file = os.path.join(character_path, "long_term.json")
        self.config_file = os.path.join(character_path, "config.yaml")
        self.config = self._load_default_config()
        self._tags_index = {}
        self.ap = ap
        self.debug_mode = False
        if self.ap and hasattr(self.ap, 'debug_mode'):
            self.debug_mode = self.ap.debug_mode
            
    def debug_print(self, *args, **kwargs):
        if self.debug_mode:
            print(*args, **kwargs)

    def _load_default_config(self) -> Dict:
        default_config = {
            "enabled": True,
            "short_term_limit": 50,
            "summary_batch_size": 30,
            "max_tags": 20,
            "summary_prompt": """请总结以下对话的主要内容：
{conversations}

总结要求：
1. 长度控制在200字以内
2. 保留重要的事实和情感
3. 使用第三人称叙述
4. 时态使用过去式""",
            "tags_prompt": """请从以下对话中提取关键词和主题标签：
{content}

提取要求：
1. 每个标签限制在1-4个字
2. 提取人物、地点、时间、事件、情感等关键信息
3. 标签之间用逗号分隔
4. 总数不超过{max_tags}个
5. 直接返回标签列表，不要其他解释"""
        }

        if not os.path.exists(self.config_file):
            default_config_str = """enabled: true
short_term_limit: 50
summary_batch_size: 30
max_tags: 20
summary_prompt: |
  请总结以下对话的主要内容：
  {conversations}
  
  总结要求：
  1. 长度控制在200字以内
  2. 保留重要的事实和情感
  3. 使用第三人称叙述
  4. 时态使用过去式
tags_prompt: |
  请从以下对话中提取关键词和主题标签：
  {content}
  
  提取要求：
  1. 每个标签限制在1-4个字
  2. 提取人物、地点、时间、事件、情感等关键信息
  3. 标签之间用逗号分隔
  4. 总数不超过{max_tags}个
  5. 直接返回标签列表，不要其他解释"""

            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    f.write(default_config_str)
                print(f"已创建默认配置文件: {self.config_file}")
            except Exception as e:
                print(f"创建配置文件失败: {e}")
                return default_config
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if not config:
                    print(f"配置文件为空，使用默认配置")
                    return default_config
                
                for key, value in default_config.items():
                    if key not in config:
                        print(f"配置项 {key} 不存在，使用默认值")
                        config[key] = value
                    elif not config[key]:
                        print(f"配置项 {key} 的值为空，使用默认值")
                        config[key] = value
                
                return config
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            return default_config

    def get_short_term(self) -> List[Message]:
        if not os.path.exists(self.short_term_file):
            print(f"短期记忆文件不存在: {self.short_term_file}")
            return []
        try:
            with open(self.short_term_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = []
                for msg in data:
                    message = Message(
                        role=msg["role"],
                        content=msg["content"]
                    )
                    if "timestamp" in msg:
                        message.timestamp = msg["timestamp"]
                    messages.append(message)
                print(f"\n=== 读取短期记忆 ===")
                print(f"读取位置: {self.short_term_file}")
                print(f"消息数量: {len(messages)}")
                if messages:
                    print(f"最后一条消息: [{messages[-1].role}] {messages[-1].content[:50]}...")
                return messages
        except Exception as e:
            print(f"读取短期记忆失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_long_term(self) -> List[Dict]:
        if not os.path.exists(self.long_term_file):
            return []
        try:
            with open(self.long_term_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取长期记忆失败: {e}")
            return []

    def save_short_term(self, messages: List[Message]):
        try:
            os.makedirs(os.path.dirname(self.short_term_file), exist_ok=True)
            
            data = []
            for msg in messages:
                msg_dict = {
                    "role": msg.role,
                    "content": msg.content
                }
                if hasattr(msg, 'timestamp'):
                    msg_dict["timestamp"] = msg.timestamp
                data.append(msg_dict)
            
            with open(self.short_term_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"\n=== 保存短期记忆 ===")
            print(f"保存位置: {self.short_term_file}")
            print(f"消息数量: {len(messages)}")
            if messages:
                print(f"最后一条消息: [{messages[-1].role}] {messages[-1].content[:50]}...")
        except Exception as e:
            print(f"保存短期记忆失败: {e}")
            import traceback
            traceback.print_exc()

    def save_long_term(self, memories: List[Dict]):
        try:
            with open(self.long_term_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存长期记忆失败: {e}")

    async def add_message(self, message: Message):
        if not self.config["enabled"]:
            return
            
        messages = self.get_short_term()
        
        messages.append(message)
        
        print(f"\n=== 添加新消息 ===")
        print(f"消息角色: {message.role}")
        print(f"消息内容: {message.content}")
        print(f"消息时间: {message.timestamp if hasattr(message, 'timestamp') else '无'}")
        print(f"当前短期记忆数量: {len(messages)}")
        
        self.save_short_term(messages)
        
        if len(messages) >= self.config["short_term_limit"]:
            print(f"短期记忆达到上限({self.config['short_term_limit']})，开始总结...")
            await self._summarize_memories()

    async def _extract_tags(self, content: str) -> List[str]:
        if not self.ap:
            print("警告: Application 实例未设置，无法使用大模型")
            return self._generate_time_tags()
            
        if "tags_prompt" not in self.config:
            print("警告: 配置文件中缺少 tags_prompt")
            return self._generate_time_tags()
            
        try:
            prompt = """请从以下对话中提取关键词和主题标签：
{content}

提取要求：
1. 每个标签限制在1-4个字
2. 提取人物、地点、时间、事件、情感等关键信息
3. 标签之间用英文逗号分隔
4. 总数必须是50个标签
5. 每个标签必须独立，不能包含换行符
6. 直接返回标签列表，不要其他解释
7. 如果内容不足以提取50个标签，可以通过细化和延伸相关概念来补充"""

            prompt = prompt.format(content=content)
        except Exception as e:
            print(f"构建提示词失败: {e}")
            return self._generate_time_tags()
        
        try:
            model = await self.ap.model_mgr.get_model_by_name(self.ap.provider_cfg.data.get("model", "gpt-3.5-turbo"))
            response = await model.requester.call(query=None, model=model, messages=[Message(role="user", content=prompt)])
            tags_str = response.content if response else ""
            
            tags = []
            for tag in tags_str.split(','):
                tag = tag.strip()
                if tag and '\n' not in tag:
                    tags.append(tag)
                    
            if len(tags) < 50:
                tags.extend(self._generate_time_tags())
                generic_tags = ["对话", "交流", "互动", "沟通", "表达", "理解", "关心", "回应", 
                              "聆听", "分享", "陪伴", "支持", "鼓励", "安慰", "信任", "真诚"]
                tags.extend(generic_tags[:50 - len(tags)])
            
            tags = tags[:50]
            
            return list(dict.fromkeys(tags))
        except Exception as e:
            print(f"生成标签失败: {e}")
            return self._generate_time_tags()

    def _generate_time_tags(self) -> List[str]:
        now = datetime.now()
        
        period = "上午" if now.hour < 12 else "下午"
        
        tags = [
            f"{now.year}年",
            f"{now.month}月",
            f"{now.day}日",
            period
        ]
        
        return tags

    async def _summarize_memories(self):
        if not self.ap:
            print("警告: Application 实例未设置，无法使用大模型")
            return
            
        print("\n=== 开始总结记忆 ===")
        
        messages = self.get_short_term()
        memories = self.get_long_term()
        
        print(f"当前短期记忆数量: {len(messages)}")
        print(f"当前长期记忆数量: {len(memories)}")
        
        batch_size = self.config["summary_batch_size"]
        to_summarize = messages[:batch_size]
        
        print(f"本次将总结 {len(to_summarize)} 条消息")
        
        conversations = []
        for msg in to_summarize:
            role = "用户" if msg.role == "user" else "助手"
            conversations.append(f"{role}: {msg.content}")
            
        conversations_text = "\n".join(conversations)
            
        prompt = self.config["summary_prompt"].format(
            conversations=conversations_text
        )
        
        try:
            model = await self.ap.model_mgr.get_model_by_name(self.ap.provider_cfg.data.get("model", "gpt-3.5-turbo"))
            response = await model.requester.call(query=None, model=model, messages=[Message(role="user", content=prompt)])
            summary_content = response.content if response else "对话总结生成失败"
            
            print("\n[生成的总结]")
            print(summary_content)
            
            tags = await self._extract_tags(conversations_text)
            
            print("\n[提取的标签]")
            print(", ".join(tags))
            
            summary = {
                "time": datetime.now().isoformat(),
                "content": summary_content,
                "tags": tags,
                "original": [msg.dict() for msg in to_summarize]
            }
            
            memories.append(summary)
            self.save_long_term(memories)
            
            remaining_messages = messages[batch_size:]
            print(f"\n保留 {len(remaining_messages)} 条消息在短期记忆中")
            self.save_short_term(remaining_messages)
            
        except Exception as e:
            print(f"生成总结失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def clear_all(self):
        print("\n=== 清空所有记忆 ===")
        
        try:
            if os.path.exists(self.character_path):
                for filename in os.listdir(self.character_path):
                    if filename.endswith('.json'):
                        file_path = os.path.join(self.character_path, filename)
                        try:
                            os.remove(file_path)
                            print(f"已删除记忆文件: {file_path}")
                        except Exception as e:
                            print(f"删除文件 {file_path} 失败: {e}")
                print(f"已清理角色目录: {self.character_path}")
        except Exception as e:
            print(f"清理角色目录失败: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            self.save_short_term([])
            self.save_long_term([])
            print("已清空内存中的记忆")
        except Exception as e:
            print(f"清空内存记忆失败: {e}")
            import traceback
            traceback.print_exc()
            
        print("=== 记忆清空完成 ===\n") 