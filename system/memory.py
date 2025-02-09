import os
import yaml
import json
import asyncio
from typing import Dict, List, Tuple, Any, Optional
from pkg.provider.entities import Message
from datetime import datetime
from collections import Counter
import re
from pkg.provider.modelmgr.modelmgr import ModelManager

class Memory:
    def __init__(self, character_path: str, host):
        """
        初始化记忆管理器
        :param character_path: 角色目录路径
        :param host: Application 实例
        """
        self.character_path = character_path
        self.short_term_file = os.path.join(character_path, "short_term.json")
        self.long_term_file = os.path.join(character_path, "long_term.json")
        self.config_file = os.path.join(character_path, "memory_config.yaml")
        self.config = self._load_default_config()
        self._tags_index = {}  # 标签索引
        self.host = host  # 保存 Application 实例
        self.debug_mode = False
        if self.host and hasattr(self.host, 'debug_mode'):
            self.debug_mode = self.host.debug_mode
            
        # 添加并发控制
        self.locks = {}  # 用于存储每个会话的锁
        self.semaphores = {}  # 用于存储每个会话的信号量
            
    def get_session_key(self, is_group: bool, session_id: str) -> str:
        """
        获取会话的唯一标识符
        :param is_group: 是否是群聊
        :param session_id: 会话ID（群号或用户ID）
        :return: 会话的唯一标识符
        """
        return f"{'group' if is_group else 'person'}_{session_id}"
            
    async def get_session_lock(self, is_group: bool, session_id: str) -> asyncio.Lock:
        """
        获取会话的锁
        :param is_group: 是否是群聊
        :param session_id: 会话ID（群号或用户ID）
        :return: 会话的锁
        """
        session_key = self.get_session_key(is_group, session_id)
        if session_key not in self.locks:
            self.locks[session_key] = asyncio.Lock()
        return self.locks[session_key]
            
    async def get_session_semaphore(self, is_group: bool, session_id: str, max_concurrent: int = 5) -> asyncio.Semaphore:
        """
        获取会话的信号量
        :param is_group: 是否是群聊
        :param session_id: 会话ID（群号或用户ID）
        :param max_concurrent: 最大并发数
        :return: 会话的信号量
        """
        session_key = self.get_session_key(is_group, session_id)
        if session_key not in self.semaphores:
            self.semaphores[session_key] = asyncio.Semaphore(max_concurrent)
        return self.semaphores[session_key]
            
    def debug_print(self, *args, **kwargs):
        """调试信息打印函数"""
        if self.debug_mode:
            print(*args, **kwargs)

    def _load_default_config(self) -> Dict[str, Any]:
        """加载或创建默认配置"""
        default_config = {
            "enabled": True,
            "short_term_limit": 20,  # 短期记忆上限
            "summary_batch_size": 10,  # 触发总结的消息数量
            "max_memory": 100,  # 长期记忆上限
            "max_concurrent": 5,  # 每个会话的最大并发数
            "summary_prompt": """
请总结以下对话内容的关键信息。总结应该：
1. 提取重要的事件、情感变化和关系发展
2. 识别对话中的主要主题和关键词
3. 保留时间和上下文信息

请按以下格式输出：
{
    "summary": "总结内容",
    "tags": ["标签1", "标签2", ...],  # 用于后续检索的关键词标签
    "time": "总结时间"
}
"""
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    # 合并配置，保留默认值
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                print(f"加载配置失败: {e}")
                
        # 如果加载失败或文件不存在，保存并返回默认配置
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(default_config, f, allow_unicode=True)
        return default_config

    async def get_short_term(self, is_group: bool = False, session_id: str = None) -> List[Message]:
        """获取短期记忆"""
        if session_id:
            # 使用会话锁来保护文件访问
            async with await self.get_session_lock(is_group, session_id):
                if not os.path.exists(self.short_term_file):
                    return []
                    
                try:
                    with open(self.short_term_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return [Message(**msg) for msg in data]
                except Exception as e:
                    print(f"读取短期记忆失败: {e}")
                    return []
        else:
            # 向后兼容的旧方法
            if not os.path.exists(self.short_term_file):
                return []
                
            try:
                with open(self.short_term_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [Message(**msg) for msg in data]
            except Exception as e:
                print(f"读取短期记忆失败: {e}")
                return []

    async def save_short_term(self, messages: List[Message], is_group: bool = False, session_id: str = None):
        """保存短期记忆"""
        if session_id:
            # 使用会话锁来保护文件访问
            async with await self.get_session_lock(is_group, session_id):
                os.makedirs(os.path.dirname(self.short_term_file), exist_ok=True)
                with open(self.short_term_file, 'w', encoding='utf-8') as f:
                    json.dump([msg.__dict__ for msg in messages], f, ensure_ascii=False, indent=2)
        else:
            # 向后兼容的旧方法
            os.makedirs(os.path.dirname(self.short_term_file), exist_ok=True)
            with open(self.short_term_file, 'w', encoding='utf-8') as f:
                json.dump([msg.__dict__ for msg in messages], f, ensure_ascii=False, indent=2)

    async def get_long_term(self, is_group: bool = False, session_id: str = None) -> List[Dict[str, Any]]:
        """获取长期记忆"""
        if session_id:
            # 使用会话锁来保护文件访问
            async with await self.get_session_lock(is_group, session_id):
                if not os.path.exists(self.long_term_file):
                    return []
                    
                try:
                    with open(self.long_term_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"读取长期记忆失败: {e}")
                    return []
        else:
            # 向后兼容的旧方法
            if not os.path.exists(self.long_term_file):
                return []
                
            try:
                with open(self.long_term_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"读取长期记忆失败: {e}")
                return []

    async def save_long_term(self, memories: List[Dict[str, Any]], is_group: bool = False, session_id: str = None):
        """保存长期记忆"""
        if session_id:
            # 使用会话锁来保护文件访问
            async with await self.get_session_lock(is_group, session_id):
                os.makedirs(os.path.dirname(self.long_term_file), exist_ok=True)
                with open(self.long_term_file, 'w', encoding='utf-8') as f:
                    json.dump(memories, f, ensure_ascii=False, indent=2)
        else:
            # 向后兼容的旧方法
            os.makedirs(os.path.dirname(self.long_term_file), exist_ok=True)
            with open(self.long_term_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)

    async def add_message(self, message: Message, is_group: bool = False, session_id: str = None):
        """添加新消息到短期记忆"""
        if not self.config["enabled"]:
            return
            
        if session_id:
            # 使用会话的信号量控制并发
            async with await self.get_session_semaphore(is_group, session_id):
                messages = await self.get_short_term(is_group, session_id)
                messages.append(message)
                
                # 如果超过上限，保留最新的消息
                if len(messages) > self.config["short_term_limit"]:
                    messages = messages[-self.config["short_term_limit"]:]
                    
                await self.save_short_term(messages, is_group, session_id)
        else:
            # 向后兼容的旧方法
            messages = await self.get_short_term()
            messages.append(message)
            
            # 如果超过上限，保留最新的消息
            if len(messages) > self.config["short_term_limit"]:
                messages = messages[-self.config["short_term_limit"]:]
                
            await self.save_short_term(messages)

    async def get_relevant_memories(self, current_context: str, is_group: bool = False, session_id: str = None, max_memories: int = 3) -> List[Dict[str, Any]]:
        """
        根据当前上下文获取相关的长期记忆
        :param current_context: 当前上下文
        :param is_group: 是否是群聊
        :param session_id: 会话ID
        :param max_memories: 最大返回记忆数量
        :return: 相关的长期记忆列表
        """
        long_term = await self.get_long_term(is_group, session_id)
        if not long_term:
            return []
            
        # 从当前上下文中提取关键词
        keywords = set(current_context.lower().split())
        
        # 计算每条记忆的相关性得分
        scored_memories = []
        for memory in long_term:
            score = 0
            # 检查标签匹配
            memory_tags = set(tag.lower() for tag in memory.get('tags', []))
            matching_tags = keywords & memory_tags
            score += len(matching_tags) * 2  # 标签匹配权重更高
            
            # 检查内容匹配
            memory_content = memory.get('summary', '').lower()
            matching_words = keywords & set(memory_content.split())
            score += len(matching_words)
            
            if score > 0:
                scored_memories.append((score, memory))
        
        # 按相关性排序并返回前N条记忆
        scored_memories.sort(reverse=True)
        return [memory for _, memory in scored_memories[:max_memories]]

    async def _summarize_memories(self):
        """总结短期记忆并添加到长期记忆"""
        if not self.config["enabled"]:
            return
            
        messages = await self.get_short_term()
        if len(messages) < self.config["summary_batch_size"]:
            return
            
        # 准备要总结的消息
        messages_to_summarize = []
        for msg in messages:
            messages_to_summarize.append({
                "role": msg.role,
                "content": msg.content,
                "time": msg.timestamp if hasattr(msg, 'timestamp') else datetime.now().isoformat()
            })
        
        # 构建更清晰的总结提示词
        prompt = """请总结以下对话内容的关键信息。你的回复必须是一个有效的JSON格式，包含以下字段：
- summary: 总结的主要内容
- tags: 关键词标签数组
- time: 总结时间（将自动填充，你可以省略）

示例格式：
{
    "summary": "用户和助手讨论了...",
    "tags": ["话题1", "话题2", "情感1"],
    "time": "2024-01-01T00:00:00"
}

请直接返回JSON，不要添加任何其他格式标记（如```json）。

对话内容：
"""
        
        for msg in messages_to_summarize:
            prompt += f"[{msg['role']}] {msg['content']}\n"
        
        try:
            # 检查host和application的可用性
            if not self.host:
                print("警告: host对象不可用，无法执行记忆总结")
                return
            
            if not hasattr(self.host, 'ap'):
                print("警告: application对象不可用，无法执行记忆总结")
                return
            
            if not hasattr(self.host.ap, 'model_mgr'):
                print("警告: 模型管理器不可用，无法执行记忆总结")
                return
            
            # 获取当前使用的模型
            model = await self.host.ap.model_mgr.get_model_by_name(
                self.host.ap.provider_cfg.data.get("model", "gpt-3.5-turbo")
            )
            
            # 创建一个消息列表
            prompt_messages = [
                Message(role="user", content=prompt)
            ]
            
            # 调用模型进行总结
            response = await model.requester.call(
                query=None,
                model=model,
                messages=prompt_messages
            )
            
            if not response or not response.content:
                print("总结失败：未获得AI回复")
                return
            
            # 清理和解析AI的总结结果
            try:
                # 清理回复内容，移除可能的格式标记
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                # 尝试解析JSON
                summary_data = json.loads(content)
                
                if not isinstance(summary_data, dict):
                    raise ValueError("总结结果必须是一个JSON对象")
                    
                # 确保必要的字段存在
                if "summary" not in summary_data:
                    raise ValueError("总结结果缺少 'summary' 字段")
                if "tags" not in summary_data:
                    raise ValueError("总结结果缺少 'tags' 字段")
                if not isinstance(summary_data["tags"], list):
                    raise ValueError("'tags' 字段必须是一个数组")
                    
                # 添加或更新时间戳和content字段
                summary_data["time"] = datetime.now().isoformat()
                summary_data["content"] = summary_data["summary"]  # 确保content字段存在
                
                # 保存到长期记忆
                long_term = await self.get_long_term()
                long_term.append(summary_data)
                
                # 如果超过上限，移除最旧的记忆
                if len(long_term) > self.config["max_memory"]:
                    long_term = long_term[-self.config["max_memory"]:]
                    
                await self.save_long_term(long_term)
                
                # 清空已总结的短期记忆
                remaining_messages = messages[len(messages_to_summarize):]
                await self.save_short_term(remaining_messages)
                
                print(f"记忆总结成功，标签: {', '.join(summary_data['tags'])}")
                
            except json.JSONDecodeError as e:
                print(f"解析总结结果失败: {e}")
                print(f"清理后的内容: {content}")
                return
            except ValueError as e:
                print(f"总结结果格式错误: {e}")
                print(f"清理后的内容: {content}")
                return
                
        except Exception as e:
            print(f"总结过程出错: {e}")
            return

    def clear_all(self):
        """清空所有记忆"""
        # 清空短期记忆
        if os.path.exists(self.short_term_file):
            os.remove(self.short_term_file)
            
        # 清空长期记忆
        if os.path.exists(self.long_term_file):
            os.remove(self.long_term_file)

    async def _extract_tags(self, content: str) -> List[str]:
        """从内容中提取标签"""
        if not self.host:
            print("警告: Application 实例未设置，无法使用大模型")
            return self._generate_time_tags()
            
        if "tags_prompt" not in self.config:
            print("警告: 配置文件中缺少 tags_prompt")
            return self._generate_time_tags()
            
        # 构建标签提取提示词
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
        
        # 使用大模型生成标签
        try:
            model = await self.host.model_mgr.get_model_by_name(self.host.provider_cfg.data.get("model", "gpt-3.5-turbo"))
            response = await model.requester.call(query=None, model=model, messages=[Message(role="user", content=prompt)])
            tags_str = response.content if response else ""
            
            # 分割标签并清理
            tags = []
            for tag in tags_str.split(','):
                tag = tag.strip()
                if tag and '\n' not in tag:  # 确保标签不包含换行符
                    tags.append(tag)
                    
            # 如果标签数量不足50个，添加时间标签和一些通用标签来补充
            if len(tags) < 50:
                tags.extend(self._generate_time_tags())
                # 添加一些通用标签直到达到50个
                generic_tags = ["对话", "交流", "互动", "沟通", "表达", "理解", "关心", "回应", 
                              "聆听", "分享", "陪伴", "支持", "鼓励", "安慰", "信任", "真诚"]
                tags.extend(generic_tags[:50 - len(tags)])
            
            # 如果超过50个，只保留前50个
            tags = tags[:50]
            
            # 去重
            return list(dict.fromkeys(tags))
        except Exception as e:
            print(f"生成标签失败: {e}")
            return self._generate_time_tags()  # 至少返回时间标签

    def _generate_time_tags(self) -> List[str]:
        """生成时间相关的标签"""
        now = datetime.now()
        
        # 确定时间段
        period = "上午" if now.hour < 12 else "下午"
        
        # 生成标签
        tags = [
            f"{now.year}年",
            f"{now.month}月",
            f"{now.day}日",
            period
        ]
        
        return tags 