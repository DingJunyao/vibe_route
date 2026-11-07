# 临时调试脚本：SSH 执行命令并回显输出（凭据从环境变量读取）
import os
import sys

import paramiko


def main() -> None:
    host = os.environ["SSH_HOST"]
    user = os.environ["SSH_USER"]
    password = os.environ["SSH_PASSWORD"]
    commands = sys.argv[1:]
    if not commands:
        print("usage: python _ssh_run.py 'cmd1' 'cmd2' ...")
        raise SystemExit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=15)
    try:
        for cmd in commands:
            print(f"$ {cmd}")
            _, stdout, stderr = client.exec_command(
                f"echo {password} | sudo -S {cmd}", timeout=120
            )
            out = stdout.read().decode(errors="replace")
            err = stderr.read().decode(errors="replace")
            for line in out.splitlines():
                if line.strip():
                    print(" ", line)
            if err.strip():
                print("  [err]", err.strip()[:300])
    finally:
        client.close()


if __name__ == "__main__":
    main()
