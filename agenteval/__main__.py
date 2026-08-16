"""支持 python -m agenteval web / demo。"""

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("用法：python -m agenteval web | demo")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "web":
        from agenteval.cli import web
        web()
    elif cmd == "demo":
        from agenteval.cli import demo
        demo()
    else:
        print(f"未知命令：{cmd}。可用命令：web, demo")
        sys.exit(1)


if __name__ == "__main__":
    main()
