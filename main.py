from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from .system.image_processor import ImageProcessor
from .system.chat_manager import ChatManager
from .pojia.pojia_mode import PoJiaModePlugin
import os
import yaml
from .system.regex_processor import RegexProcessor
from .system.user_manager import UserManager
from .system.memory import Memory
from datetime import datetime
from pkg.provider.entities import Message
from .system.world_book_processor import WorldBookProcessor
from typing import Dict, Any, Callable, Awaitable, Optional, List

# 通用错误处理装饰器
def error_handler(func):
    async def wrapper(self, ctx: EventContext, *args, **kwargs):
        try:
            return await func(self, ctx, *args, **kwargs)
        except Exception as e:
            error_msg = f"执行 {func.__name__} 时发生错误: {str(e)}"
            print(error_msg)
            ctx.add_return("reply", [error_msg])
            ctx.prevent_default()
    return wrapper

# 状态检查装饰器
def require_tavern_enabled(func):
    async def wrapper(self, ctx: EventContext, *args, **kwargs):
        user_id = ctx.event.sender_id
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
            ctx.prevent_default()
            return
        return await func(self, ctx, *args, **kwargs)
    return wrapper

# 命令处理器基类
class CommandBase:
    def __init__(self):
        self.commands: Dict[str, Callable[[EventContext], Awaitable[None]]] = {}
        
    def register(self, command: str, handler: Callable[[EventContext], Awaitable[None]]):
        """注册命令处理器"""
        self.commands[command] = handler
        
    async def handle(self, ctx: EventContext, msg: str) -> bool:
        """处理命令，返回是否是命令"""
        for cmd, handler in self.commands.items():
            if msg.startswith(cmd):
                await handler(ctx)
                return True
        return False

# 注册插件
@register(name="QQSillyTavern（QQ酒馆）", description="QQ酒馆聊天插件", version="0.1", author="小馄饨")
class TavernPlugin(BasePlugin, CommandBase):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        BasePlugin.__init__(self, host)
        CommandBase.__init__(self)
        self.started_users = set()
        self.user_manager = None
        self.chat_manager = None
        self.world_book_processor = None
        self.pojia_plugin = None
        self.debug_mode = False
        
        # 加载配置
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.debug_mode = config.get('system', {}).get('debug', False)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
        
        self.enabled_users = set()  # 初始化启用用户集合
        self.selecting_users = set()  # 正在选择角色的用户
        self.current_page = {}  # 用户当前查看的角色页面
        self.image_processor = ImageProcessor()  # 创建图片处理器实例
        
        # 初始化用户管理器
        self.user_manager = UserManager(os.path.dirname(__file__))
        
        # 初始化聊天管理器
        self.chat_manager = ChatManager()
        self.chat_manager.set_debug_mode(self.debug_mode)
        self.chat_manager.plugin = self  # 设置插件实例引用
        
        # 初始化世界设定处理器
        self.world_book_processor = WorldBookProcessor(os.path.dirname(__file__))
        
        # 初始化破甲插件
        self.pojia_plugin = PoJiaModePlugin(self.host, self.chat_manager, self.user_manager)
        
        # 加载正则规则
        regex_rules = {}
        try:
            regex_path = os.path.join(os.path.dirname(__file__), "regex_rules.yaml")
            with open(regex_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                regex_rules = config.get('rules', {})
                self.regex_enabled = config.get('enabled', True)
        except Exception as e:
            print(f"加载正则规则失败: {e}")
            self.regex_enabled = False
            regex_rules = {}
            
        self.regex_processor = RegexProcessor(regex_rules, self.regex_enabled)
        
        self._register_commands()

    def _register_commands(self):
        """注册所有命令"""
        # 基础命令
        self.register("/帮助", self._send_help_message)
        self.register("/开启酒馆", self._handle_enable_tavern)
        self.register("/关闭酒馆", self._handle_disable_tavern)
        self.register("/开始", self._handle_start_command)
        
        # 角色系统命令
        self.register("/角色", self._handle_character_command)
        
        # 记忆系统命令
        self.register("/记忆", self._handle_memory_command)
        
        # 世界书命令
        self.register("/世界书", self._handle_world_book_command)
        
        # 破甲模式命令
        self.register("/破甲", self._handle_pojia_command)
        
        # 用户预设命令
        self.register("/设定我的个人资料", self._handle_set_preset)
        
    def debug_print(self, *args, **kwargs):
        """调试信息打印函数"""
        if self.debug_mode:
            print(*args, **kwargs)

    # 异步初始化
    async def initialize(self):
        """异步初始化"""
        # 初始化用户管理器
        self.user_manager = UserManager(os.path.dirname(__file__))
        
        # 初始化聊天管理器
        self.chat_manager = ChatManager()
        self.chat_manager.set_debug_mode(self.debug_mode)
        
        # 初始化世界设定处理器
        self.world_book_processor = WorldBookProcessor(os.path.dirname(__file__))
        
        # 初始化破甲插件
        self.pojia_plugin = PoJiaModePlugin(self.host, self.chat_manager, self.user_manager)
        
        # 初始化破甲模式
        await self.pojia_plugin.initialize()
        
        # 自动转换角色卡
        try:
            count, converted = self.image_processor.convert_all_character_cards()
            if count > 0:
                self.ap.logger.info(f"成功转换 {count} 个角色卡")
                self.ap.logger.info(f"转换的角色: {', '.join(converted)}")
            else:
                self.ap.logger.info("没有找到需要转换的角色卡")
        except Exception as e:
            self.ap.logger.error(f"角色卡转换失败: {e}")

    @handler(PersonNormalMessageReceived)
    async def handle_person_message(self, ctx: EventContext):
        """处理私聊消息"""
        user_id = ctx.event.sender_id
        message = ctx.event.text_message.strip()
        
        # 检查是否在设置个人资料流程中
        setting_history_key = f"setting_profile_{user_id}"
        in_setting = hasattr(self, setting_history_key)
        
        # 如果是设置命令或在设置流程中，由设置处理器处理
        if message.startswith("/设定我的个人资料") or in_setting:
            await self._handle_set_preset(ctx)
            ctx.prevent_default()
            return
        
        # 如果是命令，交给命令处理器处理
        if message.startswith('/'):
            await self._handle_message(ctx)
            return
            
        # 如果用户在选择角色状态
        if user_id in self.selecting_users:
            # 如果输入是数字，调用角色选择处理
            if message.isdigit():
                await self._handle_character_selection(ctx, message)
            else:
                # 非数字输入时提示用户
                ctx.add_return("reply", ["请输入数字选择角色，或使用 /帮助 查看帮助"])
                ctx.prevent_default()
            return
            
        # 如果用户未启用酒馆，忽略消息
        if user_id not in self.enabled_users:
            return
            
        # 处理正常对话消息
        await self._handle_chat_message(ctx)

    @handler(GroupNormalMessageReceived)
    async def handle_group_message(self, ctx: EventContext):
        """处理群聊消息"""
        user_id = ctx.event.sender_id
        message = ctx.event.text_message.strip()
        
        # 如果是命令，交给命令处理器处理
        if message.startswith('/'):
            await self._handle_message(ctx)
            return
            
        # 如果用户在选择角色状态
        if user_id in self.selecting_users:
            # 如果输入是数字，调用角色选择处理
            if message.isdigit():
                await self._handle_character_selection(ctx, message)
            else:
                # 非数字输入时提示用户
                ctx.add_return("reply", ["请输入数字选择角色，或使用 /帮助 查看帮助"])
                ctx.prevent_default()
            return

        # 如果用户未启用酒馆，忽略消息
        if user_id not in self.enabled_users:
            return
            
        # 处理正常对话消息
        await self._handle_chat_message(ctx)

    @handler(PromptPreProcessing)
    async def handle_prompt(self, ctx: EventContext):
        """处理提示词注入"""
        if not hasattr(ctx.event, 'query'):
            return
        
        user_id = ctx.event.query.sender_id if hasattr(ctx.event.query, "sender_id") else None
        if not user_id:
            return
            
        # 检查是否在设置个人资料流程中
        setting_history_key = f"setting_profile_{user_id}"
        in_setting = hasattr(self, setting_history_key)
        
        # 获取用户消息
        user_message = None
        if hasattr(ctx.event.query, 'user_message'):
            msg = ctx.event.query.user_message
            if isinstance(msg.content, list) and msg.content and hasattr(msg.content[0], 'text'):
                user_message = msg.content[0].text
            else:
                user_message = str(msg.content)
                
        # 如果是命令或者在设置个人资料流程中，不处理消息
        if user_message and (user_message.startswith("/") or in_setting):
            ctx.event.default_prompt = []  # 清空系统提示词
            ctx.event.prompt = []  # 清空历史消息
            return  # 直接返回，不进行后续的记忆处理
        
        # 只有在酒馆模式开启时才处理提示词
        if user_id not in self.enabled_users:
            return
            
        # 获取会话类型
        is_group = ctx.event.query.launcher_type == "group" if hasattr(ctx.event.query, "launcher_type") else False
            
        # 获取用户设定的名字
        user_name = "我"
        try:
            preset = self.user_manager.get_user_preset(user_id, is_group)
            if preset:
                import yaml
                preset_data = yaml.safe_load(preset)
                if preset_data and "user_profile" in preset_data:
                    user_name = preset_data["user_profile"].get("name", "我")
        except Exception as e:
            print(f"获取用户名失败: {e}")
            
        # 获取当前角色名
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        try:
            # 如果有用户消息，记录到记忆系统
            if user_message:
                # 替换消息中的{{user}}为用户名和{{char}}为角色名
                user_message = user_message.replace("{{user}}", user_name).replace("{{char}}", current_character)
                
                # 记录到聊天管理器（保留完整消息）
                self.chat_manager.add_message(user_id, "user", user_message)
                
                # 记录到记忆系统（保留完整消息）
                character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
                memory = Memory(character_path, self.host)
                await memory.add_message(Message(
                    role="user",
                    content=user_message,
                    timestamp=datetime.now().isoformat()
                ), is_group=is_group, session_id=str(user_id))
            
            # 从记忆系统中读取历史消息
            character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
            memory = Memory(character_path, self.host)
            
            # 获取短期记忆和相关的长期记忆
            try:
                short_term = await memory.get_short_term(is_group=is_group, session_id=str(user_id))
                if not isinstance(short_term, list):
                    print("警告: short_term 不是列表类型")
                    short_term = []
            except Exception as e:
                print(f"获取短期记忆失败: {e}")
                short_term = []
            
            # 获取相关的长期记忆
            relevant_memories = []
            if user_message:
                try:
                    relevant_memories = await memory.get_relevant_memories(user_message, is_group=is_group, session_id=str(user_id))
                except Exception as e:
                    print(f"获取相关记忆失败: {e}")
            
            # 获取用户预设
            user_preset = self.user_manager.get_user_preset(user_id, is_group)
            
            # 构建新的会话
            if user_id in self.pojia_plugin.enabled_users:
                # 破甲模式下，让破甲模式处理提示词
                await self.pojia_plugin.handle_prompt(ctx)
            else:
                # 普通模式下，使用普通提示词
                ctx.event.default_prompt = []  # 清空系统提示词
                ctx.event.prompt = []  # 清空历史消息
                
                # 1. 添加用户预设
                if user_preset:
                    ctx.event.default_prompt.append(Message(
                        role="system",
                        content=f"# 用户信息\n{user_preset}"
                    ))
                
                # 2. 添加角色设定
                try:
                    juese_dir = os.path.join(os.path.dirname(__file__), "juese")
                    char_file = os.path.join(juese_dir, f"{current_character}.yaml")
                    if os.path.exists(char_file):
                        with open(char_file, 'r', encoding='utf-8') as f:
                            character_data = yaml.safe_load(f)
                            ctx.event.default_prompt.append(Message(
                                role="system",
                                content=f"你将扮演如下：\n{yaml.dump(character_data, allow_unicode=True, sort_keys=False)}"
                            ))
                    else:
                        print(f"角色卡文件不存在: {char_file}")
                except Exception as e:
                    print(f"读取角色卡失败: {e}")
                
                # 3. 添加世界书设定
                try:
                    world_book_prompt = self.world_book_processor.get_world_book_prompt(short_term)
                    if world_book_prompt:
                        ctx.event.default_prompt.extend(world_book_prompt)
                except Exception as e:
                    print(f"处理世界书设定失败: {e}")
                
                # 4. 添加相关的长期记忆
                if relevant_memories:
                    memory_text = "# 相关的历史记忆\n"
                    for memory in relevant_memories:
                        memory_text += f"- {memory['time']}: {memory['summary']}\n"
                        memory_text += f"  标签: {', '.join(memory['tags'])}\n\n"
                    ctx.event.default_prompt.append(Message(
                        role="system",
                        content=memory_text
                    ))
                
                # 5. 添加短期记忆
                if short_term:
                    ctx.event.prompt.extend(short_term)

            # 打印调试信息
            print("\n[最终提示词]")
            for msg in ctx.event.default_prompt:
                print(f"[{msg.role}] {msg.content}")
            if ctx.event.prompt:
                print("\n[对话历史]")
                for msg in ctx.event.prompt:
                    print(f"[{msg.role}] {msg.content}")
            print("=" * 50)
            
        except Exception as e:
            print(f"处理提示词时发生错误: {e}")
            import traceback
            traceback.print_exc()

    @handler(NormalMessageResponded)
    async def handle_response(self, ctx: EventContext):
        """处理大模型的回复"""
        user_id = ctx.event.sender_id
        if user_id not in self.enabled_users:
            return

        is_group = ctx.event.launcher_type == "group"
        response = ctx.event.response_text
        
        # 设置当前用户ID用于状态处理
        self._current_user_id = user_id

        # 获取当前角色名
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        # 替换回复中的{{char}}为角色名
        response = response.replace("{{char}}", current_character)

        # 记录到聊天管理器（保留完整消息）
        self.chat_manager.add_message(user_id, "assistant", response)
        
        # 记录到记忆系统（保留完整消息）
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        # 添加带时间戳的助手回复
        await memory.add_message(Message(
            role="assistant",
            content=response,
            timestamp=datetime.now().isoformat()
        ), is_group=is_group, session_id=str(user_id))

        # 检查是否需要进行记忆总结
        messages = await memory.get_short_term(is_group=is_group, session_id=str(user_id))
        if len(messages) >= memory.config["short_term_limit"]:
            try:
                await memory._summarize_memories()
                print(f"已为用户 {user_id} 总结记忆")
            except Exception as e:
                print(f"记忆总结失败: {e}")

        # 处理消息用于显示（移除状态块）
        display_message = self._process_message_for_display(response)
        
        # 更新返回消息
        ctx.event.response_text = display_message

    async def _handle_message(self, ctx: EventContext):
        """统一的消息处理逻辑"""
        msg = ctx.event.text_message
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"

        # 处理开启/关闭酒馆命令
        if msg == "/开启酒馆":
            if user_id in self.enabled_users:
                ctx.add_return("reply", ["酒馆已经开启啦~"])
                ctx.prevent_default()
                return
                
            # 启用酒馆
            self.enabled_users.add(user_id)
            self.chat_manager.clear_history(user_id)  # 清空历史记录
            
            welcome_text = [
                "🏰 欢迎来到温馨的酒馆! 🏰",
                "\n这里是一个充满故事与欢笑的地方，让我来为您介绍一下:",
                "• 您可以与角色进行自然的对话和互动",
                "• 角色会记住您们之间的对话和情感交流",
                "• 您可以随时使用 /帮助 查看更多功能",
                "\n为了获得更好的体验，建议您:",
                "1. 使用 /设定我的个人资料 来介绍一下自己",
                "2. 给角色一些时间来了解您",
                "3. 保持真诚和友善的态度",
                "4. /角色 列表 查看角色列表",
                "\n/开始 立刻开始和角色对话。 🌟"
            ]
            ctx.add_return("reply", ["\n".join(welcome_text)])
            ctx.prevent_default()
            return
        elif msg == "/关闭酒馆":
            if user_id in self.enabled_users:
                self.enabled_users.remove(user_id)
                self.chat_manager.clear_history(user_id)  # 清空历史记录
                
                # 如果用户在破甲模式中，也要关闭破甲模式
                if user_id in self.pojia_plugin.enabled_users:
                    self.pojia_plugin.enabled_users.remove(user_id)
                
                ctx.add_return("reply", ["酒馆已关闭"])
            else:
                ctx.add_return("reply", ["酒馆本来就是关闭的呢"])
            ctx.prevent_default()
            return

        # 只有在酒馆开启时才处理其他命令和消息
        if user_id not in self.enabled_users:
            if msg.startswith("/"):
                ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
                ctx.prevent_default()
            return

        # 处理其他命令
        if await self.handle(ctx, msg):
            return

        # 应用正则处理，只用于显示
        processed_msg = self.regex_processor.process_text(msg)
        if processed_msg != msg:
            ctx.add_return("reply", [f"[处理后的消息]\n{processed_msg}"])

    async def _send_help_message(self, ctx: EventContext):
        """发送帮助信息"""
        help_text = [
            "🏰 酒馆系统命令指南 🏰",
            "\n### 基础命令",
            "```",
            "/开启酒馆 - 启动插件并进入酒馆",
            "/关闭酒馆 - 关闭插件",
            "/帮助 - 显示此帮助信息",
            "/开始 - 开始与角色对话",
            "```",
            "\n### 角色系统命令",
            "```",
            "/角色 列表 - 显示所有可用角色",
            "/角色 切换 <名称> - 切换到指定角色",
            "/角色 当前 - 显示当前角色信息",
            "```",
            "\n### 记忆系统命令",
            "```",
            "/记忆 历史 <数量> - 设置保留对话轮数",
            "/记忆 清空历史 - 清空历史对话",
            "/记忆 撤回 - 撤回最后一条消息",
            "/记忆 重新生成 - 重新生成最后回复",
            "/记忆 上限 <数量> - 设置最大记忆数",
            "/记忆 间隔 <数量> - 设置总结间隔",
            "/记忆 状态 - 查看当前记忆配置",
            "/记忆 清空记忆 - 清空所有长期记忆",
            "```",
            "\n### 世界书命令",
            "```",
            "/世界书 常开 [页码] - 查看常开条目\n"
            "/世界书 关键词调动 [页码] - 查看关键词条目\n"
            "/世界书 禁用 常开条目 <序号> - 禁用指定常开条目\n"
            "/世界书 禁用 关键词条目 <序号> - 禁用指定关键词条目\n"
            "/世界书 启用 常开条目 <序号> - 启用指定常开条目\n"
            "/世界书 启用 关键词条目 <序号> - 启用指定关键词条目",
            "```",
            "\n### 破甲模式命令",
            "```",
            "/破甲 开启 - 使用默认配置开启 - gemini模板\n"
            "/破甲 开启 claude - 使用Claude模板\n"
            "/破甲 开启 deepseek - 使用DeepSeek模板\n"
            "/破甲 关闭 - 关闭破甲模式\n"
            "/破甲 状态 - 查看当前配置",
            "```",
            "\n💡 使用说明：",
            "1. 首次使用请先输入 /开启酒馆",
            "2. 使用 /设定我的个人资料 设置你的称呼和性格",
            "3. 选择一个角色后使用 /开始 开始对话",
            "4. 在开始对话前，只能使用命令，不能直接对话",
            "5. 可以随时使用 /帮助 查看此指南"
        ]
        
        ctx.add_return("reply", ["\n".join(help_text)])
        ctx.prevent_default()

    async def _handle_enable_tavern(self, ctx: EventContext):
        """处理开启酒馆命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        if user_id in self.enabled_users:
            ctx.add_return("reply", ["酒馆已经开启啦~"])
            ctx.prevent_default()
            return
            
        # 启用酒馆
        self.enabled_users.add(user_id)
        self.chat_manager.clear_history(user_id)  # 清空历史记录
        
        welcome_text = [
            "🏰 欢迎来到温馨的酒馆! 🏰",
            "\n在开始愉快的对话之前，请先完成以下步骤：",
            "1. 使用 /设定我的个人资料 介绍一下你自己",
            "   - 这将帮助角色更好地了解你",
            "   - 包括你希望的称呼、性别和性格特点",
            "",
            "2. 使用 /角色 列表 选择一个你感兴趣的角色",
            "   - 可以输入数字快速选择",
            "   - 也可以使用 /角色 切换 <名称> 指定角色",
            "",
            "3. 使用 /开始 开始与角色对话",
            "   - 在此之前只能使用命令",
            "   - 开始后就可以自由对话了",
            "",
            "💡 可以随时使用 /帮助 查看完整的功能指南",
            "现在，让我们开始准备吧！"
        ]
        
        ctx.add_return("reply", ["\n".join(welcome_text)])
        ctx.prevent_default()

    async def _handle_disable_tavern(self, ctx: EventContext):
        """处理关闭酒馆命令"""
        user_id = ctx.event.sender_id
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["酒馆本来就是关闭的呢"])
            ctx.prevent_default()
            return
            
        # 从各种状态集合中移除用户
        self.enabled_users.remove(user_id)
        if user_id in self.started_users:
            self.started_users.remove(user_id)
        if user_id in self.selecting_users:
            self.selecting_users.remove(user_id)
        if user_id in self.current_page:
            del self.current_page[user_id]
        
        # 清空聊天历史
        self.chat_manager.clear_history(user_id)
        
        # 如果用户在破甲模式中，也要关闭破甲模式
        if user_id in self.pojia_plugin.enabled_users:
            self.pojia_plugin.enabled_users.remove(user_id)
        
        # 重置系统的聊天记录
        if hasattr(ctx.event, 'query'):
            if hasattr(ctx.event.query, 'session'):
                # 清空会话
                ctx.event.query.session = None
                
            if hasattr(ctx.event.query, 'messages'):
                # 清空消息历史
                ctx.event.query.messages = []
                
            if hasattr(ctx.event.query, 'history'):
                # 清空历史记录
                ctx.event.query.history = []
        
        ctx.add_return("reply", ["酒馆已关闭，下次进入可以重新选择角色"])
        ctx.prevent_default()

    def _process_message_for_display(self, message: str, show_status: bool = False) -> str:
        """处理消息用于显示"""
        if not message:
            return message
            
        # 处理状态块
        processed_text, status_content = self.regex_processor.process_status_block(message, show_status)
        
        # 如果有状态块内容，保存它
        if status_content:
            user_id = getattr(self, '_current_user_id', None)
            if user_id:
                self.regex_processor.save_status(user_id, status_content)
        
        return processed_text.strip()

    async def _handle_start_command(self, ctx: EventContext):
        """处理开始命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
            ctx.prevent_default()
            return
            
        if user_id in self.started_users:
            ctx.add_return("reply", ["你已经开始对话了"])
            ctx.prevent_default()
            return
            
        # 获取当前选择的角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        if current_character == "default":
            ctx.add_return("reply", ["请先使用 /角色列表 命令选择一个角色"])
            ctx.prevent_default()
            return
            
        # 将用户添加到已开始列表
        self.started_users.add(user_id)
        
        # 设置当前用户ID用于状态处理
        self._current_user_id = user_id
        
        # 获取用户设定的名字
        user_name = "我"
        try:
            preset = self.user_manager.get_user_preset(user_id, is_group)
            if preset:
                import yaml
                preset_data = yaml.safe_load(preset)
                if preset_data and "user_profile" in preset_data:
                    user_name = preset_data["user_profile"].get("name", "我")
        except Exception as e:
            print(f"获取用户名失败: {e}")
            
        # 获取角色目录路径
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        # 获取记忆中的最后一条消息
        messages = await memory.get_short_term(is_group=is_group, session_id=str(user_id))
        last_message = None
        if messages:
            for msg in reversed(messages):
                if msg.role == "assistant":
                    last_message = msg.content
                    break
        
        # 如果没有找到最后的消息，尝试从角色卡获取first_mes
        if not last_message:
            try:
                character_file = os.path.join(os.path.dirname(__file__), "juese", f"{current_character}.yaml")
                if os.path.exists(character_file):
                    with open(character_file, 'r', encoding='utf-8') as f:
                        char_data = yaml.safe_load(f)
                        last_message = char_data.get('first_mes', "开始啦~和我对话吧。")
                else:
                    last_message = "开始啦~和我对话吧。"
            except Exception as e:
                print(f"读取角色卡失败: {e}")
                last_message = "开始啦~和我对话吧。"
        
        # 替换消息中的{{user}}为用户名
        last_message = last_message.replace("{{user}}", user_name)
        
        # 记录系统的首条消息到记忆（保留完整消息）
        if last_message:
            await memory.add_message(Message(
                role="assistant",
                content=last_message,
                timestamp=datetime.now().isoformat()
            ), is_group=is_group, session_id=str(user_id))
        
        # 发送给用户的消息需要处理掉状态块
        display_message = self._process_message_for_display(last_message)
        ctx.add_return("reply", [display_message])
        ctx.prevent_default()

    async def _handle_convert_card(self, ctx: EventContext):
        """处理转换角色卡命令"""
        try:
            count, converted = self.image_processor.convert_all_character_cards()
            if count > 0:
                ctx.add_return("reply", [
                    f"成功转换 {count} 个角色卡\n" +
                    f"转换的角色: {', '.join(converted)}"
                ])
            else:
                ctx.add_return("reply", ["没有找到需要转换的角色卡"])
        except Exception as e:
            ctx.add_return("reply", [f"角色卡转换失败: {str(e)}"])
        ctx.prevent_default()

    async def _handle_memory_status(self, ctx: EventContext):
        """显示记忆系统状态"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前选择的角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        # 读取当前记忆
        short_term = await memory.get_short_term(is_group=is_group, session_id=str(user_id))
        long_term = await memory.get_long_term(is_group=is_group, session_id=str(user_id))
        
        status = [
            "===== 记忆系统状态 =====",
            f"当前角色: {current_character}",
            f"记忆系统: {'启用' if memory.config['enabled'] else '禁用'}",
            f"短期记忆数量: {len(short_term)}/{memory.config['short_term_limit']}",  # short_term 已经是列表了
            f"长期记忆数量: {len(long_term)}",  # long_term 已经是列表了
            f"总结批次大小: {memory.config['summary_batch_size']}",
            "======================="
        ]
        
        ctx.add_return("reply", ["\n".join(status)])
        ctx.prevent_default()

    async def _handle_undo(self, ctx: EventContext):
        """撤回最后一条消息（不管是用户还是助手的消息）"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前选择的角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        # 读取当前短期记忆
        messages = await memory.get_short_term(is_group=is_group, session_id=str(user_id))
        
        if not messages:
            ctx.add_return("reply", ["没有可撤回的消息"])
            ctx.prevent_default()
            return
        
        # 删除最后一条消息
        last_msg = messages.pop()
        
        # 保存更新后的短期记忆
        await memory.save_short_term(messages, is_group=is_group, session_id=str(user_id))
        
        # 同时从聊天管理器中删除最后一条消息
        self.chat_manager.remove_last_message(user_id)
        
        # 根据消息角色显示不同的提示
        role_display = "用户" if last_msg.role == "user" else "助手"
        ctx.add_return("reply", [f"已撤回{role_display}的消息: {last_msg.content}"])
        ctx.prevent_default()

    async def _handle_clear_memory(self, ctx: EventContext):
        """清空所有记忆"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前角色名
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        # 获取角色目录路径
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        print(f"\n=== 清空角色 {current_character} 的记忆 ===")
        print(f"角色目录: {character_path}")
        
        # 清空所有记忆
        memory.clear_all()
        
        # 清空聊天管理器的历史记录
        self.chat_manager.clear_history(user_id)
        
        # 清空当前会话的历史记录
        if hasattr(ctx.event, 'query'):
            if hasattr(ctx.event.query, 'session'):
                # 清空会话
                ctx.event.query.session = None
                
            if hasattr(ctx.event.query, 'messages'):
                # 清空消息历史
                ctx.event.query.messages = []
                
            if hasattr(ctx.event.query, 'history'):
                # 清空历史记录
                ctx.event.query.history = []
        
        ctx.add_return("reply", [f"已清空角色 {current_character} 的所有记忆"])
        ctx.prevent_default()

    async def _handle_force_summary(self, ctx: EventContext):
        """强制执行记忆总结，不管记忆数量多少"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前角色名
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        print("\n=== 强制总结调试信息 ===")
        print(f"用户ID: {user_id}")
        print(f"会话类型: {'群聊' if is_group else '私聊'}")
        print(f"角色名: {current_character}")
        print(f"角色目录: {character_path}")
        
        # 读取当前短期记忆
        messages = await memory.get_short_term(is_group=is_group, session_id=str(user_id))
        print(f"\n[短期记忆状态]")
        print(f"记忆数量: {len(messages)}")
        if messages:
            print("记忆内容:")
            for msg in messages:
                print(f"[{msg.role}] {msg.content}")
        
        if not messages:
            print("没有找到任何短期记忆")
            ctx.add_return("reply", ["没有可总结的记忆"])
            ctx.prevent_default()
            return
        
        # 获取当前所有短期记忆数量
        current_count = len(messages)
        
        # 保存原始配置
        original_batch_size = memory.config["summary_batch_size"]
        original_limit = memory.config["short_term_limit"]
        
        print(f"\n[配置信息]")
        print(f"原始批次大小: {original_batch_size}")
        print(f"原始记忆上限: {original_limit}")
        
        try:
            # 修改配置以强制执行总结
            memory.config["summary_batch_size"] = current_count
            memory.config["short_term_limit"] = 1  # 设置为1确保会触发总结
            
            print(f"\n[修改后配置]")
            print(f"新批次大小: {memory.config['summary_batch_size']}")
            print(f"新记忆上限: {memory.config['short_term_limit']}")
            
            # 执行总结
            print("\n[开始执行总结]")
            await memory._summarize_memories()
            
            # 读取长期记忆看看是否成功添加
            long_term = await memory.get_long_term(is_group=is_group, session_id=str(user_id))
            print(f"\n[长期记忆状态]")
            print(f"长期记忆数量: {len(long_term)}")
            if long_term:
                print("最新的长期记忆:")
                latest = long_term[-1]
                print(f"时间: {latest['time']}")
                print(f"内容: {latest['content']}")
                print(f"标签: {', '.join(latest['tags'])}")
            
            ctx.add_return("reply", [f"已总结 {current_count} 条记忆"])
        except Exception as e:
            print(f"\n[总结过程出错]")
            print(f"错误信息: {str(e)}")
            ctx.add_return("reply", [f"总结过程出错: {str(e)}"])
        finally:
            # 恢复原始配置
            memory.config["summary_batch_size"] = original_batch_size
            memory.config["short_term_limit"] = original_limit
            print("\n[配置已恢复]")
            print("=" * 50)
        
        ctx.prevent_default()

    async def _handle_test(self, ctx: EventContext):
        """测试所有功能"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        character_path = self.user_manager.get_character_path(user_id, "default", is_group)
        memory = Memory(character_path, self.host)
        
        test_results = []
        
        # 1. 测试目录结构
        test_results.append("1. 测试目录结构")
        try:
            user_path = self.user_manager.get_user_path(user_id, is_group)
            test_results.append(f"✓ 用户目录: {user_path}")
            test_results.append(f"✓ 角色目录: {character_path}")
        except Exception as e:
            test_results.append(f"✗ 目录创建失败: {e}")
        
        # 2. 测试配置文件
        test_results.append("\n2. 测试配置文件")
        try:
            if os.path.exists(memory.config_file):
                test_results.append("✓ 配置文件已创建")
                test_results.append(f"✓ 短期记忆上限: {memory.config['short_term_limit']}")
                test_results.append(f"✓ 总结批次大小: {memory.config['summary_batch_size']}")
            else:
                test_results.append("✗ 配置文件不存在")
        except Exception as e:
            test_results.append(f"✗ 配置文件读取失败: {e}")
        
        # 3. 测试记忆系统
        test_results.append("\n3. 测试记忆系统")
        try:
            # 添加测试消息
            test_msg = Message(
                role="user",
                content="这是一条测试消息",
                timestamp=datetime.now().isoformat()
            )
            await memory.add_message(test_msg, is_group=is_group, session_id=str(user_id))
            test_results.append("✓ 消息添加成功")
            
            # 读取短期记忆
            messages = await memory.get_short_term(is_group=is_group, session_id=str(user_id))
            test_results.append(f"✓ 当前短期记忆数量: {len(messages)}")
            
            # 测试保存功能
            await memory.save_short_term(messages, is_group=is_group, session_id=str(user_id))
            test_results.append("✓ 记忆保存成功")
            
            # 验证文件是否存在
            if os.path.exists(memory.short_term_file):
                test_results.append("✓ 短期记忆文件已创建")
            if os.path.exists(memory.long_term_file):
                test_results.append("✓ 长期记忆文件已创建")
            
        except Exception as e:
            test_results.append(f"✗ 记忆系统测试失败: {e}")
        
        # 4. 测试正则处理
        test_results.append("\n4. 测试正则处理")
        try:
            test_text = "这是一个[测试]消息(带表情)"
            processed = self.regex_processor.process_text(test_text)
            if processed != test_text:
                test_results.append("✓ 正则处理正常工作")
                test_results.append(f"原文: {test_text}")
                test_results.append(f"处理后: {processed}")
            else:
                test_results.append("✗ 正则处理未生效")
        except Exception as e:
            test_results.append(f"✗ 正则处理测试失败: {e}")
        
        # 返回测试结果
        ctx.add_return("reply", ["\n".join(test_results)])
        ctx.prevent_default()

    async def _handle_set_preset(self, ctx: EventContext):
        """处理设置用户预设的命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 使用一个专门的键来存储设置过程中的历史记录
        setting_history_key = f"setting_profile_{user_id}"
        setting_history = getattr(self, setting_history_key, [])
        
        # 获取当前输入（去掉命令部分）
        current_input = ctx.event.text_message.replace("/设定我的个人资料", "").strip()
        
        # 如果是新命令，不管之前的状态如何，都重新开始
        if ctx.event.text_message.startswith("/设定我的个人资料"):
            if current_input == "":  # 如果只输入了命令
            # 开始第一步：询问名字
                setting_history = []  # 清空设置历史
                message = "[设置个人资料] 第1步：请问你希望我如何称呼你？"
                setting_history.append({"role": "assistant", "content": message})
                setattr(self, setting_history_key, setting_history)
                ctx.add_return("reply", [message])
                ctx.prevent_default()
                return
            else:  # 如果命令后面带有内容，直接作为名字处理
                # 清空历史并保存名字
                setting_history = []
                setting_history.append({"role": "user", "content": current_input})
                message = f"[设置个人资料] 第2步：{current_input}，请问你的性别是？"
                setting_history.append({"role": "assistant", "content": message})
                setattr(self, setting_history_key, setting_history)
                ctx.add_return("reply", [message])
            ctx.prevent_default()
            return
            
        # 如果没有设置历史记录，说明不是在设置流程中
        if not setting_history:
            return
        
        # 获取最后一个问题
        last_question = setting_history[-1]["content"] if setting_history else ""
        
        # 根据历史记录判断当前步骤
        if "[设置个人资料] 第1步" in last_question:
            # 保存名字，进入第二步
            name = current_input.strip()
            setting_history.append({"role": "user", "content": name})
            message = f"[设置个人资料] 第2步：{name}，请问你的性别是？"
            setting_history.append({"role": "assistant", "content": message})
            setattr(self, setting_history_key, setting_history)
            ctx.add_return("reply", [message])
            ctx.prevent_default()
            
        elif "[设置个人资料] 第2步" in last_question:
            # 保存性别，进入第三步
            gender = current_input.strip()
            setting_history.append({"role": "user", "content": gender})
            message = "[设置个人资料] 第3步：好的，请简单描述一下你的性格特点。"
            setting_history.append({"role": "assistant", "content": message})
            setattr(self, setting_history_key, setting_history)
            ctx.add_return("reply", [message])
            ctx.prevent_default()
            
        elif "[设置个人资料] 第3步" in last_question:
            # 保存性格特点，询问是否需要补充
            personality = current_input.strip()
            setting_history.append({"role": "user", "content": personality})
            message = "[设置个人资料] 第4步：还有什么想要补充的信息吗？(直接输入补充内容，如果没有请输入\"没有\")"
            setting_history.append({"role": "assistant", "content": message})
            setattr(self, setting_history_key, setting_history)
            ctx.add_return("reply", [message])
            ctx.prevent_default()
            
        elif "[设置个人资料] 第4步" in last_question:
            # 完成设置，生成YAML
            additional_info = current_input.strip()
            setting_history.append({"role": "user", "content": additional_info})
            
            # 从设置历史中收集信息
            user_messages = [msg["content"] for msg in setting_history if msg["role"] == "user"]
            name = user_messages[0]
            gender = user_messages[1]
            personality = user_messages[2]
            
            # 生成用户资料YAML
            user_profile = {
                "user_profile": {
                    "name": name,
                    "gender": gender,
                    "personality": personality
                }
            }
            
            # 如果有补充信息且不是"没有"，添加到资料中
            if additional_info and additional_info != "没有":
                user_profile["user_profile"]["additional_info"] = additional_info
            
            # 转换为YAML字符串
            yaml_str = yaml.dump(user_profile, allow_unicode=True, sort_keys=False, default_flow_style=False)
            
            # 生成最终的用户预设文本
            final_preset = f"""# 用户个人资料
{yaml_str}
# 注：以上信息将用于指导AI理解用户背景和互动偏好"""
            
            # 保存用户预设
            if self.user_manager.save_user_preset(user_id, is_group, final_preset):
                response = [
                    "✅ 个人资料设置完成！",
                    "",
                    f"已保存的信息：",
                    f"• 称呼：{name}",
                    f"• 性别：{gender}",
                    f"• 性格特点：{personality}"
                ]
                if additional_info and additional_info != "没有":
                    response.append(f"• 补充信息：{additional_info}")
                response.extend([
                    "",
                    "AI将根据这些信息来更好地理解和回应你。",
                    "如需修改，可以随时重新使用 /设定我的个人资料 命令。",
                    "使用 /帮助 获得帮助信息",
                    "现在输入 /开始，开始与角色对话。"
                ])
                ctx.add_return("reply", ["\n".join(response)])
            else:
                ctx.add_return("reply", ["❌ 个人资料设置失败，请稍后重试"])
            
            # 清空设置历史
            delattr(self, setting_history_key)
            
        ctx.prevent_default()

    async def _handle_status(self, ctx: EventContext):
        """处理状态命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前选择的角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        # 获取最后一个状态块
        last_status = self.regex_processor.get_last_status(user_id)
        
        # 如果没有缓存的状态块，从记忆中读取
        if not last_status:
            # 获取角色目录路径
            character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
            memory = Memory(character_path, self.host)
            
            # 获取短期记忆
            messages = memory.get_short_term()
            
            # 从最新到最旧遍历消息，寻找助手消息中的状态块
            if messages:
                for msg in reversed(messages):
                    if msg.role == "assistant":
                        # 处理消息，提取状态块
                        _, status_content = self.regex_processor.process_status_block(msg.content, show_status=True)
                        if status_content:
                            last_status = status_content
                            # 保存找到的状态块
                            self.regex_processor.save_status(user_id, status_content)
                            break
        
        if last_status:
            ctx.add_return("reply", [
                f"角色 {current_character} 的当前状态：\n{last_status}"
            ])
        else:
            ctx.add_return("reply", [f"角色 {current_character} 暂无状态信息"])
        ctx.prevent_default()

    async def _handle_character_list(self, ctx: EventContext):
        """处理角色列表命令"""
        user_id = ctx.event.sender_id
        
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
            ctx.prevent_default()
            return
            
        if user_id in self.started_users:
            ctx.add_return("reply", ["你已经开始对话了，如需切换角色请先 /关闭酒馆 后重新开启"])
            ctx.prevent_default()
            return
            
        # 获取所有角色
        try:
            juese_dir = os.path.join(os.path.dirname(__file__), "juese")
            yaml_files = [f for f in os.listdir(juese_dir) if f.endswith('.yaml')]
            
            if not yaml_files:
                ctx.add_return("reply", ["暂无可用角色"])
                ctx.prevent_default()
                return
            
            # 获取当前页码
            current_page = self.current_page.get(user_id, 1)
            total_pages = (len(yaml_files) + 99) // 100  # 向上取整，每页100个
            
            # 计算当前页的角色范围
            start_idx = (current_page - 1) * 100
            end_idx = min(start_idx + 100, len(yaml_files))
            current_characters = yaml_files[start_idx:end_idx]
            
            # 构建角色列表显示
            display = [
                "=== 角色列表 ===",
                f"当前第 {current_page}/{total_pages} 页，本页显示 {len(current_characters)} 个角色"
            ]
            
            # 显示角色列表
            for i, char_file in enumerate(current_characters, start=1):
                char_name = os.path.splitext(char_file)[0]
                display.append(f"{i}. {char_name}")
            
            # 添加操作提示
            display.extend([
                "\n=== 操作提示 ===",
                "1. 使用 /角色 第N页 切换到指定页面",
                "2. 直接输入数字(1-100)选择本页角色",
                "3. 选择角色后使用 /开始 开始对话"
            ])
            
            # 将用户添加到选择状态
            self.selecting_users.add(user_id)
            
            ctx.add_return("reply", ["\n".join(display)])
        except Exception as e:
            ctx.add_return("reply", [f"获取角色列表失败: {e}"])
        
        ctx.prevent_default()

    async def _handle_character_command(self, ctx: EventContext):
        """处理角色命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 检查用户是否已启用酒馆
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
            ctx.prevent_default()
            return
            
        # 获取角色列表
        try:
            juese_dir = os.path.join(os.path.dirname(__file__), "juese")
            yaml_files = [f for f in os.listdir(juese_dir) if f.endswith('.yaml')]
            
            if not yaml_files:
                ctx.add_return("reply", ["暂无可用角色"])
                ctx.prevent_default()
                return
                
            # 获取当前页码
            current_page = self.current_page.get(user_id, 1)
            total_pages = (len(yaml_files) + 99) // 100  # 向上取整，每页100个
            
            # 计算当前页的角色范围
            start_idx = (current_page - 1) * 100
            end_idx = min(start_idx + 100, len(yaml_files))
            current_characters = yaml_files[start_idx:end_idx]
            
            # 构建角色列表显示
            display = [
                "=== 角色列表 ===",
                f"当前第 {current_page}/{total_pages} 页，共 {len(yaml_files)} 个角色"
            ]
            
            # 显示角色列表
            for i, char_file in enumerate(current_characters, start=1):
                char_name = os.path.splitext(char_file)[0]
                display.append(f"{i}. {char_name}")
            
            # 添加操作提示
            display.extend([
                "\n=== 操作提示 ===",
                "• 选择角色：直接输入数字(1-100)",
                f"• 翻页命令：/角色 第N页（当前第{current_page}页，共{total_pages}页）",
                "• 选择后输入 /开始 开始对话"
            ])
            
            # 将用户添加到选择状态
            self.selecting_users.add(user_id)
            
            ctx.add_return("reply", ["\n".join(display)])
        except Exception as e:
            ctx.add_return("reply", [f"获取角色列表失败: {e}"])
        
        ctx.prevent_default()

    async def _handle_character_selection(self, ctx: EventContext, selection: str):
        """处理角色选择"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 如果用户不在选择状态，忽略数字输入
        if user_id not in self.selecting_users:
            return
            
        # 阻止数字选择被记录到记忆
        ctx.prevent_default()
        
        # 获取当前页码
        current_page = self.current_page.get(user_id, 1)
        
        # 获取所有角色
        juese_dir = os.path.join(os.path.dirname(__file__), "juese")
        yaml_files = [f for f in os.listdir(juese_dir) if f.endswith('.yaml')]
        total_pages = max(1, (len(yaml_files) + 99) // 100)  # 至少有1页，每页100个
        
        # 处理角色选择
        try:
            selection_num = int(selection)
            if 1 <= selection_num <= 100:  # 修改为1-100
                # 计算实际角色索引
                start_idx = (current_page - 1) * 100  # 每页100个
                actual_idx = start_idx + selection_num - 1
                
                if actual_idx < len(yaml_files):
                    selected_char = os.path.splitext(yaml_files[actual_idx])[0]
                    
                    # 清理旧的记忆和历史记录
                    self.chat_manager.clear_history(user_id)
                    
                    # 确保角色目录存在
                    character_path = self.user_manager.get_character_path(user_id, selected_char, is_group)
                    os.makedirs(character_path, exist_ok=True)
                    
                    # 初始化记忆系统
                    memory = Memory(character_path, self.host)
                    memory.clear_all()  # 清空旧的记忆
                    
                    # 保存选择的角色
                    self.user_manager.save_user_character(user_id, selected_char, is_group)
                    
                    # 清理所有状态
                    if user_id in self.selecting_users:
                        self.selecting_users.remove(user_id)
                    if user_id in self.started_users:
                        self.started_users.remove(user_id)
                    
                    # 返回选择成功消息
                    ctx.add_return("reply", [
                        f"✅ 已切换到角色: {selected_char}\n"
                        "已初始化角色记忆和历史记录\n"
                        "现在请输入 /开始 开始对话"
                    ])
                else:
                    ctx.add_return("reply", ["当前页码下无此角色，请检查输入的数字"])
            else:
                ctx.add_return("reply", [f"请输入1-100之间的数字选择角色，或使用 /角色 第N页 切换页面"])
        except ValueError:
            ctx.add_return("reply", [f"请输入1-100之间的数字选择角色，或使用 /角色 第N页 切换页面"])

    async def _handle_world_book_command(self, ctx: EventContext):
        """处理世界书相关命令"""
        msg = ctx.event.text_message.strip()
        parts = msg.split()
        
        if len(parts) < 2:
            ctx.add_return("reply", [
                "请使用以下格式：\n"
                "/世界书 常开 [页码] - 查看常开条目\n"
                "/世界书 关键词调动 [页码] - 查看关键词条目\n"
                "/世界书 禁用 常开条目 <序号> - 禁用指定常开条目\n"
                "/世界书 禁用 关键词条目 <序号> - 禁用指定关键词条目\n"
                "/世界书 启用 常开条目 <序号> - 启用指定常开条目\n"
                "/世界书 启用 关键词条目 <序号> - 启用指定关键词条目"
            ])
            ctx.prevent_default()
            return
            
        subcommand = parts[1]
        
        if subcommand in ["常开", "关键词调动"]:
            page = 1
            if len(parts) > 2:
                try:
                    page = int(parts[2])
                    if page < 1:
                        ctx.add_return("reply", ["页码必须大于0"])
                        ctx.prevent_default()
                        return
                except ValueError:
                    ctx.add_return("reply", ["页码必须是数字"])
                    ctx.prevent_default()
                    return
            
            is_constant = subcommand == "常开"
            entries, total_pages = self.world_book_processor.get_entries_by_type(is_constant, page)
            
            if page > total_pages:
                ctx.add_return("reply", [f"页码超出范围，最大页码为 {total_pages}"])
                ctx.prevent_default()
                return
            
            if not entries:
                ctx.add_return("reply", [f"没有找到{subcommand}类型的世界书条目"])
                ctx.prevent_default()
                return
                
            # 构建显示信息
            display = [f"=== {subcommand}世界书 ==="]
            for i, entry in enumerate(entries, 1):
                display.append(f"{i}. {entry.get_display_info(not is_constant)}")
                
            # 添加页码信息
            display.extend([
                f"\n=== 第 {page}/{total_pages} 页 ===",
                f"查看其他页请使用：/世界书 {subcommand} <页码>"
            ])
            
            ctx.add_return("reply", ["\n".join(display)])
            ctx.prevent_default()
            return
            
        elif subcommand in ["禁用", "启用"] and len(parts) >= 4:
            entry_type = " ".join(parts[2:-1])  # 获取条目类型（常开条目/关键词条目）
            try:
                entry_num = int(parts[-1])  # 获取序号
            except ValueError:
                ctx.add_return("reply", ["序号必须是数字"])
                ctx.prevent_default()
                return
                
            # 根据类型获取对应的条目列表
            is_constant = entry_type == "常开条目"
            entries, _ = self.world_book_processor.get_entries_by_type(is_constant, 1)
            
            if not entries or entry_num < 1 or entry_num > len(entries):
                ctx.add_return("reply", ["无效的条目序号"])
                ctx.prevent_default()
                return
                
            # 获取要操作的条目
            entry = entries[entry_num - 1]
            
            # 执行启用/禁用操作
            if subcommand == "启用":
                entry.enabled = True
                action = "启用"
            else:
                entry.enabled = False
                action = "禁用"
                
            # 保存更改
            try:
                self.world_book_processor._save_world_books()
                ctx.add_return("reply", [f"已{action}{entry_type} {entry_num}: {entry.comment}"])
            except Exception as e:
                ctx.add_return("reply", [f"保存更改失败: {e}"])
            ctx.prevent_default()
            return
            
        ctx.add_return("reply", ["无效的世界书命令"])
        ctx.prevent_default()

    async def _handle_pojia_command(self, ctx: EventContext):
        """处理破甲模式相关命令"""
        msg = ctx.event.text_message.strip()
        parts = msg.split()
        user_id = ctx.event.sender_id
        
        if len(parts) < 2:
            await self.pojia_plugin._send_help_message(ctx)
            return
            
        subcommand = parts[1]
        
        if subcommand == "开启":
            # 传递完整的命令消息
            await self.pojia_plugin._handle_enable_command(ctx, user_id, msg)
        elif subcommand == "关闭":
            await self.pojia_plugin._handle_disable_command(ctx, user_id)
        elif subcommand == "状态":
            await self.pojia_plugin._handle_status_command(ctx, user_id)
        else:
            await self.pojia_plugin._send_help_message(ctx)
        ctx.prevent_default()

    async def _handle_character_switch(self, ctx: EventContext, character_name: str):
        """处理角色切换命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 检查角色是否存在
        juese_dir = os.path.join(os.path.dirname(__file__), "juese")
        character_file = os.path.join(juese_dir, f"{character_name}.yaml")
        
        if not os.path.exists(character_file):
            ctx.add_return("reply", [f"角色 {character_name} 不存在"])
            ctx.prevent_default()
            return
            
        # 保存用户的角色选择
        self.user_manager.save_user_character(user_id, character_name, is_group)
        
        # 清空聊天历史
        self.chat_manager.clear_history(user_id)
        
        # 提示用户切换成功
        ctx.add_return("reply", [
            f"✅ 已切换到角色: {character_name}\n"
            "已加载该角色的记忆和历史记录\n"
            "请使用 /开始 命令开始新的对话"
        ])
        ctx.prevent_default()

    async def _handle_character_info(self, ctx: EventContext):
        """显示当前角色信息"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        if current_character == "default":
            ctx.add_return("reply", ["当前未选择角色，请使用 /角色 列表 选择一个角色"])
            ctx.prevent_default()
            return
        
        # 获取角色信息
        description = '暂无描述'
        personality = '暂无性格描述'
        try:
            juese_dir = os.path.join(os.path.dirname(__file__), "juese")
            char_file = os.path.join(juese_dir, f"{current_character}.yaml")
            with open(char_file, 'r', encoding='utf-8') as f:
                char_data = yaml.safe_load(f)
                description = char_data.get('description', '暂无描述')
                personality = char_data.get('personality', '暂无性格描述')
        except Exception as e:
            print(f"读取角色信息失败: {e}")
        
        # 获取记忆状态
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        short_term = memory.get_short_term()
        long_term = memory.get_long_term()
        
        # 构建显示信息
        info = [
            f"=== 当前角色信息 ===",
            f"名称：{current_character}",
            f"简介：{description}",
            f"性格：{personality}",
            f"\n记忆状态：",
            f"• 短期记忆：{len(short_term)} 条",
            f"• 长期记忆：{len(long_term)} 条",
            f"\n可使用 /记忆 状态 查看详细记忆信息"
        ]
        
        ctx.add_return("reply", ["\n".join(info)])
        ctx.prevent_default()

    async def _handle_memory_setting(self, ctx: EventContext, setting: str, value: int):
        """处理记忆系统设置"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        # 参数范围检查
        if setting == "历史":
            if value < 1 or value > 1000:
                ctx.add_return("reply", ["历史记忆数量必须在1-100之间"])
                ctx.prevent_default()
                return
            memory.config["short_term_limit"] = value
        elif setting == "上限":
            if value < 1 or value > 1000:
                ctx.add_return("reply", ["记忆上限必须在1-1000之间"])
                ctx.prevent_default()
                return
            memory.config["max_memory"] = value
        elif setting == "间隔":
            if value < 1 or value > memory.config["short_term_limit"]:
                ctx.add_return("reply", [f"总结间隔必须在1-{memory.config['short_term_limit']}之间"])
                ctx.prevent_default()
                return
            memory.config["summary_batch_size"] = value
        
        # 保存配置
        try:
            with open(memory.config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(memory.config, f, allow_unicode=True)
            
            # 重新加载配置
            memory.config = memory._load_default_config()
            
            ctx.add_return("reply", [
                f"已更新{setting}设置为: {value}\n"
                f"当前配置：\n"
                f"• 历史记忆数量：{memory.config['short_term_limit']}\n"
                f"• 记忆上限：{memory.config.get('max_memory', '未设置')}\n"
                f"• 总结间隔：{memory.config['summary_batch_size']}"
            ])
        except Exception as e:
            ctx.add_return("reply", [f"保存配置失败: {e}"])
        
        ctx.prevent_default()

    async def _handle_clear_history(self, ctx: EventContext):
        """清空对话历史"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 清空聊天管理器的历史
        self.chat_manager.clear_history(user_id)
        
        # 清空记忆系统的短期记忆
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        memory.save_short_term([])
        
        ctx.add_return("reply", ["已清空对话历史"])
        ctx.prevent_default()

    async def _handle_regenerate(self, ctx: EventContext):
        """重新生成最后回复"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.host)
        
        # 获取短期记忆
        messages = memory.get_short_term()
        if not messages:
            ctx.add_return("reply", ["没有可重新生成的消息"])
            ctx.prevent_default()
            return
            
        # 删除最后一条助手消息
        for i in range(len(messages)-1, -1, -1):
            if messages[i].role == "assistant":
                messages.pop(i)
                break
        
        # 保存更新后的短期记忆
        memory.save_short_term(messages)
        
        ctx.add_return("reply", ["已删除最后一条回复，请等待重新生成"])
        ctx.prevent_default()

    async def _handle_world_book_list(self, ctx: EventContext, is_common: bool):
        """显示世界书列表"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        # 获取当前角色
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        # 获取世界书条目
        entries = self.world_book_processor.entries
        if not entries:
            ctx.add_return("reply", ["没有找到任何世界书条目"])
            ctx.prevent_default()
            return
            
        # 按constant属性分类
        constant_entries = [e for e in entries if e.constant]
        keyword_entries = [e for e in entries if not e.constant]
        
        # 构建显示信息
        display = [f"=== {current_character} 的世界书 ===\n"]
        
        if constant_entries:
            display.append("【常开条目】")
            for i, entry in enumerate(constant_entries, 1):
                display.append(f"{i}. {entry.get_display_info()}")
            display.append("")
            
        if keyword_entries:
            display.append("【关键词条目】")
            for i, entry in enumerate(keyword_entries, 1):
                display.append(f"{i}. {entry.get_display_info(True)}")
        
        ctx.add_return("reply", ["\n".join(display)])
        ctx.prevent_default()

    async def _handle_world_book_import(self, ctx: EventContext, is_common: bool):
        """导入世界书"""
        # TODO: 实现世界书导入功能
        ctx.add_return("reply", ["世界书导入功能开发中"])
        ctx.prevent_default()

    async def _handle_world_book_export(self, ctx: EventContext, is_common: bool):
        """导出世界书"""
        # TODO: 实现世界书导出功能
        ctx.add_return("reply", ["世界书导出功能开发中"])
        ctx.prevent_default()

    async def _handle_world_book_enable(self, ctx: EventContext, entry_id: int):
        """启用世界书条目"""
        entries = self.world_book_processor.entries
        if not entries or entry_id < 0 or entry_id >= len(entries):
            ctx.add_return("reply", ["无效的条目ID"])
            ctx.prevent_default()
            return
            
        entry = entries[entry_id]
        entry.enabled = True
        ctx.add_return("reply", [f"已启用条目: {entry.comment}"])
        ctx.prevent_default()

    async def _handle_world_book_disable(self, ctx: EventContext, entry_id: int):
        """禁用世界书条目"""
        entries = self.world_book_processor.entries
        if not entries or entry_id < 0 or entry_id >= len(entries):
            ctx.add_return("reply", ["无效的条目ID"])
            ctx.prevent_default()
            return
            
        entry = entries[entry_id]
        entry.enabled = False
        ctx.add_return("reply", [f"已禁用条目: {entry.comment}"])
        ctx.prevent_default()

    async def _handle_world_book_delete(self, ctx: EventContext, entry_id: int):
        """删除世界书条目"""
        entries = self.world_book_processor.entries
        if not entries or entry_id < 0 or entry_id >= len(entries):
            ctx.add_return("reply", ["无效的条目ID"])
            ctx.prevent_default()
            return
            
        entry = entries.pop(entry_id)
        ctx.add_return("reply", [f"已删除条目: {entry.comment}"])
        ctx.prevent_default()

    async def _handle_world_book_view(self, ctx: EventContext, entry_id: int):
        """查看世界书条目详情"""
        entries = self.world_book_processor.entries
        if not entries or entry_id < 0 or entry_id >= len(entries):
            ctx.add_return("reply", ["无效的条目ID"])
            ctx.prevent_default()
            return
            
        entry = entries[entry_id]
        info = [
            f"=== 世界书条目详情 ===",
            f"ID: {entry_id}",
            f"名称: {entry.comment}",
            f"类型: {'常开' if entry.constant else '关键词触发'}",
            f"状态: {'启用' if getattr(entry, 'enabled', True) else '禁用'}"
        ]
        
        if entry.key:
            info.append(f"关键词: {', '.join(entry.key)}")
            
        info.extend([
            f"\n内容:",
            entry.content
        ])
        
        ctx.add_return("reply", ["\n".join(info)])
        ctx.prevent_default()

    # 插件卸载时触发
    def __del__(self):
        pass

    async def _handle_memory_command(self, ctx: EventContext):
        """处理记忆相关命令"""
        msg = ctx.event.text_message.strip()
        parts = msg.split()
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
            ctx.prevent_default()
            return
            
        if len(parts) < 2:
            ctx.add_return("reply", [
                "请使用以下格式：\n"
                "/记忆 历史 <数量> - 设置保留对话轮数\n"
                "/记忆 清空历史 - 清空历史对话\n"
                "/记忆 撤回 - 撤回最后一条消息\n"
                "/记忆 重新生成 - 重新生成最后回复\n"
                "/记忆 上限 <数量> - 设置最大记忆数\n"
                "/记忆 间隔 <数量> - 设置总结间隔\n"
                "/记忆 状态 - 查看当前记忆配置\n"
                "/记忆 清空记忆 - 清空所有长期记忆"
            ])
            ctx.prevent_default()
            return
            
        subcommand = parts[1]
        
        if subcommand == "状态":
            await self._handle_memory_status(ctx)
        elif subcommand == "撤回":
            await self._handle_undo(ctx)
        elif subcommand == "清空记忆":
            await self._handle_clear_memory(ctx)
        elif subcommand == "清空历史":
            await self._handle_clear_history(ctx)
        elif subcommand == "重新生成":
            await self._handle_regenerate(ctx)
        elif subcommand in ["历史", "上限", "间隔"] and len(parts) > 2:
            try:
                value = int(parts[2])
                await self._handle_memory_setting(ctx, subcommand, value)
            except ValueError:
                ctx.add_return("reply", ["数值必须是整数"])
                ctx.prevent_default()
        else:
            ctx.add_return("reply", ["无效的记忆命令"])
        ctx.prevent_default()

    async def _handle_chat_message(self, ctx: EventContext):
        """处理普通对话消息"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        message = ctx.event.text_message.strip()

        # 如果用户未开始对话，提示使用/开始命令
        if user_id not in self.started_users:
            ctx.add_return("reply", ["请输入 /开始 开启对话，在此期间你只能设定个人资料和使用命令"])
            ctx.prevent_default()
            return

        # 应用正则处理，只用于显示
        processed_msg = self.regex_processor.process_text(message)
        if processed_msg != message:
            ctx.add_return("reply", [f"[处理后的消息]\n{processed_msg}"])
            
        # 设置当前用户ID用于状态处理
        self._current_user_id = user_id
