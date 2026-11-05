"""
批量注册测试账号脚本

用法:
    python scripts/batch_register.py --password 'YourPassword'
    python scripts/batch_register.py --base-url http://localhost:8000 --count 30 --prefix testuser --password 'YourPassword'

密码通过命令行参数或 VIBE_ROUTE_TEST_PASSWORD 环境变量提供，不落入本文件。
"""

import argparse
import hashlib
import json
import os
import socket
import time
from pathlib import Path
from typing import List, Dict
import urllib.request
import urllib.error
import urllib.parse


def validate_base_url(base_url: str) -> str:
    """校验目标地址：仅允许 http(s)，且解析后的 IP 必须是回环或私网地址。

    本脚本用于给本地/内网开发环境批量注册测试账号，禁止指向公网或云元数据地址。
    """
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise SystemExit(f"无效的 base-url（须为 http/https 且含主机名）: {base_url}")
    if parsed.hostname in ("metadata.google.internal", "169.254.169.254"):
        raise SystemExit("禁止请求云元数据地址")
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except OSError as e:
        raise SystemExit(f"base-url 主机解析失败: {e}")
    for info in infos:
        ip = info[4][0]
        if not (ip == "::1" or ip.startswith("127.") or ip.startswith("192.168.")
                or ip.startswith("10.") or ip.startswith("169.254.")
                or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)):
            raise SystemExit(f"base-url 解析到非私网地址 {ip}，已拒绝")
    return base_url


def hash_password(password: str) -> str:
    """前端使用 SHA256 加密密码"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_users(count: int, prefix: str, password: str) -> List[Dict]:
    """生成测试用户列表"""
    users = []
    for i in range(1, count + 1):
        username = f"{prefix}{i:03d}"
        email = f"{username}@example.com"
        hashed_password = hash_password(password)
        users.append({
            "username": username,
            "email": email,
            "password": hashed_password
        })
    return users


def register_user(user: Dict, base_url: str, invite_code: str = None) -> Dict:
    """注册单个用户"""
    payload = user.copy()
    if invite_code:
        payload["invite_code"] = invite_code

    url = f"{base_url}/api/auth/register"
    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = json.loads(response.read().decode('utf-8'))
            return {
                "username": user["username"],
                "email": user["email"],
                "status": "success",
                "user_id": body.get("id")
            }
    except urllib.error.HTTPError as e:
        error_text = e.read().decode('utf-8')[:200]
        return {
            "username": user["username"],
            "email": user["email"],
            "status": "failed",
            "error": error_text
        }
    except Exception as e:
        return {
            "username": user["username"],
            "email": user["email"],
            "status": "error",
            "error": str(e)
        }


def batch_register(users: List[Dict], base_url: str, invite_code: str = None) -> List[Dict]:
    """批量注册用户"""
    results = []
    total = len(users)
    for i, user in enumerate(users, 1):
        print(f"正在注册 [{i}/{total}]: {user['username']}...", end=' ')
        result = register_user(user, base_url, invite_code)
        results.append(result)

        if result["status"] == "success":
            print(f"[OK] 成功 (ID: {result.get('user_id', 'N/A')})")
        else:
            print(f"[FAIL] 失败 - {result.get('error', 'Unknown error')}")

        # 避免请求过快
        time.sleep(0.1)

    return results


def print_summary(results: List[Dict], output_path: str):
    """打印结果摘要"""
    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] in ("failed", "error")]

    print(f"\n{'='*50}")
    print(f"批量注册完成！总计: {len(results)} 个账号")
    print(f"{'='*50}")
    print(f"成功: {len(success)} 个")
    print(f"失败: {len(failed)} 个")

    if success:
        print(f"\n成功注册的账号:")
        for r in success:
            print(f"  - {r['username']} (ID: {r.get('user_id', 'N/A')})")

    if failed:
        print(f"\n失败的账号:")
        for r in failed:
            print(f"  - {r['username']}: {r.get('error', 'Unknown error')}")

    print(f"\n{'='*50}")

    # 保存成功账号到文件（不含密码；密码由操作者在命令行提供，请自行妥善保管）
    if success:
        Path(output_path).write_text(
            "# 批量注册成功的账号\n"
            f"# 总数: {len(success)}\n\n"
            + "".join(f"{r['username']},{r['email']},{r.get('user_id', '')}\n" for r in success),
            encoding="utf-8",
        )
        print(f"账号列表已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="批量注册测试账号")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端地址")
    parser.add_argument("--count", type=int, default=30, help="注册数量")
    parser.add_argument("--prefix", default="testuser", help="用户名前缀")
    parser.add_argument(
        "--password",
        default=os.environ.get("VIBE_ROUTE_TEST_PASSWORD"),
        help="测试账号密码（也可用环境变量 VIBE_ROUTE_TEST_PASSWORD）",
    )
    parser.add_argument("--invite-code", default=None, help="邀请码（可选）")
    parser.add_argument("--output", default="registered_users.txt", help="成功账号输出文件")
    args = parser.parse_args()

    if not args.password:
        parser.error("必须通过 --password 或环境变量 VIBE_ROUTE_TEST_PASSWORD 提供密码")

    validate_base_url(args.base_url)

    print(f"开始批量注册 {args.count} 个测试账号...")
    print(f"后端地址: {args.base_url}")
    print(f"用户名前缀: {args.prefix}")
    print(f"{'='*50}\n")

    users = generate_users(args.count, args.prefix, args.password)
    results = batch_register(users, args.base_url, args.invite_code)
    print_summary(results, args.output)


if __name__ == "__main__":
    main()
