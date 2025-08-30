#!/usr/bin/env python3
import os
import time
import json
from typing import List, Dict
from datetime import datetime

from bs4 import BeautifulSoup

# 直接导入并调用 zhuaqu.main()，避免子进程管理的复杂性
import zhuaqu

# 基于脚本所在目录，避免 cron 下 CWD 不一致
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "output", "mima_data.json")
HTML_PATH = os.path.join(BASE_DIR, "index.html")
INTERVAL_SECONDS = 5 * 60  # 5 分钟


def log(step: str):
	now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	print(f"[{now}] {step}")


def _get_mtime(path: str) -> float:
	try:
		return os.path.getmtime(path)
	except OSError:
		return -1.0


def _load_json_list(path: str) -> List[Dict]:
	try:
		with open(path, "r", encoding="utf-8") as f:
			data = json.load(f)
			return data if isinstance(data, list) else []
	except Exception:
		return []


def _update_index_html(data: List[Dict], html_path: str = HTML_PATH) -> None:
	log("[HTML] 开始更新 index.html")
	# 读取现有 HTML
	with open(html_path, "r", encoding="utf-8") as f:
		html = f.read()

	soup = BeautifulSoup(html, "html.parser")
	section = soup.find("section", class_="list")
	if section is None:
		raise RuntimeError('index.html 中未找到 <section class="list"> 区域，无法写入数据')

	# 清空列表区域并重建卡片
	section.clear()
	section["aria-label"] = "密码列表"

	def build_card(item: Dict):
		article = soup.new_tag("article", attrs={"class": "card"})

		name_div = soup.new_tag("div", attrs={"class": "name"})
		name_div.string = str(item.get("名称", ""))

		pass_div = soup.new_tag("div", attrs={"class": "pass", "aria-label": "密码"})
		pass_div.string = str(item.get("密码", ""))

		date_div = soup.new_tag("div", attrs={"class": "date"})
		date_div.string = str(item.get("日期", ""))

		article.append(name_div)
		article.append(pass_div)
		article.append(date_div)
		return article

	for item in data:
		if isinstance(item, dict):
			section.append(build_card(item))

	# 写回 HTML（先备份）
	backup_path = html_path + ".bak"
	try:
		if os.path.exists(html_path):
			with open(backup_path, "w", encoding="utf-8") as bf:
				bf.write(html)
	except Exception:
		# 备份失败不应阻塞主流程
		pass

	with open(html_path, "w", encoding="utf-8") as f:
		# 直接写 str(soup) 尽量减少重排
		f.write(str(soup))
	log("[HTML] index.html 更新完成")


def run_once_and_maybe_update() -> bool:
	"""
	执行一次抓取：
	- 在执行前后比较 JSON 文件 mtime。
	- 若更新发生，读取 JSON 并更新 index.html。
	返回：是否已更新并完成（True 则主循环应退出）。
	"""
	log("[RUN] 开始抓取流程：比较 JSON mtime")
	before_mtime = _get_mtime(JSON_PATH)

	try:
		# 执行抓取逻辑；内部仅在有变化时才写 mima_data.json
		log("[RUN] 调用 zhuaqu.main() 执行抓取")
		zhuaqu.main()
	except Exception as e:
		log(f"[ERR] 运行 zhuaqu 失败：{e}")
		return False  # 失败则等待重试

	after_mtime = _get_mtime(JSON_PATH)
	updated = (after_mtime > before_mtime)

	if not updated:
		log("[RUN] 未检测到数据更新，将于5分钟后重试……")
		return False

	data = _load_json_list(JSON_PATH)
	if not data:
		log("[RUN] JSON 文件存在但为空或格式不正确，稍后重试……")
		return False

	try:
		_update_index_html(data, HTML_PATH)
		log("[OK ] index.html 已根据最新 JSON 成功更新。")
		return True
	except Exception as e:
		log(f"[ERR] 更新 index.html 失败：{e}")
		return False


def main_loop():
	# 确保工作目录为脚本目录（影响相对路径的依赖如 zhuaqu 的输出）
	log("[INIT] 设置工作目录并进入循环")
	try:
		os.chdir(BASE_DIR)
	except Exception:
		pass
	while True:
		loop_start = time.time()
		log("[LOOP] 本轮开始")
		done = run_once_and_maybe_update()
		if done:
			log("[LOOP] 已完成更新，退出主循环")
			break
		elapsed = int(time.time() - loop_start)
		remaining = max(0, INTERVAL_SECONDS - elapsed)
		log(f"[LOOP] 本轮结束，将在 {remaining}s 后重试")
		time.sleep(remaining)


if __name__ == "__main__":
	log("[MAIN] 程序启动")
	main_loop()
	log("[MAIN] 程序退出")

