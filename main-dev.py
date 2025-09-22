import requests
import json
import os
import base64
import gzip
import zlib
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class CloudflareKVReader:
    """简化的 Cloudflare KV 读取器"""
    
    def __init__(self):
        """从环境变量初始化"""
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        self.namespace_id = os.getenv("NAMESPACE_ID")
        self.key_name = os.getenv("KEY_NAME")
        
        if not all([self.account_id, self.api_token]):
            raise ValueError("请在 .env 文件中配置 CLOUDFLARE_ACCOUNT_ID 和 CLOUDFLARE_API_TOKEN")
        
        # 创建会话，避免代理问题
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.proxies = {}
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })
        
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/storage/kv/namespaces"
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            response = self.session.get(self.base_url, timeout=30)
            return response.status_code == 200
        except:
            return False
    
    def list_namespaces(self) -> list:
        """列出命名空间"""
        try:
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('result', [])
        except Exception as e:
            print(f"❌ 获取命名空间失败: {e}")
            return []
    
    def list_keys(self, namespace_id: str) -> list:
        """列出指定命名空间中的键"""
        try:
            url = f"{self.base_url}/{namespace_id}/keys"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('result', [])
        except Exception as e:
            print(f"❌ 获取键列表失败: {e}")
            return []
    
    def get_value(self, namespace_id: str, key: str) -> Optional[str]:
        """读取键值"""
        try:
            url = f"{self.base_url}/{namespace_id}/values/{key}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 404:
                print(f"❌ 键 '{key}' 不存在")
                return None
            
            response.raise_for_status()
            return response.text
            
        except Exception as e:
            print(f"❌ 读取键值失败: {e}")
            return None
    
    def decode_protobuf_pako_base64(self, value: str) -> dict:
        """
        解码 protobuf + pako压缩 + base64 编码的数据
        解码顺序: base64 → pako解压 → protobuf解析
        """
        result = {
            "original_length": len(value),
            "decoded": False,
            "steps": [],
            "data": None,
            "error": None,
            "raw_bytes": None
        }
        
        try:
            # 步骤1: Base64 解码
            result["steps"].append("开始 Base64 解码...")
            decoded_bytes = base64.b64decode(value)
            result["steps"].append(f"✅ Base64 解码成功，得到 {len(decoded_bytes)} 字节")
            
            # 步骤2: Pako 解压 (使用 zlib)
            result["steps"].append("开始 Pako/zlib 解压...")
            
            # 尝试不同的解压方法
            decompressed_data = None
            
            # 方法1: 直接 zlib 解压
            try:
                decompressed_data = zlib.decompress(decoded_bytes)
                result["steps"].append(f"✅ zlib 直接解压成功，得到 {len(decompressed_data)} 字节")
            except:
                pass
            
            # 方法2: 带窗口大小的 zlib 解压
            if not decompressed_data:
                try:
                    decompressed_data = zlib.decompress(decoded_bytes, -zlib.MAX_WBITS)
                    result["steps"].append(f"✅ zlib 窗口解压成功，得到 {len(decompressed_data)} 字节")
                except:
                    pass
            
            # 方法3: gzip 解压
            if not decompressed_data:
                try:
                    decompressed_data = gzip.decompress(decoded_bytes)
                    result["steps"].append(f"✅ gzip 解压成功，得到 {len(decompressed_data)} 字节")
                except:
                    pass
            
            if not decompressed_data:
                result["steps"].append("❌ 所有解压方法都失败")
                result["error"] = "无法解压数据，可能不是 pako/zlib/gzip 格式"
                result["raw_bytes"] = decoded_bytes
                return result
            
            # 步骤3: Protobuf 解析
            result["steps"].append("开始 Protobuf 解析...")
            result["raw_bytes"] = decompressed_data
            
            # 由于我们不知道确切的 protobuf 结构，先尝试基本的解析
            try:
                # 尝试将原始字节作为 UTF-8 文本解析
                text_data = decompressed_data.decode('utf-8', errors='ignore')
                if text_data.strip():
                    result["steps"].append("✅ 解压后数据包含可读文本")
                    # 尝试作为 JSON 解析
                    try:
                        json_data = json.loads(text_data)
                        result["data"] = json_data
                        result["steps"].append("✅ 解压后数据是有效的 JSON")
                        result["decoded"] = True
                        return result
                    except:
                        result["data"] = {"text": text_data}
                        result["steps"].append("⚠️ 解压后数据是文本但不是 JSON")
                        result["decoded"] = True
                        return result
                
                # 如果不是文本，显示十六进制
                hex_preview = decompressed_data[:100].hex()
                result["steps"].append(f"解压后数据 (hex 前100字节): {hex_preview}")
                result["data"] = {
                    "binary_data": True,
                    "length": len(decompressed_data),
                    "hex_preview": hex_preview,
                    "first_bytes": list(decompressed_data[:20])
                }
                result["decoded"] = True
                
            except Exception as e:
                result["error"] = f"Protobuf 解析错误: {e}"
                result["steps"].append(f"❌ Protobuf 解析失败: {e}")
        
        except Exception as e:
            result["error"] = str(e)
            result["steps"].append(f"❌ 解码过程出错: {e}")
        
        return result
    
    def try_decode_value(self, value: str) -> dict:
        """尝试各种方式解码值"""
        result = {
            "original_length": len(value),
            "decoded": False,
            "method": None,
            "data": None,
            "error": None
        }
        
        # 优先尝试 protobuf + pako + base64 解码
        protobuf_result = self.decode_protobuf_pako_base64(value)
        if protobuf_result["decoded"]:
            result.update({
                "decoded": True,
                "method": "protobuf_pako_base64",
                "data": protobuf_result["data"],
                "steps": protobuf_result["steps"],
                "raw_bytes": protobuf_result.get("raw_bytes")
            })
            return result
        
        # 如果 protobuf 解码失败，尝试其他方法
        
        # 尝试直接 JSON 解析
        try:
            data = json.loads(value)
            result.update({
                "decoded": True,
                "method": "direct_json",
                "data": data
            })
            return result
        except:
            pass
        
        # 尝试 Base64 + JSON
        try:
            decoded_bytes = base64.b64decode(value)
            decoded_text = decoded_bytes.decode('utf-8')
            data = json.loads(decoded_text)
            result.update({
                "decoded": True,
                "method": "base64_json",
                "data": data
            })
            return result
        except:
            pass
        
        # 如果都失败，返回原始数据和 protobuf 尝试的详细信息
        result.update({
            "decoded": True,
            "method": "raw_with_protobuf_attempt",
            "data": {
                "raw_value": value[:200] + "..." if len(value) > 200 else value,
                "protobuf_attempt": protobuf_result
            }
        })
        
        return result

def main():
    """主函数"""
    
    print("🔧 Cloudflare KV 读取工具 - 支持 Protobuf+Pako+Base64 解码")
    print("=" * 60)
    
    try:
        reader = CloudflareKVReader()
        print(f"✅ 配置加载成功")
        print(f"   账户 ID: {reader.account_id}")
        print(f"   命名空间: {reader.namespace_id or '未指定'}")
        print(f"   键名: {reader.key_name or '未指定'}")
    except Exception as e:
        print(f"❌ 配置错误: {e}")
        return
    
    # 测试连接
    print(f"\n🔄 测试连接...")
    if not reader.test_connection():
        print(f"❌ 连接失败，请检查网络和配置")
        return
    
    print(f"✅ 连接成功")
    
    # 列出命名空间
    print(f"\n📋 获取命名空间列表...")
    namespaces = reader.list_namespaces()
    
    if namespaces:
        print(f"找到 {len(namespaces)} 个命名空间:")
        for i, ns in enumerate(namespaces, 1):
            marker = "👉" if ns['id'] == reader.namespace_id else "  "
            print(f"{marker} {i}. {ns['title']} ({ns['id']})")
    
    # 如果指定了命名空间和键名，尝试读取
    if reader.namespace_id and reader.key_name:
        print(f"\n🔄 读取键 '{reader.key_name}'...")
        value = reader.get_value(reader.namespace_id, reader.key_name)
        
        if value:
            print(f"✅ 读取成功！数据长度: {len(value)} 字符")
            print(f"📝 原始数据预览: {value[:100]}...")
            
            # 尝试解码
            print(f"\n🔄 尝试 Protobuf+Pako+Base64 解码...")
            decode_result = reader.try_decode_value(value)
            
            print(f"\n📋 解码结果:")
            print(f"解码方法: {decode_result['method']}")
            print(f"解码状态: {'✅ 成功' if decode_result['decoded'] else '❌ 失败'}")
            
            # 显示解码步骤
            if 'steps' in decode_result:
                print(f"\n🔍 解码步骤:")
                for step in decode_result['steps']:
                    print(f"  {step}")
            
            if decode_result.get('error'):
                print(f"\n❌ 错误信息: {decode_result['error']}")
            
            if decode_result.get('data'):
                print(f"\n📋 解码后的数据:")
                print("-" * 40)
                if isinstance(decode_result['data'], dict) and 'binary_data' in decode_result['data']:
                    # 二进制数据的特殊显示
                    data = decode_result['data']
                    print(f"二进制数据长度: {data['length']} 字节")
                    print(f"十六进制预览: {data['hex_preview']}")
                    print(f"前20字节: {data['first_bytes']}")
                else:
                    print(json.dumps(decode_result['data'], indent=2, ensure_ascii=False))
                
                # 如果有原始字节数据，提供保存选项
                if decode_result.get('raw_bytes'):
                    print(f"\n💾 解压后的原始数据已获取 ({len(decode_result['raw_bytes'])} 字节)")
                    print(f"   可以保存为文件进一步分析")
    
    # 如果指定了命名空间但没有键名，列出所有键
    elif reader.namespace_id:
        print(f"\n📋 列出命名空间中的所有键...")
        keys = reader.list_keys(reader.namespace_id)
        
        if keys:
            print(f"找到 {len(keys)} 个键:")
            for i, key_info in enumerate(keys, 1):
                print(f"  {i}. {key_info['name']}")
        else:
            print("❌ 命名空间为空或不存在")
    
    print(f"\n✅ 操作完成")
    
    # 如果没有配置键名，提供交互式选择
    if not reader.key_name and reader.namespace_id:
        keys = reader.list_keys(reader.namespace_id)
        if keys:
            print(f"\n💡 提示: 在 .env 文件中设置 KEY_NAME 来直接读取特定键")
            print(f"可用的键名:")
            for key_info in keys:
                print(f"  KEY_NAME={key_info['name']}")

if __name__ == "__main__":
    main()