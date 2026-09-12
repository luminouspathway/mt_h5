# -*- coding: utf-8 -*-
# https://h5.waimai.meituan.com/login
# 美团外卖 H5 mtgsig 纯协议采集
#
# 功能：
#   1. refresh：无头 Chrome 拉取浏览器会话 → session.json
#      复用已登录的美团浏览器数据目录（DrissionPage autoPortData\<port>），
#      读取 localStorage 的 dfpId/localId/dfp_timestamp 及全部 cookie。
#   2. collect（默认）：纯协议采集
#      - Node 沙箱加载 H5guard.js 生成 mtgsig
#      - python requests 纯协议请求（cookie 携带 WEBDFPID，服务端据此关联 tempKey）
#
# 用法：
# 使用默认数据目录（autoPortData\25460）
#   python meituan_collect.py refresh

# 指定数据目录 + 端口
#   python meituan_collect.py refresh "C:\path\to\your\chrome\profile" 9222

#   python meituan_collect.py collect      # 采集（默认，可省略 collect）
#
# 首次使用：
#   先用有头浏览器登录美团外卖 https://h5.waimai.meituan.com/waimai/mindex/menu，
#   登录态写入 Chrome 数据目录；之后 refresh 即可无头拉取。
import json, subprocess, sys, os, time, urllib.parse
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
SIGNER = os.path.join(BASE, "standalone_sign.js")
SESSION_FILE = os.path.join(BASE, "session.json")


# =====================================================================
# 手动 cookie 覆盖区（换号最直接的方式）
# ---------------------------------------------------------------------
# 把从网页复制的 cookies 字典整段粘贴到下面 MANUAL_COOKIES = {} 里即可。
# 填了将优先使用，忽略 session.json 的 cookies；留空则走 session.json。
# 指纹（dfpId/localId/dfp_timestamp/uuid）会自动从 WEBDFPID 解析，
# 无需手动填。示例：
#   MANUAL_COOKIES = {
#       "uuid": "",
#       "WEBDFPID": "",
#       "token": "",
#       ......
# }
# =====================================================================
MANUAL_COOKIES  = {

}


def _resolve_fingerprint(cookies):
    """从 cookies 的 WEBDFPID（dfpId - dfp_timestamp - localId）解析指纹，返回 dict。
    若无法解析则返回 None（调用方回退旧值）。"""
    w = cookies.get("WEBDFPID")
    if not w or w.count("-") < 2:
        return None
    parts = w.split("-", 2)
    return {
        "dfpId": parts[0],
        "dfp_timestamp": parts[1],
        "localId": parts[2],
    }


# ============ 会话加载 ============
def load_session():
    if MANUAL_COOKIES:
        # 手动 cookie：优先使用，指纹从 WEBDFPID 解析
        cookies = dict(MANUAL_COOKIES)
        fp = _resolve_fingerprint(cookies)
        if not fp:
            raise RuntimeError(
                "手动 MANUAL_COOKIES 里缺少 WEBDFPID（格式 dfpId-timestamp-localId），无法确定指纹"
            )
        return {
            **fp,
            "uuid": cookies.get("uuid") or cookies.get("openh5_uuid") or cookies.get("iuuid") or "",
            "cookies": cookies,
        }
    if not os.path.exists(SESSION_FILE):
        raise RuntimeError(
            "缺少 session.json。请先运行: python refresh_session.py [数据目录] [端口]\n"
            "（无头模式从已登录的浏览器数据目录拉取 cookie/dfpId）"
        )
    with open(SESSION_FILE, encoding="utf-8") as f:
        return json.load(f)


S = load_session()
DFPID = S["dfpId"]
DFP_TS = S["dfp_timestamp"]
LOCALID = S["localId"]
UUID = S["uuid"]
WEBDFPID = f"{DFPID}-{DFP_TS}-{LOCALID}"
COOKIES = dict(S.get("cookies", {}))
COOKIES["WEBDFPID"] = WEBDFPID

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
# 店铺菜单页地址（originUrl 参数，抓包可得；换店铺时同步改 poi_id_str 等）
ORIGIN_URL = "https://h5.waimai.meituan.com/waimai/mindex/menu"


def build_body(poi_id_str="cLUcTuH14UkpVesFmYHLVQI", spu_tag_id="863444338", uuid=UUID):
    """构造 menuproducts 请求体（application/x-www-form-urlencoded）。

    参数说明：
      poi_id_str : 店铺 ID。来自店铺菜单页 URL 里的 poi_id_str 参数（换店铺时改这里）。
      spu_tag_id : 商品分类 tag ID。来自抓包的请求体 spu_tag_id 字段（换店铺/分类时改这里）。
      uuid       : 设备唯一标识。默认取 session.json 的 uuid（换号后 refresh 自动更新）。

    注意：mtgsig 签名绑定本请求体，body 改动后必须重新 sign（fetch 内部已自动处理）。
    """
    data = {
        "optimus_code": "",
        "optimus_risk_level": "",
        "wm_poi_id": "",
        "poi_id_str": poi_id_str,
        "spu_tag_id": spu_tag_id,
        "support_new_page_v3": "",
        "sort_type": "",
        "tag_type": "",
        "link_identifier_info": "",
        "uuid": uuid,
        "platform": "",
        "partner": "",
        "originUrl": ORIGIN_URL,
        "riskLevel": "",
        "optimusCode": "",
        "wm_latitude": "",
        "wm_longitude": "",
        "wm_actual_latitude": "",
        "wm_actual_longitude": "",
        "wmUuidDeregistration": "0",
        "wmUserIdDeregistration": "0",
        "openh5_uuid": uuid,
    }
    return "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in data.items()
    )


def sign(ts, body):
    """用沙箱 H5guard 生成 mtgsig"""
    env = dict(os.environ)
    env["SIGN_URL"] = (
        f"https://i.waimai.meituan.com/openh5/v2/poi/menuproducts"
    )
    env["SIGN_DATA"] = body
    env["DFPID"] = DFPID
    env["LOCALID"] = LOCALID
    env["DFP_TS"] = DFP_TS
    r = subprocess.run(
        ["node", SIGNER], capture_output=True, text=True, cwd=BASE, timeout=60, env=env
    )
    if r.returncode != 0:
        raise RuntimeError("sign error: " + (r.stderr or "")[-500:])
    for line in (r.stdout or "").splitlines():
        if line.startswith("MTGSIG:"):
            return json.loads(line[len("MTGSIG:") :])
    raise RuntimeError("no MTGSIG output")


def fetch(url_path="/openh5/v2/poi/menuproducts", body=None, ts=None):
    """纯协议请求，返回 (resp, mtgsig)"""
    if body is None:
        body = build_body()
    if ts is None:
        ts = int(time.time() * 1000)
    mt = sign(ts, body)
    url = f"https://i.waimai.meituan.com{url_path}"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://h5.waimai.meituan.com",
        "Referer": "https://h5.waimai.meituan.com/",
        "User-Agent": UA,
        "mtgsig": json.dumps(mt, separators=(",", ":")),
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    resp = requests.post(url, headers=headers, cookies=COOKIES, data=body, timeout=30)
    return resp, mt


def cmd_collect():
    for i in range(1):
        resp, mt = fetch()
        print(f"[{i}] HTTP {resp.status_code}  a2={mt['a2']} a6len={len(mt['a6'])}")
        if resp.status_code == 200:
            try:
                print(resp.json())
                
            except Exception:
                print("    " + resp.text)
        else:
            print("    " + resp.text)
        time.sleep(1)


if __name__ == "__main__":
    cmd_collect()

