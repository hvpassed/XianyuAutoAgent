import os
import json
from typing import Optional, Dict, List
from dotenv import load_dotenv
from PyCookieCloud import PyCookieCloud



class GoofishCookieFetcher:
    """专门用于获取 goofish.com 相关域名 cookies 的类"""
    
    # goofish 相关的域名列表
    GOOFISH_DOMAINS = [
        'goofish.com',
    ]
    
    def __init__(self, 
                 cookie_cloud_url: Optional[str] = None,
                 cookie_cloud_uuid: Optional[str] = None, 
                 cookie_cloud_password: Optional[str] = None):
        """
        初始化 GoofishCookieFetcher
        
        :param cookie_cloud_url: CookieCloud 服务器地址，如果为 None 则从环境变量读取
        :param cookie_cloud_uuid: CookieCloud UUID，如果为 None 则从环境变量读取
        :param cookie_cloud_password: CookieCloud 密码，如果为 None 则从环境变量读取
        """
        # 加载环境变量
        load_dotenv()

        self.cookie_cloud_url = cookie_cloud_url or os.getenv("COOKIE_CLOUD_URL")
        self.cookie_cloud_uuid = cookie_cloud_uuid or os.getenv("COOKIE_CLOUD_UUID")
        self.cookie_cloud_password = cookie_cloud_password or os.getenv("COOKIE_CLOUD_PASSWORD")
        
        if not all([self.cookie_cloud_url, self.cookie_cloud_uuid, self.cookie_cloud_password]):
            raise ValueError("请提供 CookieCloud 配置或在 .env 文件中设置相关环境变量")
        
        self._cookie_cloud = None
        self._cached_data = None
        
    @property
    def cookie_cloud(self):
        """懒加载 CookieCloud 实例"""
        if self._cookie_cloud is None:
            self._cookie_cloud = PyCookieCloud(
                self.cookie_cloud_url,
                self.cookie_cloud_uuid,
                self.cookie_cloud_password
            )
        return self._cookie_cloud
    
    def _get_all_cookies_data(self) -> Optional[Dict]:
        """获取所有 cookie 数据，带缓存"""
        if self._cached_data is None:
            #print("从 CookieCloud 获取数据...")
            self._cached_data = self.cookie_cloud.get_decrypted_data()
            # if self._cached_data:
            #     #print(f"成功获取 {len(self._cached_data)} 个域名的数据")
            # else:
            #     #print("获取数据失败")
        return self._cached_data
    
    def get_goofish_domains(self) -> List[str]:
        """
        获取当前数据中包含的 goofish 相关域名
        
        :return: goofish 相关域名列表
        """
        data = self._get_all_cookies_data()
        if not data:
            return []
        
        goofish_domains = []
        for domain in data.keys():
            if any(goofish_domain in domain.lower() for goofish_domain in self.GOOFISH_DOMAINS):
                goofish_domains.append(domain)
        
        return goofish_domains
    
    def get_cookies_for_domain(self, domain: str) -> Optional[str]:
        """
        获取指定域名的 cookie 字符串
        
        :param domain: 域名
        :return: cookie 字符串，格式为 "name1=value1; name2=value2"
        """
        data = self._get_all_cookies_data()
        if not data or domain not in data:
            return None
        
        cookies = data[domain]
        cookie_pairs = []
        
        for cookie in cookies:
            name = cookie.get('name', '').strip()
            value = cookie.get('value', '').strip()
            if name and value:
                cookie_pairs.append(f"{name}={value}")
        
        return '; '.join(cookie_pairs) if cookie_pairs else None
    
    def get_goofish_cookies(self, preferred_domain: str = 'goofish.com') -> Optional[str]:
        """
        获取 goofish 的 cookie 字符串
        
        :param preferred_domain: 首选域名，默认为 'goofish.com'
        :return: cookie 字符串
        """
        goofish_domains = self.get_goofish_domains()
        
        if not goofish_domains:
            print("未找到 goofish 相关域名的 cookies")
            return None
        
        print(f"找到 {len(goofish_domains)} 个 goofish 相关域名:")
        for i, domain in enumerate(goofish_domains, 1):
            print(f"  {i}. {domain}")
        
        # 优先选择首选域名
        target_domain = None
        for domain in goofish_domains:
            if preferred_domain.lower() in domain.lower():
                target_domain = domain
                break
        
        # 如果没有找到首选域名，选择第一个
        if not target_domain:
            target_domain = goofish_domains[0]
        
        print(f"选择域名: {target_domain}")
        
        cookie_string = self.get_cookies_for_domain(target_domain)
        if cookie_string:
            print(f"成功获取 cookies")
            return cookie_string
        else:
            print(f"该域名没有有效的 cookies")
            return None
    
    def get_all_goofish_cookies(self) -> Dict[str, str]:
        """
        获取所有 goofish 相关域名的 cookie 字符串
        
        :return: 域名到 cookie 字符串的映射
        """
        goofish_domains = self.get_goofish_domains()
        result = {}
        
        for domain in goofish_domains:
            cookie_string = self.get_cookies_for_domain(domain)
            if cookie_string:
                result[domain] = cookie_string
        
        return result
    
    def get_specific_cookie_value(self, cookie_name: str, domain: Optional[str] = None) -> Optional[str]:
        """
        获取指定 cookie 的值
        
        :param cookie_name: cookie 名称
        :param domain: 指定域名，如果为 None 则在所有 goofish 域名中搜索
        :return: cookie 值
        """
        if domain:
            # 在指定域名中查找
            data = self._get_all_cookies_data()
            if not data or domain not in data:
                return None
            
            cookies = data[domain]
            for cookie in cookies:
                if cookie.get('name') == cookie_name:
                    return cookie.get('value')
        else:
            # 在所有 goofish 域名中查找
            goofish_domains = self.get_goofish_domains()
            data = self._get_all_cookies_data()
            
            for domain in goofish_domains:
                if domain in data:
                    cookies = data[domain]
                    for cookie in cookies:
                        if cookie.get('name') == cookie_name:
                            return cookie.get('value')
        
        return None
    
    def refresh_cache(self):
        """刷新缓存，重新获取数据"""
        self._cached_data = None
        print("🔄 缓存已清空")
    def get_goofish_cookie_str(self) -> Optional[str]:
        return self.get_cookies_for_domain('goofish.com')

def main():
    """示例用法"""
    print("🔧 Goofish Cookie 获取工具")
    print("=" * 50)
    
    try:
        # 创建获取器
        fetcher = GoofishCookieFetcher()
        
        print(fetcher.get_goofish_cookie_str())

        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()