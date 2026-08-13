"""V2 迁移独立入口：python -m app.migrate_v2

等价于应用启动时的 init_db()（含迁移），供生产库手动升级用。
"""
from . import db

if __name__ == "__main__":
    db.init_db()
    print("migration complete")
