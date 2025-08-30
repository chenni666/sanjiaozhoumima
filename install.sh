#!/usr/bin/env bash
# 一键安装脚本（Linux）
# 作用：
# 1) 安装 Microsoft Edge（优先，适配国内网络），必要时按架构回退到 Chromium
# 2) 安装 Python3（尽量选择较新版本）并创建虚拟环境 .venv
# 3) 使用清华镜像安装 Python 依赖（selenium、beautifulsoup4、lxml 可选）
# 4) 进行一次基础校验

set -euo pipefail

echo "[1/7] 检测权限与包管理器..."
if [ "$(id -u)" -ne 0 ]; then
	SUDO=sudo
else
	SUDO=""
fi

PM=""
if command -v apt-get >/dev/null 2>&1; then
	PM=apt
elif command -v dnf >/dev/null 2>&1; then
	PM=dnf
elif command -v yum >/dev/null 2>&1; then
	PM=yum
elif command -v zypper >/dev/null 2>&1; then
	PM=zypper
else
	echo "不支持的发行版：未找到 apt/dnf/yum/zypper"
	exit 1
fi

ARCH=$(uname -m)
echo "检测到架构: ${ARCH}; 包管理器: ${PM}"

echo "[2/7] 安装基础工具..."
case "$PM" in
	apt)
		export DEBIAN_FRONTEND=noninteractive
		$SUDO apt-get update -y
		$SUDO apt-get install -y --no-install-recommends \
			ca-certificates curl wget gnupg unzip software-properties-common \
			fonts-liberation fonts-noto-cjk
		;;
	dnf)
		$SUDO dnf -y install ca-certificates curl wget gnupg2 unzip \
			google-noto-sans-cjk-fonts || true
		;;
	yum)
		$SUDO yum -y install ca-certificates curl wget gnupg2 unzip \
			google-noto-sans-cjk-fonts || true
		;;
	zypper)
		$SUDO zypper --non-interactive refresh
		$SUDO zypper --non-interactive install ca-certificates curl wget gpg2 unzip \
			noto-sans-cjk-fonts || true
		;;
esac

echo "[3/7] 安装浏览器（优先 Edge）..."
install_edge=false
if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then
	case "$PM" in
		apt)
			# Microsoft Edge APT 源（全球 CDN，国内可直接访问）
			if [ ! -f /etc/apt/trusted.gpg.d/microsoft.gpg ]; then
				curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | \
					gpg --dearmor | $SUDO tee /etc/apt/trusted.gpg.d/microsoft.gpg >/dev/null
			fi
			echo "deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/microsoft.gpg] https://packages.microsoft.com/repos/edge stable main" | \
				$SUDO tee /etc/apt/sources.list.d/microsoft-edge.list >/dev/null
			$SUDO apt-get update -y
			if $SUDO apt-get install -y microsoft-edge-stable; then
				install_edge=true
			fi
			;;
		dnf)
			$SUDO rpm --import https://packages.microsoft.com/keys/microsoft.asc || true
			EDGE_REPO=/etc/yum.repos.d/microsoft-edge.repo
			if [ ! -f "$EDGE_REPO" ]; then
				$SUDO bash -c 'cat > /etc/yum.repos.d/microsoft-edge.repo <<"EOF"
[microsoft-edge]
name=Microsoft Edge
baseurl=https://packages.microsoft.com/yumrepos/edge
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
EOF'
			fi
			if $SUDO dnf -y install microsoft-edge-stable; then
				install_edge=true
			fi
			;;
		yum)
			$SUDO rpm --import https://packages.microsoft.com/keys/microsoft.asc || true
			EDGE_REPO=/etc/yum.repos.d/microsoft-edge.repo
			if [ ! -f "$EDGE_REPO" ]; then
				$SUDO bash -c 'cat > /etc/yum.repos.d/microsoft-edge.repo <<"EOF"
[microsoft-edge]
name=Microsoft Edge
baseurl=https://packages.microsoft.com/yumrepos/edge
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
EOF'
			fi
			if $SUDO yum -y install microsoft-edge-stable; then
				install_edge=true
			fi
			;;
		zypper)
			$SUDO rpm --import https://packages.microsoft.com/keys/microsoft.asc || true
			if ! zypper lr | grep -qi edge; then
				$SUDO zypper --non-interactive addrepo \
					https://packages.microsoft.com/yumrepos/edge microsoft-edge || true
			fi
			if $SUDO zypper --non-interactive install microsoft-edge-stable; then
				install_edge=true
			fi
			;;
	esac
else
	echo "非 x86_64 架构，Edge 官方 Linux 包不可用，将回退到 Chromium。"
fi

if ! $install_edge; then
	echo "Edge 安装未成功，尝试安装 Chromium 作为回退..."
	case "$PM" in
		apt)
			$SUDO apt-get install -y chromium-browser || $SUDO apt-get install -y chromium || true
			# 可选：同时安装匹配的 chromedriver（某些版本仓库提供）
			$SUDO apt-get install -y chromium-driver || true
			;;
		dnf)
			$SUDO dnf -y install chromium || true
			;;
		yum)
			$SUDO yum -y install chromium || true
			;;
		zypper)
			$SUDO zypper --non-interactive install chromium || true
			;;
	esac
fi

echo "[4/7] 安装 Python 与 venv（尽量较新）..."
PYTHON=python3
have_py=false
case "$PM" in
	apt)
		$SUDO apt-get install -y python3 python3-venv python3-pip
		# 按版本优先级尝试安装更高版本（若仓库可用）
		for ver in 3.13 3.12 3.11; do
			if apt-cache show python${ver} >/dev/null 2>&1; then
				$SUDO apt-get install -y python${ver} python${ver}-venv || true
				PYTHON="python${ver}"
				have_py=true
				break
			fi
		done
		;;
	dnf)
		$SUDO dnf -y install python3 python3-pip python3-virtualenv || true
		# Fedora/RHEL 的特定版本包可选
		for ver in 3.13 3.12 3.11; do
			if dnf list --available python${ver} >/dev/null 2>&1; then
				$SUDO dnf -y install python${ver} python${ver}-pip || true
				PYTHON="python${ver}"
				have_py=true
				break
			fi
		done
		;;
	yum)
		$SUDO yum -y install python3 python3-pip || true
		;;
	zypper)
		$SUDO zypper --non-interactive install python3 python3-pip python3-venv || true
		;;
esac

if ! command -v $PYTHON >/dev/null 2>&1; then
	echo "未检测到可用的 $PYTHON，可尝试手工安装更高版本 Python 或使用 pyenv。"
	exit 1
fi

echo "使用 Python 解释器：$($PYTHON --version 2>&1)"

echo "[5/7] 创建虚拟环境 .venv 并安装依赖（清华源）..."
$PYTHON -m venv .venv || $PYTHON -m ensurepip --upgrade && $PYTHON -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install \
	selenium \
	beautifulsoup4 \
	lxml \
	-i https://pypi.tuna.tsinghua.edu.cn/simple

echo "[6/7] 创建输出目录..."
mkdir -p output

echo "[7/7] 校验 Selenium 与浏览器可用性..."
python - <<'PY'
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

ok = False
err = None

try:
		# 优先尝试 Edge
		try:
				opts = webdriver.EdgeOptions()
				opts.add_argument('--headless=new')
				opts.add_argument('--disable-gpu')
				opts.add_argument('--no-sandbox')
				driver = webdriver.Edge(options=opts)
				ok = True
				driver.quit()
				print('Edge 启动正常。')
		except Exception as e:
				err = e
				print(f'Edge 启动失败：{e}')
				# 退回尝试 Chrome/Chromium
				try:
						copts = webdriver.ChromeOptions()
						copts.add_argument('--headless=new')
						copts.add_argument('--disable-gpu')
						copts.add_argument('--no-sandbox')
						cdrv = webdriver.Chrome(options=copts)
						ok = True
						cdrv.quit()
						print('Chrome/Chromium 启动正常。')
				except Exception as e2:
						err = e2
						print(f'Chrome/Chromium 启动失败：{e2}')
finally:
		if not ok:
				raise SystemExit(1)
PY

if [ $? -eq 0 ]; then
	echo "安装完成 ✅"
	echo
	echo "使用方法："
	echo "  source .venv/bin/activate"
	echo "  python main.py"
else
	echo "安装完成，但浏览器启动校验失败，请检查服务器网络与依赖。"
	exit 1
fi

