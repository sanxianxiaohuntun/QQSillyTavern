import re
from typing import Dict, Optional, List, Tuple

class RegexRule:
    def __init__(self, name: str, pattern: str, replace: str = '', enabled: bool = True, description: str = ''):
        self.name = name
        self.pattern = pattern
        self.replace = replace
        self.enabled = enabled
        self.description = description
        self._compile()
        
    def _compile(self):
        try:
            self.regex = re.compile(self.pattern, re.DOTALL)
        except re.error as e:
            print(f"正则表达式编译失败 [{self.name}]: {self.pattern}")
            print(f"错误信息: {e}")
            self.enabled = False
            
    def apply(self, text: str) -> str:
        if not self.enabled:
            return text
        try:
            return self.regex.sub(self.replace, text)
        except Exception as e:
            print(f"正则替换失败 [{self.name}]: {e}")
            return text

class RegexProcessor:
    def __init__(self, config: dict, enabled: bool = True):
        self.enabled = enabled
        self.show_processed = config.get('show_processed', True)
        self.rules: Dict[str, RegexRule] = {}
        self._load_rules(config.get('rules', {}))
        
        # 状态块处理相关
        self.status_pattern = re.compile(r'<StatusBlock>(.*?)</StatusBlock>', re.DOTALL)
        self.last_status: Dict[str, str] = {}  # 用于存储每个用户的最后一个状态块
        
    def _load_rules(self, rules_config: dict):
        for name, rule_config in rules_config.items():
            if isinstance(rule_config, str):
                # 简单格式: "规则名: 正则表达式"
                self.rules[name] = RegexRule(name, rule_config)
            else:
                # 详细格式: {pattern, replace, enabled, description}
                self.rules[name] = RegexRule(
                    name=name,
                    pattern=rule_config['pattern'],
                    replace=rule_config.get('replace', ''),
                    enabled=rule_config.get('enabled', True),
                    description=rule_config.get('description', '')
                )
                
    def process_text(self, text: str) -> str:
        """处理普通文本的正则替换"""
        if not self.enabled or not text:
            return text
            
        result = text
        for rule in self.rules.values():
            result = rule.apply(result)
        return result
        
    def process_status_block(self, text: str, show_status: bool = False) -> Tuple[str, Optional[str]]:
        """
        处理文本中的状态块
        :param text: 原始文本
        :param show_status: 是否显示状态块
        :return: (处理后的文本, 提取的状态块内容)
        """
        if not text:
            return text, None
            
        # 查找状态块
        match = self.status_pattern.search(text)
        if not match:
            return text, None
            
        status_content = match.group(1).strip()
        
        # 移除状态块
        processed_text = self.status_pattern.sub('', text).strip()
        
        if show_status:
            # 如果需要显示状态，返回状态块内容
            return processed_text, status_content
        else:
            # 否则只返回处理后的文本
            return processed_text, None
            
    def save_status(self, user_id: str, status_content: str):
        """保存用户的最后一个状态块"""
        self.last_status[user_id] = status_content
        
    def get_last_status(self, user_id: str) -> Optional[str]:
        """获取用户的最后一个状态块"""
        return self.last_status.get(user_id)
        
    def get_rule_info(self, name: str) -> Optional[dict]:
        """获取规则详细信息"""
        rule = self.rules.get(name)
        if not rule:
            return None
        return {
            'name': rule.name,
            'pattern': rule.pattern,
            'replace': rule.replace,
            'enabled': rule.enabled,
            'description': rule.description
        }
        
    def list_rules(self) -> List[dict]:
        """列出所有规则的详细信息"""
        return [self.get_rule_info(name) for name in self.rules] 