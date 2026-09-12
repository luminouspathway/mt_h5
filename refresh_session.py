# -*- coding: utf-8 -*-
# 美团 H5 会话自动拉取（独立脚本）
#
# 作用：无头 Chrome 复用已登录的浏览器数据目录，读取美团登录态
#   （localStorage 的 dfpId/localId/dfp_timestamp + 全部 cookie），
#   写入 session.json，供 meituan_collect.py 使用。
#
# 用法：
#   python refresh_session.py [数据目录] [端口]
#     数据目录: Chrome 用户数据目录（含美团登录态），默认 autoPortData\25460
#     端口:     Chrome 调试端口，默认 25460
#
# 说明：
#   - 无头模式必须指向"已登录美团"的数据目录，否则读不到 dfpId/localId
#   - 换新账号后，在同一浏览器登录新号，再运行本脚本即可自动更新 session.json
#   - 也支持环境变量 DP_USER_DATA_DIR 指定数据目录
import json, sys, os, time

from DrissionPage import Chromium, ChromiumOptions

PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 25460
BASE = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE, "session.json")
USER_DATA_DIR = os.environ.get(
    "DP_USER_DATA_DIR",
    (
        sys.argv[1]
        if len(sys.argv) > 1
        else rf"C:\Users\user\AppData\Local\Temp\DrissionPage\autoPortData\{PORT}"
    ),
)


def main():
    co = ChromiumOptions()
    co.set_local_port(PORT)
    co.set_user_data_path(USER_DATA_DIR)
    co.headless(True)  # 无头模式
    browser = Chromium(co)
    try:
        tab = browser.latest_tab
        if "meituan" not in tab.url:
            tab.get("https://h5.waimai.meituan.com/")
            time.sleep(3)

        ls = tab.run_js(
            "return JSON.stringify({"
            "dfpId: localStorage.getItem('dfpId'),"
            "localId: localStorage.getItem('localId'),"
            "dfp_timestamp: localStorage.getItem('dfp_timestamp'),"
            "uuid: localStorage.getItem('uuid')"
            "})"
        )
        store = json.loads(ls) if ls else {}
        dfp_id = store.get("dfpId")
        local_id = store.get("localId")
        dfp_ts = store.get("dfp_timestamp")
        uuid = store.get("uuid")

        cookies = {}
        try:
            for c in tab.cookies():
                name, val = c.get("name"), c.get("value")
                if name and name not in cookies:
                    cookies[name] = val
        except Exception as e:
            print("[cookies warn]", e)

        if not dfp_id or not local_id:
            print(
                "[ERR] 未读到 dfpId/localId。请确认数据目录已登录美团外卖：",
                USER_DATA_DIR,
            )
            sys.exit(1)

        # uuid 从 cookie 补（localStorage 里可能没有 uuid 键）
        if not uuid:
            for cand in ("uuid", "openh5_uuid", "iuuid"):
                if cookies.get(cand):
                    uuid = cookies[cand]
                    break

        session = {
            "dfpId": dfp_id,
            "localId": local_id,
            "dfp_timestamp": dfp_ts or "",
            "uuid": uuid or "",
            "cookies": cookies,
        }
        _d = os.path.dirname(SESSION_FILE)
        if _d:
            os.makedirs(_d, exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
        print("[dfpId]", dfp_id)
        print("[localId]", local_id)
        print("[dfp_timestamp]", dfp_ts)
        print("[uuid]", uuid)
        print("[cookies]", len(cookies), "个")
        print("[OK] 已写入", SESSION_FILE)
    finally:
        browser.quit()


if __name__ == "__main__":
    main()
