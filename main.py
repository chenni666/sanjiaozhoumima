#!/usr/bin/env python3
"""
主程序入口
依据GitHub Actions工作流程设计，提供数据抓取和HTML更新功能
"""

import os
import time
import json
import logging
from typing import List, Dict, Tuple
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

# 导入自定义模块
import zhuaqu as scraper


class Config:
    """配置管理类"""
    def __init__(self):
        self.BASE_DIR = Path(__file__).parent.absolute()
        self.OUTPUT_DIR = self.BASE_DIR / "output"
        self.JSON_PATH = self.OUTPUT_DIR / "mima_data.json"
        self.HTML_PATH = self.BASE_DIR / "index.html"
        self.BACKUP_PATH = self.HTML_PATH.with_suffix('.html.bak')
        self.RETRY_INTERVAL = 30  # 30秒重试间隔
        self.MAX_RETRIES = 120    # 最大重试次数（1小时）
        
        # 确保输出目录存在
        self.OUTPUT_DIR.mkdir(exist_ok=True)


class Logger:
    """日志管理类"""
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def info(self, message: str):
        self.logger.info(message)
        
    def error(self, message: str):
        self.logger.error(message)
        
    def warning(self, message: str):
        self.logger.warning(message)


class DataManager:
    """数据管理类"""
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
    
    def get_file_mtime(self, path: Path) -> float:
        """获取文件修改时间"""
        try:
            return path.stat().st_mtime if path.exists() else -1.0
        except OSError:
            return -1.0
    
    def load_json_data(self, path: Path) -> List[Dict]:
        """加载JSON数据"""
        try:
            if not path.exists():
                return []
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"加载JSON数据失败: {e}")
            return []
    
    def save_json_data(self, data: List[Dict], path: Path) -> bool:
        """保存JSON数据"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"JSON数据已保存到: {path}")
            return True
        except IOError as e:
            self.logger.error(f"保存JSON数据失败: {e}")
            return False


class HTMLUpdater:
    """HTML更新器类"""
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
    
    def create_backup(self) -> bool:
        """创建HTML备份"""
        try:
            if self.config.HTML_PATH.exists():
                content = self.config.HTML_PATH.read_text(encoding='utf-8')
                self.config.BACKUP_PATH.write_text(content, encoding='utf-8')
                self.logger.info("HTML备份创建成功")
            return True
        except IOError as e:
            self.logger.warning(f"创建HTML备份失败: {e}")
            return False
    
    def build_card_element(self, soup: BeautifulSoup, item: Dict) -> any:
        """构建单个卡片元素"""
        article = soup.new_tag("article", attrs={"class": "card"})

        name_div = soup.new_tag("div", attrs={"class": "name"})
        name_div.string = str(item.get("名称", ""))

        pass_div = soup.new_tag("div", attrs={"class": "pass", "aria-label": "密码"})
        pass_div.string = str(item.get("密码", ""))

        date_div = soup.new_tag("div", attrs={"class": "date"})
        date_div.string = str(item.get("日期", ""))

        article.extend([name_div, pass_div, date_div])
        return article
    
    def update_html(self, data: List[Dict]) -> bool:
        """更新HTML文件"""
        try:
            self.logger.info("开始更新index.html")
            
            # 读取现有HTML
            with open(self.config.HTML_PATH, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, "html.parser")
            section = soup.find("section", class_="list")
            
            if section is None:
                raise RuntimeError('index.html 中未找到 <section class="list"> 区域')

            # 创建备份
            self.create_backup()

            # 清空并重建列表区域
            section.clear()
            section["aria-label"] = "密码列表"

            # 添加所有卡片
            for item in data:
                if isinstance(item, dict):
                    card = self.build_card_element(soup, item)
                    section.append(card)

            # 写回HTML文件
            with open(self.config.HTML_PATH, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            self.logger.info("index.html 更新完成")
            return True
            
        except Exception as e:
            self.logger.error(f"更新HTML失败: {e}")
            return False


class ScrapingManager:
    """抓取管理器"""
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.data_manager = DataManager(config, logger)
        self.html_updater = HTMLUpdater(config, logger)
    
    def run_once_and_maybe_update(self) -> bool:
        """执行一次抓取并可能更新HTML"""
        self.logger.info("开始执行抓取流程")
        
        # 获取抓取前的文件修改时间
        before_mtime = self.data_manager.get_file_mtime(self.config.JSON_PATH)
        
        try:
            # 执行抓取
            self.logger.info("调用抓取模块执行数据抓取")
            success = scraper.main()
            
            if not success:
                self.logger.warning("抓取执行失败")
                return False
                
        except Exception as e:
            self.logger.error(f"抓取过程中出现异常: {e}")
            return False
        
        # 检查文件是否有更新
        after_mtime = self.data_manager.get_file_mtime(self.config.JSON_PATH)
        
        if after_mtime <= before_mtime:
            self.logger.info("未检测到数据更新")
            return False
        
        # 加载新数据
        data = self.data_manager.load_json_data(self.config.JSON_PATH)
        
        if not data:
            self.logger.warning("JSON文件为空或格式不正确")
            return False
        
        # 更新HTML
        if self.html_updater.update_html(data):
            self.logger.info("数据抓取和HTML更新完成")
            return True
        else:
            return False


def main():
    """主函数 - 用于GitHub Actions工作流"""
    # 初始化配置和日志
    config = Config()
    logger = Logger()
    scraping_manager = ScrapingManager(config, logger)
    
    # 设置工作目录
    os.chdir(config.BASE_DIR)
    logger.info("程序启动，开始抓取流程")
    
    # 执行抓取和更新
    success = scraping_manager.run_once_and_maybe_update()
    
    if success:
        logger.info("抓取和更新成功完成")
        return True
    else:
        logger.error("抓取和更新失败")
        return False


def run_once_and_maybe_update() -> bool:
    """为GitHub Actions提供的兼容性函数"""
    return main()


def continuous_mode():
    """连续模式 - 用于本地调试"""
    config = Config()
    logger = Logger()
    scraping_manager = ScrapingManager(config, logger)
    
    os.chdir(config.BASE_DIR)
    logger.info("程序启动，进入连续监控模式")
    
    retry_count = 0
    
    while retry_count < config.MAX_RETRIES:
        retry_count += 1
        logger.info(f"第 {retry_count} 次尝试")
        
        if scraping_manager.run_once_and_maybe_update():
            logger.info("抓取成功，退出连续模式")
            break
        
        if retry_count < config.MAX_RETRIES:
            logger.info(f"等待 {config.RETRY_INTERVAL} 秒后重试")
            time.sleep(config.RETRY_INTERVAL)
    else:
        logger.error(f"已达到最大重试次数 {config.MAX_RETRIES}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        continuous_mode()
    else:
        main()
