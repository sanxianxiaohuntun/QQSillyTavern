from pkg.plugin.context import APIHost
from pkg.provider.entities import Message
import yaml
import json
import os
from ..system.chat_manager import ChatManager
from ..system.memory import Memory
from pkg.plugin.context import EventContext
from ..system.world_book_processor import WorldBookProcessor

class PoJiaModePlugin:
    def __init__(self, host: APIHost, chat_manager: ChatManager, user_manager):
        self.host = host
        self.enabled_users = set()
        self.prompt_template = []
        self.config = {}
        self.chat_manager = chat_manager
        self.user_manager = user_manager
        self.world_book_processor = None
        
    async def initialize(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            return

        self.world_book_processor = WorldBookProcessor(os.path.dirname(os.path.dirname(__file__)))

        template_name = self.config.get("default_template", "gemini")
        template_path = os.path.join(
            os.path.dirname(__file__), 
            self.config["templates"].get(template_name, "prompts/gemini.json")
        )

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                self.prompt_template = json.load(f)
                if self.config.get("debug", False):
                    print(f"已加载模板: {template_name}")
        except Exception as e:
            print(f"读取提示词模板失败: {e}")
            return

    async def _send_help_message(self, ctx):
        help_text = [
            "破甲模式使用说明：",
            "1. 基础命令：",
            "   • /开启破甲模式 [模板名] - 开启破甲模式",
            "   • /切换破甲模式 <模板名> - 切换到其他模板",
            "   • /关闭破甲模式 - 关闭破甲模式",
            f"2. 可用模板：{', '.join(self.config['templates'].keys())}",
            "3. 注意事项：",
            "   • 切换模板前需要先开启破甲模式",
            "   • 每个用户可以使用不同的模板",
            "   • 关闭后需要重新开启才能使用"
        ]
        ctx.add_return("reply", ["\n".join(help_text)])
        ctx.prevent_default()

    async def _handle_enable_command(self, ctx, user_id: str, msg: str):
        if user_id in self.enabled_users:
            ctx.add_return("reply", ["已经处于破甲模式，如需切换模板请使用 /切换破甲模式 <模板名>"])
            ctx.prevent_default()
            return
            
        template_name = self._get_template_name(msg)
        if not template_name:
            ctx.add_return("reply", [f"模板不存在，可用模板: {', '.join(self.config['templates'].keys())}"])
            ctx.prevent_default()
            return
            
        if await self._load_template(template_name):
            self.enabled_users.add(user_id)
            ctx.add_return("reply", [f"已开启破甲模式（使用 {template_name} 模板）"])
        else:
            ctx.add_return("reply", ["开启失败，请检查日志"])
        ctx.prevent_default()

    async def _handle_switch_command(self, ctx, user_id: str, msg: str):
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["请先使用 /开启破甲模式 命令开启破甲模式"])
            ctx.prevent_default()
            return
            
        template_name = self._get_template_name(msg)
        if not template_name:
            ctx.add_return("reply", [f"模板不存在，可用模板: {', '.join(self.config['templates'].keys())}"])
            ctx.prevent_default()
            return
            
        if await self._load_template(template_name):
            ctx.add_return("reply", [f"已切换到 {template_name} 模板"])
        else:
            ctx.add_return("reply", ["切换失败，请检查日志"])
        ctx.prevent_default()

    async def _handle_disable_command(self, ctx, user_id: str):
        if user_id in self.enabled_users:
            self.enabled_users.remove(user_id)
            ctx.add_return("reply", ["已关闭破甲模式"])
            ctx.prevent_default()

    def _get_template_name(self, msg: str) -> str:
        parts = msg.split()
        template_name = parts[2] if len(parts) > 2 else self.config.get("default_template", "Gemini")
        
        templates_map = {
            "gemini": "Gemini",
            "claude": "Claude",
            "deepseek": "DeepSeek"
        }
        
        return templates_map.get(template_name.lower(), template_name)

    async def _load_template(self, template_name: str) -> bool:
        try:
            template_path = os.path.join(
                os.path.dirname(__file__), 
                self.config["templates"][template_name]
            )
            with open(template_path, "r", encoding="utf-8") as f:
                self.prompt_template = json.load(f)
            return True
        except Exception as e:
            print(f"加载模板失败: {e}")
            return False

    async def handle_prompt(self, ctx: EventContext):
        if not hasattr(ctx.event.query, "sender_id") or \
           ctx.event.query.sender_id not in self.enabled_users:
            return
        
        current_input = self._get_current_input(ctx)
        
        final_prompt = await self._build_prompt(ctx, current_input)
        
        ctx.event.default_prompt = []
        ctx.event.prompt = []
        ctx.event.default_prompt.extend(final_prompt)

    def _get_current_input(self, ctx) -> str:
        if hasattr(ctx.event.query, "user_message"):
            msg = ctx.event.query.user_message
            if isinstance(msg.content, list) and msg.content and hasattr(msg.content[0], 'text'):
                return msg.content[0].text
            return str(msg.content)
        return ""

    async def _build_prompt(self, ctx, current_input: str) -> list:
        final_prompt = []
        
        user_id = ctx.event.query.sender_id if hasattr(ctx.event.query, "sender_id") else None
        is_group = ctx.event.query.launcher_type == "group" if hasattr(ctx.event.query, "launcher_type") else False
        
        current_character = self.user_manager.get_user_character(user_id, is_group)
        
        character_path = self.user_manager.get_character_path(user_id, current_character, is_group)
        memory = Memory(character_path)
        short_term = memory.get_short_term()
        
        print(f"\n=== 破甲模式角色信息 ===")
        print(f"用户ID: {user_id}")
        print(f"当前角色: {current_character}")
        print(f"角色路径: {character_path}")
        
        for msg in self.prompt_template:
            role = msg["role"]
            content = msg["content"]
            
            if content == "<用户预设>":
                user_preset = self.user_manager.get_user_preset(user_id, is_group)
                final_prompt.append(Message(
                    role="system",
                    content=user_preset
                ))
                continue
            
            elif content == "<角色卡>":
                try:
                    prompt = await self.chat_manager.build_prompt(ctx, user_id)
                    if prompt:
                        final_prompt.extend(prompt)
                    else:
                        print("未能从 chat_manager 获取角色设定")
                        juese_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "juese")
                        char_file = os.path.join(juese_dir, f"{current_character}.yaml")
                        if os.path.exists(char_file):
                            with open(char_file, 'r', encoding='utf-8') as f:
                                character_data = yaml.safe_load(f)
                            final_prompt.append(Message(
                                role="system",
                                content=f"你将扮演如下：\n{yaml.dump(character_data, allow_unicode=True, sort_keys=False)}"
                            ))
                except Exception as e:
                    print(f"读取角色卡失败: {e}")
                continue
                
            elif content == "<Game Materials>":
                if self.world_book_processor:
                    world_book_prompt = self.world_book_processor.get_world_book_prompt(short_term)
                    if world_book_prompt:
                        final_prompt.extend(world_book_prompt)
                continue
            
            elif content == "<聊天记录>":
                final_prompt.extend(short_term)
                continue
            
            if "<当前输入内容>" in content:
                content = content.replace("<当前输入内容>", current_input)
            
            final_prompt.append(Message(role=role, content=content))
        
        print("\n=== 最终提示词 ===")
        for msg in final_prompt:
            print(f"[{msg.role}] {msg.content}")
        print("=" * 50)
        
        return final_prompt

    def _get_message_content(self, msg) -> str:
        content = msg.content
        if isinstance(content, list) and content and hasattr(content[0], 'text'):
            return content[0].text
        return str(content)

    def _insert_dynamic_content(self, prompt: list, default_prompt: list, chat_history: list) -> list:
        result = []
        for msg in prompt:
            result.append(msg)
            if msg.content == "<用户预设>":
                result.extend(default_prompt)
            elif msg.content == "<聊天记录>":
                result.extend(chat_history)
        return result

    def _log_debug_info(self, ctx, current_input: str, final_prompt: list):
        print("\n=== 破甲模式调试信息 ===")
        print(f"用户ID: {ctx.event.query.sender_id}")
        print(f"当前输入: {current_input}")
        print("\n[修改后提示词]")
        for msg in final_prompt:
            print(f"  [{msg.role}] {msg.content}")
        print("=" * 50)

    async def get_response(self, msg: str) -> str:
        return f"[破甲模式] 收到消息：{msg}"

    async def _handle_status_command(self, ctx: EventContext, user_id: str):
        if user_id not in self.enabled_users:
            ctx.add_return("reply", ["破甲模式未开启"])
            ctx.prevent_default()
            return
            
        template_name = None
        for name, path in self.config["templates"].items():
            template_path = os.path.join(os.path.dirname(__file__), path)
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    template_data = json.load(f)
                    if template_data == self.prompt_template:
                        template_name = name
                        break
            except Exception:
                continue
                
        if not template_name:
            template_name = "未知"
            
        status = [
            "=== 破甲模式状态 ===",
            f"状态: 已开启",
            f"当前模板: {template_name}",
            f"可用模板: {', '.join(self.config['templates'].keys())}",
            "\n切换模板请使用: /破甲 开启 <模板名>"
        ]
        
        ctx.add_return("reply", ["\n".join(status)])
        ctx.prevent_default()

    def __del__(self):
        pass 