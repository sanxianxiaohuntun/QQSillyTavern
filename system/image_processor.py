import os
import yaml
import json
import struct
import zlib
import base64
from typing import Dict, Any, Tuple, List

class ImageProcessor:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(__file__))
        self._init_directories()
        
    def _init_directories(self):
        """初始化目录结构"""
        dirs = {
            'png': '原始PNG角色卡目录',
            'png/converted': '已转换的PNG角色卡目录',
            'juese': '转换后的角色卡目录',
        }
        
        for dir_name, desc in dirs.items():
            dir_path = os.path.join(self.base_path, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"创建{desc}: {dir_path}")

    def _clean_text(self, text: str) -> str:
        """清理文本,统一换行符等"""
        if not isinstance(text, str):
            return ""
        return text.replace('\r\n', '\n').replace('\r', '\n')

    def _is_empty(self, text: str) -> bool:
        """检查文本是否为空"""
        if not text:
            return True
        return len(text.strip()) == 0

    def _extract_png_chunks(self, data: bytes) -> List[tuple[bytes, bytes]]:
        """提取PNG文件的所有数据块"""
        # 验证PNG签名
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError("不是有效的PNG文件")
            
        chunks = []
        pos = 8  # 跳过签名
        
        while pos < len(data):
            length = struct.unpack('>I', data[pos:pos+4])[0]
            pos += 4
            
            chunk_type = data[pos:pos+4]
            pos += 4
            
            chunk_data = data[pos:pos+length]
            pos += length
            
            pos += 4  # 跳过CRC
            
            chunks.append((chunk_type, chunk_data))
            
            if chunk_type == b'IEND':
                break
                
        return chunks

    def _decode_text_chunk(self, data: bytes) -> tuple[str, str]:
        """解码PNG文本块数据"""
        null_pos = data.find(b'\0')
        if null_pos == -1:
            raise ValueError("无效的文本块格式")
            
        keyword = data[:null_pos].decode('latin1')
        text_data = data[null_pos+1:]
        
        try:
            if all(c in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in text_data):
                decoded = base64.b64decode(text_data)
                try:
                    text = decoded.decode('utf-8')
                    return keyword, text
                except UnicodeDecodeError:
                    pass
        except:
            pass
        
        return keyword, text_data.decode('utf-8', errors='ignore')

    def process_character_image(self, image_path: str) -> Dict[str, Any]:
        """处理SillyTavern角色卡PNG图片"""
        try:
            with open(image_path, 'rb') as f:
                png_data = f.read()
            
            chunks = self._extract_png_chunks(png_data)
            character_data = None
            
            for chunk_type, chunk_data in chunks:
                if chunk_type == b'tEXt':
                    try:
                        keyword, text_data = self._decode_text_chunk(chunk_data)
                        
                        if keyword == 'chara':
                            try:
                                character_data = json.loads(text_data)
                                if self._is_valid_character(character_data):
                                    break
                            except json.JSONDecodeError:
                                try:
                                    decoded = base64.b64decode(text_data)
                                    character_data = json.loads(decoded.decode('utf-8'))
                                    if self._is_valid_character(character_data):
                                        break
                                except Exception:
                                    pass
                    except Exception:
                        pass
            
            if not character_data:
                file_name = os.path.splitext(os.path.basename(image_path))[0]
                character_data = self._create_default_character(file_name)
            
            self._save_character(character_data, image_path)
            
            return character_data
            
        except Exception as e:
            print(f"处理角色卡失败 {os.path.basename(image_path)}: {e}")
            return {}
            
    def _is_valid_character(self, data: Dict[str, Any]) -> bool:
        """验证是否是有效的角色数据"""
        if not isinstance(data, dict):
            return False
        return 'name' in data

    def _create_default_character(self, name: str) -> Dict[str, Any]:
        """创建默认角色数据"""
        return {
            'name': name,
            'description': '由PNG转换的角色卡',
            'personality': '',
            'first_mes': '',
            'scenario': '',
            'mes_example': '',
            'creator_notes': '通过PNG直接转换（未找到角色数据）',
        }

    def _save_character(self, data: Dict[str, Any], original_path: str) -> None:
        """保存角色数据为YAML"""
        try:
            file_name = data.get('name', os.path.splitext(os.path.basename(original_path))[0])
            yaml_path = os.path.join(self.base_path, 'juese', f"{file_name}.yaml")
            
            os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
            
            save_data = {}
            for field in ['name', 'description', 'personality', 'first_mes', 'scenario', 'mes_example']:
                value = self._clean_text(data.get(field, ''))
                if not self._is_empty(value):
                    save_data[field] = value
            
            with open(yaml_path, 'w', encoding='utf-8', newline='\n') as f:
                yaml.safe_dump(
                    save_data,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                    width=float("inf"),
                    indent=2
                )
                
            print(f"已转换并保存: {os.path.basename(original_path)} -> {os.path.basename(yaml_path)}")
            
        except Exception as e:
            print(f"保存角色卡失败: {e}")
            import traceback
            traceback.print_exc()

    def convert_all_character_cards(self) -> Tuple[int, list[str]]:
        """转换所有PNG角色卡"""
        png_dir = os.path.join(self.base_path, "png")
        converted_dir = os.path.join(png_dir, "converted")
        converted = []
        count = 0
        
        # 确保已转换目录存在
        if not os.path.exists(converted_dir):
            os.makedirs(converted_dir)
        
        # 只处理png目录下的文件，不处理converted子目录中的文件
        for file_name in os.listdir(png_dir):
            if not file_name.lower().endswith('.png'):
                continue
                
            # 跳过converted目录
            if file_name == "converted":
                continue
                
            image_path = os.path.join(png_dir, file_name)
            try:
                # 检查文件是否是目录
                if os.path.isdir(image_path):
                    continue
                    
                character_data = self.process_character_image(image_path)
                if character_data:
                    count += 1
                    converted.append(character_data.get('name', file_name))
                    
                    # 移动已转换的PNG文件到converted目录
                    converted_path = os.path.join(converted_dir, file_name)
                    try:
                        os.rename(image_path, converted_path)
                        print(f"已移动转换完成的文件到: {converted_path}")
                    except Exception as e:
                        print(f"移动文件失败 {file_name}: {e}")
                        
            except Exception as e:
                print(f"转换失败 {file_name}: {e}")
                
        return count, converted 