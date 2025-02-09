import os
import yaml
from typing import List

class UserManager:
    def __init__(self, base_path: str):
        """
        初始化用户管理器
        :param base_path: 插件根目录路径
        """
        self.base_path = base_path
        self.users_path = os.path.join(base_path, "users")
        self._ensure_directories()
        self.user_characters = {}  # 用户当前使用的角色
        self.user_presets = {}     # 用户预设
        self.debug_mode = False
        
    def _ensure_directories(self):
        """确保必要的目录结构存在"""
        # 创建用户根目录
        os.makedirs(self.users_path, exist_ok=True)
        
        # 创建群聊和私聊目录
        os.makedirs(os.path.join(self.users_path, "group"), exist_ok=True)
        os.makedirs(os.path.join(self.users_path, "person"), exist_ok=True)
        
    def get_user_path(self, user_id: str, is_group: bool = False) -> str:
        """获取用户目录路径"""
        base = "group" if is_group else "person"
        user_path = os.path.join(self.users_path, base, str(user_id))
        os.makedirs(user_path, exist_ok=True)
        return user_path
        
    def get_character_path(self, user_id: str, character_name: str, is_group: bool = False) -> str:
        """获取角色目录路径"""
        user_path = self.get_user_path(user_id, is_group)
        character_path = os.path.join(user_path, "characters", character_name)
        os.makedirs(character_path, exist_ok=True)
        return character_path

    def get_user_preset_path(self, user_id: str, is_group: bool) -> str:
        """获取用户预设文件路径"""
        user_path = self.get_user_path(user_id, is_group)
        return os.path.join(user_path, "preset.yaml")

    def get_user_character_path(self, user_id: str, is_group: bool) -> str:
        """获取用户当前角色配置文件路径"""
        user_path = self.get_user_path(user_id, is_group)
        return os.path.join(user_path, "character.yaml")

    def get_user_preset(self, user_id: str, is_group: bool) -> str:
        """获取用户预设内容，如果不存在则返回默认预设"""
        preset_path = self.get_user_preset_path(user_id, is_group)
        
        # 默认预设
        default_preset = "我是我，你可以根据对话来识别我的性格、年龄和性别。"
        
        if not os.path.exists(preset_path):
            return default_preset
        
        try:
            with open(preset_path, 'r', encoding='utf-8') as f:
                preset = yaml.safe_load(f)
                return preset.get('description', default_preset)
        except Exception as e:
            print(f"读取用户预设失败: {e}")
            return default_preset

    def save_user_preset(self, user_id: str, is_group: bool, preset: str):
        """保存用户预设"""
        preset_path = self.get_user_preset_path(user_id, is_group)
        
        try:
            with open(preset_path, 'w', encoding='utf-8') as f:
                yaml.dump({'description': preset}, f, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存用户预设失败: {e}")
            return False

    def save_user_character(self, user_id: str, character_name: str, is_group: bool = False):
        """保存用户选择的角色"""
        char_path = self.get_user_character_path(user_id, is_group)
        
        try:
            with open(char_path, 'w', encoding='utf-8') as f:
                yaml.dump({'character': character_name}, f, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存用户角色选择失败: {e}")
            return False

    def get_user_character(self, user_id: str, is_group: bool = False) -> str:
        """获取用户当前选择的角色名称"""
        char_path = self.get_user_character_path(user_id, is_group)
        
        if not os.path.exists(char_path):
            return "default"
            
        try:
            with open(char_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('character', 'default')
        except Exception as e:
            print(f"读取用户角色选择失败: {e}")
            return "default"

    def debug_print(self, *args, **kwargs):
        """调试信息打印函数"""
        if self.debug_mode:
            print(*args, **kwargs)
            
    def set_debug_mode(self, debug: bool):
        """设置调试模式"""
        self.debug_mode = debug

    def reset_user_state(self, user_id: str):
        """重置用户状态到刚开启酒馆的状态"""
        # 清除用户的预设
        if user_id in self.user_presets:
            del self.user_presets[user_id]
        
        self.debug_print(f"已重置用户 {user_id} 的状态")

    def switch_character(self, user_id: str, character_name: str, is_group: bool = False) -> bool:
        """切换用户的角色
        
        Args:
            user_id: 用户ID
            character_name: 角色名称
            is_group: 是否是群聊
            
        Returns:
            bool: 切换是否成功
        """
        # 检查角色是否存在
        juese_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "juese")
        character_file = os.path.join(juese_dir, f"{character_name}.yaml")
        
        if not os.path.exists(character_file):
            self.debug_print(f"角色 {character_name} 不存在")
            return False
            
        # 保存角色选择
        key = f"{user_id}{'_group' if is_group else ''}"
        self.user_characters[key] = character_name
        
        self.debug_print(f"用户 {user_id} 切换到角色 {character_name}")
        return True

    def get_character_list(self) -> List[str]:
        """获取所有可用的角色列表"""
        juese_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "juese")
        if not os.path.exists(juese_dir):
            return []
            
        # 获取所有yaml文件
        character_files = [f[:-5] for f in os.listdir(juese_dir) if f.endswith('.yaml')]
        return sorted(character_files)  # 按字母顺序排序 