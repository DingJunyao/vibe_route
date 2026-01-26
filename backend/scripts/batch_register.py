"""
批量注册测试账号脚本

用法:
    python scripts/batch_register.py
"""

import hashlib
import json
import time
from typing import List, Dict
import urllib.request
import urllib.error
import ssl

# 配置
BASE_URL = "http://localhost:8000"
COUNT = 30
PREFIX = "testuser"
DEFAULT_PASSWORD = "Test123456"
INVITE_CODE = None  # 如果需要邀请码，在这里填写


def hash_password(password: str) -> str:
    """前端使用 SHA256 加密密码"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_users(count: int, prefix: str) -> List[Dict]:
    """生成测试用户列表"""
    users = []
    for i in range(1, count + 1):
        username = f"{prefix}{i:03d}"
        email = f"{username}@example.com"
        hashed_password = hash_password(DEFAULT_PASSWORD)
        users.append({
            "username": username,
            "email": email,
            "password": hashed_password
        })
    return users


def register_user(user: Dict) -> Dict:
    """注册单个用户"""
    payload = user.copy()
    if INVITE_CODE:
        payload["invite_code"] = INVITE_CODE

    url = f"{BASE_URL}/api/auth/register"
    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        # 忽略 SSL 证书验证（仅用于本地开发）
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=context, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return {
                    "username": user["username"],
                    "email": user["email"],
                    "status": "success",
                    "user_id": data.get("id")
                }
            else:
                return {
                    "username": user["username"],
                    "email": user["email"],
                    "status": "failed",
                    "error": f"HTTP {response.status}"
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


def batch_register(users: List[Dict]) -> List[Dict]:
    """批量注册用户"""
    results = []
    total = len(users)
    for i, user in enumerate(users, 1):
        print(f"正在注册 [{i}/{total}]: {user['username']}...", end=' ')
        result = register_user(user)
        results.append(result)

        if result["status"] == "success":
            print(f"[OK] 成功 (ID: {result.get('user_id', 'N/A')})")
        else:
            print(f"[FAIL] 失败 - {result.get('error', 'Unknown error')}")

        # 避免请求过快
        time.sleep(0.1)

    return results


def print_summary(results: List[Dict]):
    """打印结果摘要"""
    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] in ("failed", "error")]

    print(f"\n{'='*50}")
    print(f"批量注册完成！总计: {len(results)} 个账号")
    print(f"{'='*50}")
    print(f"成功: {len(success)} 个")
    print(f"失败: {len(failed)} 个")
    print(f"\n默认密码: {DEFAULT_PASSWORD}")
    print(f"用户名格式: {PREFIX}001 ~ {PREFIX}{COUNT:03d}")

    if success:
        print(f"\n成功注册的账号:")
        for r in success:
            print(f"  - {r['username']} (ID: {r.get('user_id', 'N/A')})")

    if failed:
        print(f"\n失败的账号:")
        for r in failed:
            print(f"  - {r['username']}: {r.get('error', 'Unknown error')}")

    print(f"\n{'='*50}")

    # 保存成功账号到文件
    if success:
        with open("registered_users.txt", "w", encoding="utf-8") as f:
            f.write(f"# 批量注册成功的账号\n")
            f.write(f"# 密码: {DEFAULT_PASSWORD}\n")
            f.write(f"# 总数: {len(success)}\n\n")
            for r in success:
                f.write(f"{r['username']},{r['email']},{r.get('user_id', '')}\n")
        print(f"账号列表已保存到: registered_users.txt")


def main():
    print(f"开始批量注册 {COUNT} 个测试账号...")
    print(f"后端地址: {BASE_URL}")
    print(f"用户名前缀: {PREFIX}")
    print(f"默认密码: {DEFAULT_PASSWORD}")
    print(f"{'='*50}\n")

    users = generate_users(COUNT, PREFIX)
    results = batch_register(users)
    print_summary(results)


if __name__ == "__main__":
    main()
