from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from .system.image_processor import ImageProcessor
from .system.chat_manager import ChatManager
from .system.command_handler import CommandHandler
from .pojia.pojia_mode import PoJiaModePlugin
import os
import yaml
from .system.regex_processor import RegexProcessor
from .system.user_manager import UserManager
from .system.memory import Memory
from datetime import datetime
from pkg.provider.entities import Message
from .system.status_regex import StatusBlockProcessor
from .system.world_book_processor import WorldBookProcessor


@register(name="QQSillyTavern（QQ酒馆）", description="QQ酒馆聊天插件", version="0.1", author="小馄饨")
class TavernPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.started_users = set()
        self.user_manager = None
        self.chat_manager = None
        self.world_book_processor = None
        self.pojia_plugin = None
        self.status_processor = None
        self.debug_mode = False
        
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.debug_mode = config.get('system', {}).get('debug', False)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
        
        self.enabled_users = set() 
        self.selecting_users = set()
        self.current_page = {}  
        self.image_processor = ImageProcessor() 
        self.user_manager = UserManager(os.path.dirname(__file__))
        self.chat_manager = ChatManager()
        self.chat_manager.set_debug_mode(self.debug_mode)
        self.chat_manager.plugin = self
        self.world_book_processor = WorldBookProcessor(os.path.dirname(__file__))
        self.status_processor = StatusBlockProcessor()
        self.pojia_plugin = PoJiaModePlugin(self.host, self.chat_manager, self.user_manager)
        self.command_handler = CommandHandler()
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
        self.command_handler.register("/帮助", self._send_help_message)
        self.command_handler.register("/开启酒馆", self._handle_enable_tavern)
        self.command_handler.register("/关闭酒馆", self._handle_disable_tavern)
        self.command_handler.register("/开始", self._handle_start_command)
        self.command_handler.register("/角色", self._handle_character_command)
        self.command_handler.register("/记忆", self._handle_memory_command)
        self.command_handler.register("/世界书", self._handle_world_book_command)
        self.command_handler.register("/破甲", self._handle_pojia_command)
        self.command_handler.register("/设定我的个人资料", self._handle_set_preset)
        
    def debug_print(self, *args, **kwargs):
        """调试信息打印函数"""
        if self.debug_mode:
            print(*args, **kwargs)
    async def initialize(self):
        self.user_manager = UserManager(os.path.dirname(__file__))
        self.chat_manager = ChatManager()
        self.chat_manager.set_debug_mode(self.debug_mode)
        self.world_book_processor = WorldBookProcessor(os.path.dirname(__file__))
        self.status_processor = StatusBlockProcessor()
        self.pojia_plugin = PoJiaModePlugin(self.host, self.chat_manager, self.user_manager)
        await self.pojia_plugin.initialize()
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
        setting_history_key = f"setting_profile_{user_id}"
        in_setting = hasattr(self, setting_history_key)
        if message.startswith("/设定我的个人资料") or in_setting:
            await self._handle_set_preset(ctx)
            ctx.prevent_default()
            return
        if message.startswith('/'):
            await self._handle_message(ctx)
            return
        if user_id in self.selecting_users:
            if message.isdigit():
                await self._handle_character_selection(ctx, message)
            else:
                ctx.add_return("reply", ["请输入数字选择角色，或使用 /帮助 查看帮助"])
                ctx.prevent_default()
            return           
        if user_id not in self.enabled_users:
            return
            
        await self._handle_chat_message(ctx)

    @handler(GroupNormalMessageReceived)
    async def handle_group_message(self, ctx: EventContext):
        user_id = ctx.event.sender_id
        message = ctx.event.text_message.strip()
        
        if message.startswith('/'):
            await self._handle_message(ctx)
            return
            
        if user_id in self.selecting_users:
            if message.isdigit():
                await self._handle_character_selection(ctx, message)
            else:
                ctx.add_return("reply", ["请输入数字选择角色，或使用 /帮助 查看帮助"])
                ctx.prevent_default()
            return

        if user_id not in self.enabled_users:
            return
            
        await self._handle_chat_message(ctx)

    @handler(PromptPreProcessing)
    async def handle_prompt(self, ctx: EventContext):
        if not hasattr(ctx.event, 'query'):
            return
        
        user_id = ctx.event.query.sender_id if hasattr(ctx.event.query, "sender_id") else None
        if not user_id:
            return
            
        setting_history_key = f"setting_profile_{user_id}"
        in_setting = hasattr(self, setting_history_key)
        
        user_message = None
        if hasattr(ctx.event.query, 'user_message'):
            msg = ctx.event.query.user_message
            if isinstance(msg.content, list) and msg.content and hasattr(msg.content[0], 'text'):
                user_message = msg.content[0].text
            else:
                user_message = str(msg.content)
                
        if user_message and (user_message.startswith("/") or in_setting):
            ctx.event.default_prompt = []
            ctx.event.prompt = []
            return
        
        if user_id not in self.enabled_users:
            return
            
        is_group = ctx.event.query.launcher_type == "group" if hasattr(ctx.event.query, "launcher_type") else False
            
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
            
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        self.debug_print("\n=== 提示词处理调试信息 ===")
        self.debug_print(f"用户ID: {user_id}")
        self.debug_print(f"当前角色: {current_character}")
        
        if user_message:
            user_message = user_message.replace("{{user}}", user_name).replace("{{char}}", current_character)
            
            self.chat_manager.add_message(user_id, "user", user_message)
            
            character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
            memory = Memory(character_path, self.ap)
            await memory.add_message(Message(
                role="user",
                content=user_message,
                timestamp=datetime.now().isoformat()
            ))
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        short_term = memory.get_short_term()
        long_term = memory.get_long_term()
        
        user_preset = self.user_manager.get_user_preset(user_id, is_group)
        
        if user_id in self.pojia_plugin.enabled_users:
            await self.pojia_plugin.handle_prompt(ctx)
        else:
            ctx.event.default_prompt = []
            ctx.event.prompt = []
            
            if user_preset:
                ctx.event.default_prompt.append(Message(
                    role="system",
                    content=f"# 用户信息\n{user_preset}"
                ))
            
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
            except Exception as e:
                print(f"读取角色卡失败: {e}")
            
            world_book_prompt = self.world_book_processor.get_world_book_prompt(short_term)
            if world_book_prompt:
                ctx.event.default_prompt.extend(world_book_prompt)
            
            if long_term:
                ctx.event.default_prompt.append(Message(
                    role="system",
                    content="[历史记忆摘要]\n" + "\n".join(f"- {memory['content']}" for memory in long_term)
                ))
            
            if short_term:
                ctx.event.prompt.extend(short_term)

        self.debug_print("\n[最终提示词]")
        for msg in ctx.event.default_prompt:
            self.debug_print(f"[{msg.role}] {msg.content}")
        if ctx.event.prompt:
            print("\n[对话历史]")
            for msg in ctx.event.prompt:
                print(f"[{msg.role}] {msg.content}")
        print("=" * 50)

    @handler(NormalMessageResponded)
    async def handle_response(self, ctx: EventContext):
        user_id = ctx.event.sender_id
        if user_id not in self.enabled_users:
            return

        is_group = ctx.event.launcher_type == "group"
        response = ctx.event.response_text
        
        self._current_user_id = user_id

        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        response = response.replace("{{char}}", current_character)

        self.chat_manager.add_message(user_id, "assistant", response)
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        await memory.add_message(Message(
            role="assistant",
            content=response,
            timestamp=datetime.now().isoformat()
        ))

        display_message = self._process_message_for_display(response)
        
        ctx.event.response_text = display_message

    async def _handle_message(self, ctx: EventContext):
        msg = ctx.event.text_message
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"

        if msg == "/开启酒馆":
            if user_id in self.enabled_users:
                ctx.add_return("reply", ["酒馆已经开启啦~"])
                ctx.prevent_default()
                return
                
            self.enabled_users.add(user_id)
            self.chat_manager.clear_history(user_id)
            
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
                self.chat_manager.clear_history(user_id)
                
                if user_id in self.pojia_plugin.enabled_users:
                    self.pojia_plugin.enabled_users.remove(user_id)
                
                ctx.add_return("reply", ["酒馆已关闭"])
            else:
                ctx.add_return("reply", ["酒馆本来就是关闭的呢"])
            ctx.prevent_default()
            return

        if user_id not in self.enabled_users:
            if msg.startswith("/"):
                ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
                ctx.prevent_default()
            return

        if await self.command_handler.handle(ctx, msg):
            return

        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        self.chat_manager.add_message(user_id, "user", msg)
        
        await memory.add_message(Message(
            role="user",
            content=msg,
            timestamp=datetime.now().isoformat()
        ))
        
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
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        if user_id in self.enabled_users:
            ctx.add_return("reply", ["酒馆已经开启啦~"])
            ctx.prevent_default()
            return
            
        self.enabled_users.add(user_id)
        self.chat_manager.clear_history(user_id)
        
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
        user_id = ctx.event.sender_id
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["酒馆本来就是关闭的呢"])
            ctx.prevent_default()
            return
            
        self.enabled_users.remove(user_id)
        if user_id in self.started_users:
            self.started_users.remove(user_id)
        if user_id in self.selecting_users:
            self.selecting_users.remove(user_id)
        if user_id in self.current_page:
            del self.current_page[user_id]
        
        self.chat_manager.clear_history(user_id)
        
        if user_id in self.pojia_plugin.enabled_users:
            self.pojia_plugin.enabled_users.remove(user_id)
        
        if hasattr(ctx.event, 'query'):
            if hasattr(ctx.event.query, 'session'):
                ctx.event.query.session = None
                ctx.event.query.session = None
                
            if hasattr(ctx.event.query, 'messages'):
                ctx.event.query.messages = []
                
            if hasattr(ctx.event.query, 'history'):
                ctx.event.query.history = []
        
        ctx.add_return("reply", ["酒馆已关闭，下次进入可以重新选择角色"])
        ctx.prevent_default()

    def _process_message_for_display(self, message: str, show_status: bool = False) -> str:
        if not message:
            return message
            
        processed_text, status_content = self.status_processor.process_text(message, show_status)
        
        if status_content:
            user_id = getattr(self, '_current_user_id', None)
            if user_id:
                self.status_processor.save_status(user_id, status_content)
        
        return processed_text.strip()

    async def _handle_start_command(self, ctx: EventContext):
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
            
        current_character = self.user_manager.get_user_character(user_id, is_group)
        if current_character == "default":
            ctx.add_return("reply", ["请先使用 /角色列表 命令选择一个角色"])
            ctx.prevent_default()
            return
            
        self.started_users.add(user_id)
        
        self._current_user_id = user_id
        
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
            
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        messages = memory.get_short_term()
        last_message = None
        if messages:
            for msg in reversed(messages):
                if msg.role == "assistant":
                    last_message = msg.content
                    break
        
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
        
        last_message = last_message.replace("{{user}}", user_name)
        
        if last_message:
            await memory.add_message(Message(
                role="assistant",
                content=last_message,
                timestamp=datetime.now().isoformat()
            ))
        
        display_message = self._process_message_for_display(last_message)
        ctx.add_return("reply", [display_message])
        ctx.prevent_default()

    async def _handle_convert_card(self, ctx: EventContext):
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
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        short_term = memory.get_short_term()
        long_term = memory.get_long_term()
        
        status = [
            "===== 记忆系统状态 =====",
            f"当前角色: {current_character}",
            f"记忆系统: {'启用' if memory.config['enabled'] else '禁用'}",
            f"短期记忆数量: {len(short_term)}/{memory.config['short_term_limit']}",
            f"长期记忆数量: {len(long_term)}",
            f"总结批次大小: {memory.config['summary_batch_size']}",
            "======================="
        ]
        
        ctx.add_return("reply", ["\n".join(status)])
        ctx.prevent_default()

    async def _handle_undo(self, ctx: EventContext):
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        messages = memory.get_short_term()
        
        if not messages:
            ctx.add_return("reply", ["没有可撤回的消息"])
            ctx.prevent_default()
            return
        
        last_msg = messages.pop()
        
        memory.save_short_term(messages)
        
        self.chat_manager.remove_last_message(user_id)
        
        role_display = "用户" if last_msg.role == "user" else "助手"
        ctx.add_return("reply", [f"已撤回{role_display}的消息: {last_msg.content}"])
        ctx.prevent_default()

    async def _handle_clear_memory(self, ctx: EventContext):
        """清空所有记忆"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        print(f"\n=== 清空角色 {current_character} 的记忆 ===")
        print(f"角色目录: {character_path}")
        
        memory.clear_all()
        
        self.chat_manager.clear_history(user_id)
        
        if hasattr(ctx.event, 'query'):
            if hasattr(ctx.event.query, 'session'):
                ctx.event.query.session = None
                
            if hasattr(ctx.event.query, 'messages'):
                ctx.event.query.messages = []
                
            if hasattr(ctx.event.query, 'history'):
                ctx.event.query.history = []
        
        ctx.add_return("reply", [f"已清空角色 {current_character} 的所有记忆"])
        ctx.prevent_default()

    async def _handle_force_summary(self, ctx: EventContext):
        """强制执行记忆总结，不管记忆数量多少"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        print("\n=== 强制总结调试信息 ===")
        print(f"用户ID: {user_id}")
        print(f"会话类型: {'群聊' if is_group else '私聊'}")
        print(f"角色名: {current_character}")
        print(f"角色目录: {character_path}")
        
        messages = memory.get_short_term()
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
        
        current_count = len(messages)
        
        original_batch_size = memory.config["summary_batch_size"]
        original_limit = memory.config["short_term_limit"]
        
        print(f"\n[配置信息]")
        print(f"原始批次大小: {original_batch_size}")
        print(f"原始记忆上限: {original_limit}")
        
        try:
            memory.config["summary_batch_size"] = current_count
            memory.config["short_term_limit"] = 1  
            
            print(f"\n[修改后配置]")
            print(f"新批次大小: {memory.config['summary_batch_size']}")
            print(f"新记忆上限: {memory.config['short_term_limit']}")
            
            print("\n[开始执行总结]")
            await memory._summarize_memories()
            
            long_term = memory.get_long_term()
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
        memory = Memory(character_path, self.ap)
        
        test_results = []
        
        test_results.append("1. 测试目录结构")
        try:
            user_path = self.user_manager.get_user_path(user_id, is_group)
            test_results.append(f"✓ 用户目录: {user_path}")
            test_results.append(f"✓ 角色目录: {character_path}")
        except Exception as e:
            test_results.append(f"✗ 目录创建失败: {e}")
        
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
        
        test_results.append("\n3. 测试记忆系统")
        try:
            test_msg = Message(
                role="user",
                content="这是一条测试消息",
                timestamp=datetime.now().isoformat()
            )
            await memory.add_message(test_msg)
            test_results.append("✓ 消息添加成功")
            
            messages = memory.get_short_term()
            test_results.append(f"✓ 当前短期记忆数量: {len(messages)}")
            
            memory.save_short_term(messages)
            test_results.append("✓ 记忆保存成功")
            
            if os.path.exists(memory.short_term_file):
                test_results.append("✓ 短期记忆文件已创建")
            if os.path.exists(memory.long_term_file):
                test_results.append("✓ 长期记忆文件已创建")
            
        except Exception as e:
            test_results.append(f"✗ 记忆系统测试失败: {e}")
        
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
        
        ctx.add_return("reply", ["\n".join(test_results)])
        ctx.prevent_default()

    async def _handle_set_preset(self, ctx: EventContext):
        """处理设置用户预设的命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        setting_history_key = f"setting_profile_{user_id}"
        setting_history = getattr(self, setting_history_key, [])
        
        current_input = ctx.event.text_message.replace("/设定我的个人资料", "").strip()
        
        if ctx.event.text_message.startswith("/设定我的个人资料"):
            if current_input == "":  
                setting_history = []  
                message = "[设置个人资料] 第1步：请问你希望我如何称呼你？"
                setting_history.append({"role": "assistant", "content": message})
                setattr(self, setting_history_key, setting_history)
                ctx.add_return("reply", [message])
                ctx.prevent_default()
                return
            else:  
                setting_history = []
                setting_history.append({"role": "user", "content": current_input})
                message = f"[设置个人资料] 第2步：{current_input}，请问你的性别是？"
                setting_history.append({"role": "assistant", "content": message})
                setattr(self, setting_history_key, setting_history)
                ctx.add_return("reply", [message])
            ctx.prevent_default()
            return
            
        if not setting_history:
            return
        
        last_question = setting_history[-1]["content"] if setting_history else ""
        
        if "[设置个人资料] 第1步" in last_question:
            name = current_input.strip()
            setting_history.append({"role": "user", "content": name})
            message = f"[设置个人资料] 第2步：{name}，请问你的性别是？"
            setting_history.append({"role": "assistant", "content": message})
            setattr(self, setting_history_key, setting_history)
            ctx.add_return("reply", [message])
            ctx.prevent_default()
            
        elif "[设置个人资料] 第2步" in last_question:
            gender = current_input.strip()
            setting_history.append({"role": "user", "content": gender})
            message = "[设置个人资料] 第3步：好的，请简单描述一下你的性格特点。"
            setting_history.append({"role": "assistant", "content": message})
            setattr(self, setting_history_key, setting_history)
            ctx.add_return("reply", [message])
            ctx.prevent_default()
            
        elif "[设置个人资料] 第3步" in last_question:
            personality = current_input.strip()
            setting_history.append({"role": "user", "content": personality})
            message = "[设置个人资料] 第4步：还有什么想要补充的信息吗？(直接输入补充内容，如果没有请输入\"没有\")"
            setting_history.append({"role": "assistant", "content": message})
            setattr(self, setting_history_key, setting_history)
            ctx.add_return("reply", [message])
            ctx.prevent_default()
            
        elif "[设置个人资料] 第4步" in last_question:
            additional_info = current_input.strip()
            setting_history.append({"role": "user", "content": additional_info})
            
            user_messages = [msg["content"] for msg in setting_history if msg["role"] == "user"]
            name = user_messages[0]
            gender = user_messages[1]
            personality = user_messages[2]
            
            user_profile = {
                "user_profile": {
                    "name": name,
                    "gender": gender,
                    "personality": personality
                }
            }
            
            if additional_info and additional_info != "没有":
                user_profile["user_profile"]["additional_info"] = additional_info
            
            yaml_str = yaml.dump(user_profile, allow_unicode=True, sort_keys=False, default_flow_style=False)
            
            final_preset = f"""# 用户个人资料
{yaml_str}
# 注：以上信息将用于指导AI理解用户背景和互动偏好"""
            
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
            
            delattr(self, setting_history_key)
            
        ctx.prevent_default()

    async def _handle_status(self, ctx: EventContext):
        """处理状态命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        last_status = self.status_processor.get_last_status(user_id)
        
        if not last_status:
            character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
            memory = Memory(character_path, self.ap)
            
            messages = memory.get_short_term()
            
            if messages:
                for msg in reversed(messages):
                    if msg.role == "assistant":
                        _, status_content = self.status_processor.process_text(msg.content, show_status=True)
                        if status_content:
                            last_status = status_content
                            self.status_processor.save_status(user_id, status_content)
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
            
        try:
            juese_dir = os.path.join(os.path.dirname(__file__), "juese")
            yaml_files = [f for f in os.listdir(juese_dir) if f.endswith('.yaml')]
            
            if not yaml_files:
                ctx.add_return("reply", ["暂无可用角色"])
                ctx.prevent_default()
                return
            
            current_page = self.current_page.get(user_id, 1)
            total_pages = (len(yaml_files) + 99) // 100  
            
            start_idx = (current_page - 1) * 100
            end_idx = min(start_idx + 100, len(yaml_files))
            current_characters = yaml_files[start_idx:end_idx]
            
            display = [
                "=== 角色列表 ===",
                f"当前第 {current_page}/{total_pages} 页，本页显示 {len(current_characters)} 个角色"
            ]
            
            for i, char_file in enumerate(current_characters, start=1):
                char_name = os.path.splitext(char_file)[0]
                display.append(f"{i}. {char_name}")
            
            display.extend([
                "\n=== 操作提示 ===",
                "1. 使用 /角色 第N页 切换到指定页面",
                "2. 直接输入数字(1-100)选择本页角色",
                "3. 选择角色后使用 /开始 开始对话"
            ])
            
            self.selecting_users.add(user_id)
            
            ctx.add_return("reply", ["\n".join(display)])
        except Exception as e:
            ctx.add_return("reply", [f"获取角色列表失败: {e}"])
        
        ctx.prevent_default()

    async def _handle_character_command(self, ctx: EventContext):
        """处理角色命令"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["请先使用 /开启酒馆 命令开启酒馆"])
            ctx.prevent_default()
            return
            
        try:
            juese_dir = os.path.join(os.path.dirname(__file__), "juese")
            yaml_files = [f for f in os.listdir(juese_dir) if f.endswith('.yaml')]
            
            if not yaml_files:
                ctx.add_return("reply", ["暂无可用角色"])
                ctx.prevent_default()
                return
                
            current_page = self.current_page.get(user_id, 1)
            total_pages = (len(yaml_files) + 99) // 100  
            
            start_idx = (current_page - 1) * 100
            end_idx = min(start_idx + 100, len(yaml_files))
            current_characters = yaml_files[start_idx:end_idx]
            
            display = [
                "=== 角色列表 ===",
                f"当前第 {current_page}/{total_pages} 页，共 {len(yaml_files)} 个角色"
            ]
            
            for i, char_file in enumerate(current_characters, start=1):
                char_name = os.path.splitext(char_file)[0]
                display.append(f"{i}. {char_name}")
            
            display.extend([
                "\n=== 操作提示 ===",
                "• 选择角色：直接输入数字(1-100)",
                f"• 翻页命令：/角色 第N页（当前第{current_page}页，共{total_pages}页）",
                "• 选择后输入 /开始 开始对话"
            ])
            
            self.selecting_users.add(user_id)
            
            ctx.add_return("reply", ["\n".join(display)])
        except Exception as e:
            ctx.add_return("reply", [f"获取角色列表失败: {e}"])
        
        ctx.prevent_default()

    async def _handle_character_selection(self, ctx: EventContext, selection: str):
        """处理角色选择"""
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        if user_id not in self.selecting_users:
            return
            
        ctx.prevent_default()
        
        current_page = self.current_page.get(user_id, 1)
        
        juese_dir = os.path.join(os.path.dirname(__file__), "juese")
        yaml_files = [f for f in os.listdir(juese_dir) if f.endswith('.yaml')]
        total_pages = max(1, (len(yaml_files) + 99) // 100)  
        
        try:
            selection_num = int(selection)
            if 1 <= selection_num <= 100:  
                start_idx = (current_page - 1) * 100  
                actual_idx = start_idx + selection_num - 1
                
                if actual_idx < len(yaml_files):
                    selected_char = os.path.splitext(yaml_files[actual_idx])[0]
                    
                    self.chat_manager.clear_history(user_id)
                    
                    character_path = self.user_manager.get_character_path(user_id, selected_char, is_group)
                    os.makedirs(character_path, exist_ok=True)
                    
                    memory = Memory(character_path, self.ap)
                    memory.clear_all()  
                    
                    self.user_manager.save_user_character(user_id, selected_char, is_group)
                    
                    if user_id in self.selecting_users:
                        self.selecting_users.remove(user_id)
                    if user_id in self.started_users:
                        self.started_users.remove(user_id)
                    
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
                
            display = [f"=== {subcommand}世界书 ==="]
            for i, entry in enumerate(entries, 1):
                display.append(f"{i}. {entry.get_display_info(not is_constant)}")
                
            display.extend([
                f"\n=== 第 {page}/{total_pages} 页 ===",
                f"查看其他页请使用：/世界书 {subcommand} <页码>"
            ])
            
            ctx.add_return("reply", ["\n".join(display)])
            ctx.prevent_default()
            return
            
        elif subcommand in ["禁用", "启用"] and len(parts) >= 4:
            entry_type = " ".join(parts[2:-1])  
            try:
                entry_num = int(parts[-1])  
            except ValueError:
                ctx.add_return("reply", ["序号必须是数字"])
                ctx.prevent_default()
                return
                
            is_constant = entry_type == "常开条目"
            entries, _ = self.world_book_processor.get_entries_by_type(is_constant, 1)
            
            if not entries or entry_num < 1 or entry_num > len(entries):
                ctx.add_return("reply", ["无效的条目序号"])
                ctx.prevent_default()
                return
                
            entry = entries[entry_num - 1]
            
            if subcommand == "启用":
                entry.enabled = True
                action = "启用"
            else:
                entry.enabled = False
                action = "禁用"
                
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
            await self.pojia_plugin._handle_enable_command(ctx, user_id, msg)
        elif subcommand == "关闭":
            await self.pojia_plugin._handle_disable_command(ctx, user_id)
        elif subcommand == "状态":
            await self.pojia_plugin._handle_status_command(ctx, user_id)
        else:
            await self.pojia_plugin._send_help_message(ctx)
        ctx.prevent_default()

    async def _handle_character_switch(self, ctx: EventContext, character_name: str):
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        juese_dir = os.path.join(os.path.dirname(__file__), "juese")
        character_file = os.path.join(juese_dir, f"{character_name}.yaml")
        
        if not os.path.exists(character_file):
            ctx.add_return("reply", [f"角色 {character_name} 不存在"])
            ctx.prevent_default()
            return
            
        self.user_manager.save_user_character(user_id, character_name, is_group)
        
        self.chat_manager.clear_history(user_id)
        
        ctx.add_return("reply", [
            f"✅ 已切换到角色: {character_name}\n"
            "已加载该角色的记忆和历史记录\n"
            "请使用 /开始 命令开始新的对话"
        ])
        ctx.prevent_default()

    async def _handle_character_info(self, ctx: EventContext):
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        if current_character == "default":
            ctx.add_return("reply", ["当前未选择角色，请使用 /角色 列表 选择一个角色"])
            ctx.prevent_default()
            return
        
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
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        short_term = memory.get_short_term()
        long_term = memory.get_long_term()
        
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
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        if setting == "历史":
            if value < 1 or value > 100:
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
        
        try:
            with open(memory.config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(memory.config, f, allow_unicode=True)
            
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
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        self.chat_manager.clear_history(user_id)
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        memory.save_short_term([])
        
        ctx.add_return("reply", ["已清空对话历史"])
        ctx.prevent_default()

    async def _handle_regenerate(self, ctx: EventContext):
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        
        messages = memory.get_short_term()
        if not messages:
            ctx.add_return("reply", ["没有可重新生成的消息"])
            ctx.prevent_default()
            return
            
        for i in range(len(messages)-1, -1, -1):
            if messages[i].role == "assistant":
                messages.pop(i)
                break
        
        memory.save_short_term(messages)
        
        ctx.add_return("reply", ["已删除最后一条回复，请等待重新生成"])
        ctx.prevent_default()

    async def _handle_world_book_list(self, ctx: EventContext, is_common: bool):
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        entries = self.world_book_processor.entries
        if not entries:
            ctx.add_return("reply", ["没有找到任何世界书条目"])
            ctx.prevent_default()
            return
            
        constant_entries = [e for e in entries if e.constant]
        keyword_entries = [e for e in entries if not e.constant]
        
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
        ctx.add_return("reply", ["世界书导入功能开发中"])
        ctx.prevent_default()

    async def _handle_world_book_export(self, ctx: EventContext, is_common: bool):
        ctx.add_return("reply", ["世界书导出功能开发中"])
        ctx.prevent_default()

    async def _handle_world_book_enable(self, ctx: EventContext, entry_id: int):
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
        entries = self.world_book_processor.entries
        if not entries or entry_id < 0 or entry_id >= len(entries):
            ctx.add_return("reply", ["无效的条目ID"])
            ctx.prevent_default()
            return
            
        entry = entries.pop(entry_id)
        ctx.add_return("reply", [f"已删除条目: {entry.comment}"])
        ctx.prevent_default()

    async def _handle_world_book_view(self, ctx: EventContext, entry_id: int):
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

    def __del__(self):
        pass

    async def _handle_memory_command(self, ctx: EventContext):
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
        user_id = ctx.event.sender_id
        is_group = ctx.event.launcher_type == "group"
        message = ctx.event.text_message.strip()

        if user_id not in self.started_users:
            ctx.add_return("reply", ["请输入 /开始 开启对话，在此期间你只能设定个人资料和使用命令"])
            ctx.prevent_default()
            return

        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        user_name = "我"
        try:
            preset = self.user_manager.get_user_preset(user_id, is_group)
            if preset:
                preset_data = yaml.safe_load(preset)
                if preset_data and "user_profile" in preset_data:
                    user_name = preset_data["user_profile"].get("name", "我")
        except Exception as e:
            print(f"获取用户名失败: {e}")
    
        message = message.replace("{{user}}", user_name).replace("{{char}}", current_character)

        self.chat_manager.add_message(user_id, "user", message)

        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path, self.ap)
        await memory.add_message(Message(
            role="user",
            content=message,
            timestamp=datetime.now().isoformat()
        ))

        processed_msg = self.regex_processor.process_text(message)
        if processed_msg != message:
            ctx.add_return("reply", [f"[处理后的消息]\n{processed_msg}"])
            
        self._current_user_id = user_id