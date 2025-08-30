#!/usr/bin/env python3
"""
数据抓取模块
负责从目标网站抓取密码数据并保存
"""

import os
import json
import time
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup


class ScrapingConfig:
    """抓取配置类"""
    def __init__(self):
        self.TARGET_URL = 'https://www.kkrb.net/?viewpage=view%2Foverview'
        self.PAGE_LOAD_TIMEOUT = 30
        self.ELEMENT_WAIT_TIMEOUT = 20
        self.CARD_WAIT_TIMEOUT = 10
        self.OUTPUT_DIR = Path(__file__).parent / "output"
        self.JSON_FILENAME = "mima_data.json"
        
        # 确保输出目录存在
        self.OUTPUT_DIR.mkdir(exist_ok=True)


class BrowserManager:
    """浏览器管理类"""
    def __init__(self):
        self.driver = None
        self.browser_name = None
        self.logger = logging.getLogger(__name__)
    
    def create_driver(self) -> Tuple[webdriver.Remote, str]:
        """创建并配置无头浏览器驱动"""
        self.logger.info("初始化浏览器驱动")
        
        browsers = [
            {
                'name': 'Chrome',
                'class': webdriver.Chrome,
                'options': webdriver.ChromeOptions()
            },
            {
                'name': 'Edge',
                'class': webdriver.Edge,
                'options': webdriver.EdgeOptions()
            }
        ]
        
        common_args = [
            '--headless=new',
            '--disable-gpu',
            '--window-size=1920,1080',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        for browser in browsers:
            try:
                for arg in common_args:
                    browser['options'].add_argument(arg)
                
                # 禁用图片加载以加快速度
                if browser['name'] == 'Chrome':
                    browser['options'].add_experimental_option("prefs", {
                        "profile.managed_default_content_settings.images": 2
                    })
                
                driver = browser['class'](options=browser['options'])
                self.driver = driver
                self.browser_name = browser['name']
                
                self.logger.info(f"成功启动 {browser['name']} 浏览器")
                return driver, browser['name']
                
            except WebDriverException as e:
                self.logger.warning(f"{browser['name']} 启动失败: {e}")
                continue
        
        raise RuntimeError('无法启动任何浏览器，请确认本机已安装 Chrome 或 Edge')
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("浏览器已关闭")
            except Exception as e:
                self.logger.warning(f"关闭浏览器时出现异常: {e}")


class DataExtractor:
    """数据提取器"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_card_data(self, card) -> Dict[str, str]:
        """从单个卡片中提取数据"""
        try:
            name_element = card.find('p', class_='overview-bd-t')
            password_element = card.find('p', class_='overview-bd-p')
            date_element = card.find('p', class_='overview-bd-ud')
            
            name = name_element.text.strip() if name_element else 'N/A'
            password = password_element.text.strip() if password_element else 'N/A'
            date = date_element.text.strip().replace('更新', '').strip() if date_element else 'N/A'
            
            return {
                '名称': name,
                '密码': password,
                '日期': date
            }
        except Exception as e:
            self.logger.warning(f"提取卡片数据失败: {e}")
            return {
                '名称': 'N/A',
                '密码': 'N/A',
                '日期': 'N/A'
            }


class DataProcessor:
    """数据处理器"""
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.json_path = self.config.OUTPUT_DIR / self.config.JSON_FILENAME
        
        # 定义地图顺序
        self.map_order = [
            "零号大坝",
            "长弓溪谷", 
            "巴克什",
            "航天基地",
            "潮汐监狱"
        ]
    
    def load_local_data(self) -> List[Dict]:
        """加载本地JSON数据"""
        if not self.json_path.exists():
            self.logger.info("本地数据文件不存在")
            return []
        
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.logger.info(f"成功加载本地数据，共 {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning("本地数据格式不正确，应为列表")
                    return []
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"加载本地数据失败: {e}")
            return []
    
    def sort_data(self, data: List[Dict]) -> List[Dict]:
        """按照预定义顺序对数据进行排序"""
        def get_sort_key(item: Dict) -> int:
            """获取排序键值"""
            name = item.get('名称', '')
            try:
                return self.map_order.index(name)
            except ValueError:
                # 如果地图名称不在预定义列表中，放在最后
                return len(self.map_order)
        
        sorted_data = sorted(data, key=get_sort_key)
        self.logger.debug(f"数据已按照预定义顺序排序: {[item['名称'] for item in sorted_data]}")
        return sorted_data
    
    def merge_data(self, scraped_data: List[Dict], local_data: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        合并抓取数据和本地数据
        基于"名称"进行合并，当"日期"或"密码"不同时更新
        """
        local_by_name = {item.get('名称'): item for item in local_data if isinstance(item, dict)}
        final_by_name = dict(local_by_name)  # 拷贝本地数据
        
        added, updated, unchanged = [], [], []
        
        for item in scraped_data:
            if not isinstance(item, dict):
                continue
                
            name = item.get('名称')
            if not name or name == 'N/A':
                continue
                
            local_item = local_by_name.get(name)
            
            if local_item is None:
                # 新增
                final_by_name[name] = item
                added.append(name)
            else:
                # 检查是否需要更新
                date_changed = item.get('日期') != local_item.get('日期')
                password_changed = item.get('密码') != local_item.get('密码')
                
                if date_changed or password_changed:
                    final_by_name[name] = item
                    updated.append(name)
                else:
                    unchanged.append(name)
        
        # 使用自定义排序方法，按照预定义顺序排序
        merged_list = self.sort_data([final_by_name[k] for k in final_by_name.keys()])
        
        stats = {
            'added': added,
            'updated': updated,
            'unchanged': unchanged,
            'added_count': len(added),
            'updated_count': len(updated),
            'unchanged_count': len(unchanged)
        }
        
        return merged_list, stats
    
    def save_data(self, data: List[Dict]) -> bool:
        """保存数据到JSON文件"""
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"数据已保存到: {self.json_path}")
            return True
            
        except IOError as e:
            self.logger.error(f"保存数据失败: {e}")
            return False


class WebScraper:
    """网页抓取器主类"""
    def __init__(self):
        self.config = ScrapingConfig()
        self.browser_manager = BrowserManager()
        self.data_extractor = DataExtractor()
        self.data_processor = DataProcessor(self.config)
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def scrape_data(self) -> Optional[List[Dict]]:
        """抓取数据的核心方法"""
        driver = None
        
        try:
            # 创建浏览器驱动
            driver, browser_name = self.browser_manager.create_driver()
            
            # 设置页面加载超时
            driver.set_page_load_timeout(self.config.PAGE_LOAD_TIMEOUT)
            
            self.logger.info(f"正在访问目标页面: {self.config.TARGET_URL}")
            driver.get(self.config.TARGET_URL)
            
            # 等待卡片容器加载
            self.logger.info("等待页面容器加载...")
            WebDriverWait(driver, self.config.ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, 'overview-bd-sortable-cards'))
            )
            
            # 等待卡片内容加载
            self.logger.info("等待卡片元素加载...")
            WebDriverWait(driver, self.config.CARD_WAIT_TIMEOUT).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#overview-bd-sortable-cards .layui-col-md3'))
            )
            
            # 获取页面源码并解析
            page_content = driver.page_source
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # 查找卡片容器
            cards_container = soup.find('div', id='overview-bd-sortable-cards')
            if not cards_container:
                raise RuntimeError('未找到卡片容器，页面结构可能已变更')
            
            # 提取所有卡片
            cards = cards_container.find_all('div', class_='layui-col-md3')
            self.logger.info(f"发现 {len(cards)} 张卡片")
            
            if not cards:
                self.logger.warning("未找到任何卡片数据")
                return []
            
            # 提取每张卡片的数据
            results = []
            for i, card in enumerate(cards, 1):
                card_data = self.data_extractor.extract_card_data(card)
                results.append(card_data)
                self.logger.debug(f"第 {i} 张卡片: {card_data['名称']}")
            
            self.logger.info(f"成功抓取 {len(results)} 条数据（使用 {browser_name}）")
            return results
            
        except TimeoutException:
            self.logger.error("页面加载超时，请检查网络连接或增加等待时间")
            return None
            
        except Exception as e:
            self.logger.error(f"抓取过程中发生错误: {e}")
            return None
            
        finally:
            self.browser_manager.close()
    
    def process_and_save(self, scraped_data: List[Dict]) -> bool:
        """处理和保存数据"""
        if not scraped_data:
            self.logger.warning("没有抓取到有效数据")
            return False
        
        # 加载本地数据进行比较
        local_data = self.data_processor.load_local_data()
        
        # 合并数据
        merged_data, stats = self.data_processor.merge_data(scraped_data, local_data)
        
        # 输出统计信息
        self.logger.info(f"数据统计: 新增 {stats['added_count']} 项, "
                        f"更新 {stats['updated_count']} 项, "
                        f"未变更 {stats['unchanged_count']} 项")
        
        if stats['added']:
            self.logger.info(f"新增项目: {', '.join(stats['added'])}")
        
        if stats['updated']:
            self.logger.info(f"更新项目: {', '.join(stats['updated'])}")
        
        # 只有在有新增或更新时才保存
        if stats['added_count'] > 0 or stats['updated_count'] > 0:
            if self.data_processor.save_data(merged_data):
                self.logger.info("数据处理和保存完成")
                return True
            else:
                return False
        else:
            self.logger.info("本地数据与抓取数据无差异，跳过保存")
            return False
    
    def run(self) -> bool:
        """运行抓取流程"""
        start_time = time.time()
        self.logger.info("开始数据抓取流程")
        
        try:
            # 抓取数据
            scraped_data = self.scrape_data()
            
            if scraped_data is None:
                return False
            
            # 处理和保存数据
            result = self.process_and_save(scraped_data)
            
            # 计算耗时
            elapsed_time = int(time.time() - start_time)
            self.logger.info(f"抓取流程完成，耗时 {elapsed_time} 秒")
            
            return result
            
        except Exception as e:
            self.logger.error(f"抓取流程发生未处理的异常: {e}")
            return False


def main() -> bool:
    """主函数"""
    scraper = WebScraper()
    return scraper.run()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
