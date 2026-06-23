# init_db.py
from core.schema import Base
from core.database import engine

def init_database():
    print("正在建立/更新資料庫表格...")
    Base.metadata.create_all(engine)
    print("資料庫初始化完成！")

if __name__ == "__main__":
    init_database()