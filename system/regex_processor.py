import re
from typing import Dict, Optional, List

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
        
    def _load_rules(self, rules_config: dict):
        for name, rule_config in rules_config.items():
            if isinstance(rule_config, str):
                self.rules[name] = RegexRule(name, rule_config)
            else:
                self.rules[name] = RegexRule(
                    name=name,
                    pattern=rule_config['pattern'],
                    replace=rule_config.get('replace', ''),
                    enabled=rule_config.get('enabled', True),
                    description=rule_config.get('description', '')
                )
                
    def process_text(self, text: str) -> str:
        if not self.enabled or not text:
            return text
            
        result = text
        for rule in self.rules.values():
            result = rule.apply(result)
        return result
        
    def get_rule_info(self, name: str) -> Optional[dict]:
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
        return [self.get_rule_info(name) for name in self.rules] 