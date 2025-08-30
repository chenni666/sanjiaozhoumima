from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import time
import json  # 新增导入json模块
import os    # 新增导入os模块用于路径操作
from datetime import datetime  # 新增导入datetime模块用于时间戳

def create_driver():
    """创建并配置无头浏览器驱动"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 初始化浏览器驱动")
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
        '--disable-dev-shm-usage'
    ]
    
    for browser in browsers:
        try:
            for arg in common_args:
                browser['options'].add_argument(arg)
            driver = browser['class'](options=browser['options'])
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 成功启动 {browser['name']} 浏览器")
            return driver, browser['name']
        except WebDriverException as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {browser['name']} 启动失败: {e}")
            continue
    
    raise RuntimeError('无法启动任何浏览器，请确认本机已安装 Chrome 或 Edge')

def extract_card_data(card):
    """从单个卡片中提取数据"""
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

def save_to_json(data, filename=None):
    """
    将数据保存为JSON文件
    
    Args:
        data: 要保存的数据
        filename: 文件名，如果为None则自动生成
    """
    # 如果没有指定文件名，则自动生成带时间戳的文件名
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mima_data.json"
    
    # 确保输出目录存在
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 完整的文件路径
    filepath = os.path.join(output_dir, filename)
    
    # 保存数据为JSON格式
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"数据已保存到: {filepath}")
    return filepath

def load_local_json(filename="mima_data.json"):
    """
    读取本地JSON数据（如果存在）。

    Returns:
        list: 本地数据列表，若文件不存在或格式不正确则返回空列表。
    """
    output_dir = "output"
    filepath = os.path.join(output_dir, filename)
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 确保为列表结构
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []

def merge_on_changes(scraped_list, local_list):
    """
    基于“名称”进行合并：
    - 若本地不存在该名称：新增。
    - 若本地存在且“日期”或“密码”有任一不同：更新为抓取数据。
    - 若均相同：保持不变。

    Args:
        scraped_list (list[dict]): 刚抓取的数据列表，包含 名称/密码/日期。
        local_list (list[dict]): 本地已保存的数据列表。

    Returns:
        tuple[list, dict]: 合并后的完整列表（保留本地未出现于抓取的数据），以及变更统计信息。
    """
    local_by_name = {item.get('名称'): item for item in local_list if isinstance(item, dict)}
    final_by_name = dict(local_by_name)  # 先拷贝本地，默认保留所有本地项

    added, updated, unchanged = [], [], []

    for item in scraped_list:
        if not isinstance(item, dict):
            continue
        name = item.get('名称')
        if not name:
            continue
        local_item = local_by_name.get(name)
        if local_item is None:
            # 新增
            final_by_name[name] = item
            added.append(name)
        else:
            # 比较日期或密码
            date_changed = item.get('日期') != local_item.get('日期')
            pwd_changed = item.get('密码') != local_item.get('密码')
            if date_changed or pwd_changed:
                final_by_name[name] = item
                updated.append(name)
            else:
                unchanged.append(name)

    # 输出列表：按名称排序，保持稳定观感
    merged_list = [final_by_name[k] for k in sorted(final_by_name.keys())]

    stats = {
        'added': added,
        'updated': updated,
        'unchanged': unchanged,
        'added_count': len(added),
        'updated_count': len(updated),
        'unchanged_count': len(unchanged)
    }

    return merged_list, stats

def main():
    """主函数"""
    driver, browser_name = None, None
    start_ts = time.time()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 启动抓取流程")
    
    try:
        driver, browser_name = create_driver()

        # 设置页面加载超时时间
        driver.set_page_load_timeout(30)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 打开页面")

        # 打开目标网页
        driver.get('https://www.kkrb.net/?viewpage=view%2Foverview')

        # 等待直到卡片区域加载完成
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, 'overview-bd-sortable-cards'))
        )
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 页面容器已加载")

        # 额外等待卡片内容加载
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#overview-bd-sortable-cards .layui-col-md3'))
        )
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 卡片元素已出现")

        # 获取页面HTML内容
        page_content = driver.page_source

        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(page_content, 'html.parser')

        # 定位所有卡片容器
        cards_container = soup.find('div', id='overview-bd-sortable-cards')
        if not cards_container:
            raise RuntimeError('未找到卡片容器（overview-bd-sortable-cards）。页面结构可能已变更，或内容尚未加载。')

        cards = cards_container.find_all('div', class_='layui-col-md3')
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 解析到 {len(cards)} 张卡片")

        # 提取每张卡片中的信息
        results = [extract_card_data(card) for card in cards]

        # 打印结果
        print(f"成功抓取数据（使用 {browser_name} 无头模式）：")
        print("-" * 50)
        for i, item in enumerate(results, 1):
            print(f"{i:2d}. {item['名称']:20} | 密码: {item['密码']:15} | 更新日期: {item['日期']}")
        print("-" * 50)
        print(f"共抓取 {len(results)} 条记录")

        # 读取本地已有数据，并仅在“日期或密码不同”时合并更新
        local_data = load_local_json()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 读取本地数据用于对比，现有 {len(local_data)} 条")
        merged, stats = merge_on_changes(results, local_data)

        if stats['added_count'] > 0 or stats['updated_count'] > 0:
            json_filepath = save_to_json(merged)
            print(f"发现新增 {stats['added_count']} 项，更新 {stats['updated_count']} 项，未变更 {stats['unchanged_count']} 项。")
            if stats['added']:
                print("新增:", ", ".join(stats['added']))
            if stats['updated']:
                print("更新:", ", ".join(stats['updated']))
            print(f"数据已导出到JSON文件: {json_filepath}")
        else:
            print("本地数据与此次抓取相比无新增或变化，跳过写入。")
        dur = int(time.time() - start_ts)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STEP] 抓取流程完成，用时 {dur}s")

    except TimeoutException:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 等待页面元素超时，请检查网络或适当增大等待时间。")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 抓取过程中发生错误: {e}")
    finally:
        # 确保浏览器关闭
        if driver:
            driver.quit()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 浏览器已关闭")

if __name__ == "__main__":
    main()