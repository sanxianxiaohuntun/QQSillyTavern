class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        if not isinstance(text, str):
            return ""
        return text.replace('\r\n', '\n').replace('\r', '\n')

    @staticmethod
    def is_empty(text: str) -> bool:
        if not text:
            return True
        return len(text.strip()) == 0 